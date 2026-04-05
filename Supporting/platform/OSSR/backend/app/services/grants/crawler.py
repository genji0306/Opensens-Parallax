"""
Grant crawler.

Primary backend is crawl4ai (https://github.com/unclecode/crawl4ai) —
a Playwright-based browser crawler with structured extraction. When
crawl4ai (or its Playwright runtime) isn't installed, we fall back to a
plain httpx + HTML-to-text pipeline so the module still works in minimal
environments.

Two-stage crawl:
    1. Fetch the listing page of a source and extract candidate call URLs
       (for hub sites like fundsforngos.org the listing page is just
       links to real funder pages).
    2. For each candidate, fetch the target page and return its
       cleaned text + metadata for the LLM extractor downstream.

Guardrails:
    - polite rate limiting (min interval between requests per host)
    - max pages per crawl
    - robots.txt respected when crawl4ai is available (it honours it by
      default); fallback httpx path also checks robots.txt
    - all network calls wrapped in timeouts
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)

# Try to import crawl4ai; fall back gracefully if missing.
try:  # pragma: no cover - import guard
    from crawl4ai import AsyncWebCrawler, CrawlerRunConfig  # type: ignore
    _HAS_CRAWL4AI = True
except Exception:  # noqa: BLE001
    _HAS_CRAWL4AI = False

try:
    import httpx  # httpx is already in the OSSR deps
    _HAS_HTTPX = True
except Exception:  # noqa: BLE001
    _HAS_HTTPX = False


REQUEST_TIMEOUT_S = 30.0
POLITE_INTERVAL_S = 2.0          # min seconds between requests to the same host
DEFAULT_MAX_PAGES = 40
USER_AGENT = "OpensensGrantHunt/1.0 (+https://opensens.fr)"


@dataclass
class CrawledPage:
    url: str
    title: str
    text: str
    html: str = ""
    links: List[str] = None  # type: ignore[assignment]
    status: int = 200
    fetched_at: float = 0.0

    def __post_init__(self) -> None:
        if self.links is None:
            self.links = []
        if not self.fetched_at:
            self.fetched_at = time.time()


class HostRateLimiter:
    """Simple per-host interval gate."""

    def __init__(self, interval: float = POLITE_INTERVAL_S) -> None:
        self.interval = interval
        self._last: dict[str, float] = {}

    async def wait(self, host: str) -> None:
        now = time.monotonic()
        last = self._last.get(host, 0.0)
        delay = self.interval - (now - last)
        if delay > 0:
            await asyncio.sleep(delay)
        self._last[host] = time.monotonic()


class GrantCrawler:
    """
    Async crawler with crawl4ai primary + httpx fallback.
    Call .crawl() from sync code via asyncio.run() or from an async context.
    """

    def __init__(
        self,
        max_pages: int = DEFAULT_MAX_PAGES,
        interval_s: float = POLITE_INTERVAL_S,
    ) -> None:
        self.max_pages = max_pages
        self.rate = HostRateLimiter(interval_s)
        self._robots_cache: dict[str, RobotFileParser] = {}

    # ── Public API ───────────────────────────────────────────────

    async def fetch(self, url: str) -> Optional[CrawledPage]:
        """Fetch a single page with all guardrails applied."""
        if not self._allowed(url):
            logger.info("robots.txt disallows %s", url)
            return None
        host = urlparse(url).netloc
        await self.rate.wait(host)
        if _HAS_CRAWL4AI:
            page = await self._fetch_crawl4ai(url)
            if page is not None:
                return page
        if _HAS_HTTPX:
            return await self._fetch_httpx(url)
        logger.warning("No HTTP backend available (need crawl4ai or httpx)")
        return None

    async def fetch_many(self, urls: List[str]) -> List[CrawledPage]:
        """
        Fetch a list of URLs sequentially (polite) respecting rate limits.
        Bounded by self.max_pages.
        """
        out: List[CrawledPage] = []
        for url in urls[: self.max_pages]:
            try:
                page = await self.fetch(url)
                if page:
                    out.append(page)
            except Exception as e:  # noqa: BLE001
                logger.warning("fetch failed for %s: %s", url, e)
        return out

    # ── crawl4ai backend ─────────────────────────────────────────

    async def _fetch_crawl4ai(self, url: str) -> Optional[CrawledPage]:
        try:
            async with AsyncWebCrawler(verbose=False) as crawler:
                run_config = CrawlerRunConfig(
                    word_count_threshold=20,
                    page_timeout=int(REQUEST_TIMEOUT_S * 1000),
                    user_agent=USER_AGENT,
                )
                result = await crawler.arun(url=url, config=run_config)
                if not result or not getattr(result, "success", False):
                    return None
                text = (
                    getattr(result, "markdown", None)
                    or getattr(result, "cleaned_html", None)
                    or ""
                )
                html = getattr(result, "html", "") or ""
                # Extract outbound links — crawl4ai surfaces these on result.links
                links_info = getattr(result, "links", None) or {}
                internal = [l.get("href") for l in (links_info.get("internal") or [])]
                external = [l.get("href") for l in (links_info.get("external") or [])]
                all_links = [l for l in (internal + external) if l]
                return CrawledPage(
                    url=url,
                    title=getattr(result, "title", "") or "",
                    text=str(text),
                    html=html,
                    links=all_links,
                    status=200,
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("crawl4ai failed for %s: %s", url, e)
            return None

    # ── httpx fallback ───────────────────────────────────────────

    async def _fetch_httpx(self, url: str) -> Optional[CrawledPage]:
        if not _HAS_HTTPX:
            return None
        try:
            async with httpx.AsyncClient(
                timeout=REQUEST_TIMEOUT_S,
                follow_redirects=True,
                headers={"User-Agent": USER_AGENT},
            ) as client:
                resp = await client.get(url)
                if resp.status_code >= 400:
                    return None
                html = resp.text
                title, text, links = _html_to_text(html, base=url)
                return CrawledPage(
                    url=url,
                    title=title,
                    text=text,
                    html=html,
                    links=links,
                    status=resp.status_code,
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("httpx fetch failed for %s: %s", url, e)
            return None

    # ── robots.txt ───────────────────────────────────────────────

    def _allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        host = f"{parsed.scheme}://{parsed.netloc}"
        rp = self._robots_cache.get(host)
        if rp is None:
            rp = RobotFileParser()
            rp.set_url(urljoin(host, "/robots.txt"))
            try:
                rp.read()
            except Exception:  # noqa: BLE001
                # If robots.txt is unreachable, default to allowed
                rp = None  # type: ignore[assignment]
            self._robots_cache[host] = rp  # type: ignore[assignment]
        if rp is None:
            return True
        try:
            return rp.can_fetch(USER_AGENT, url)
        except Exception:  # noqa: BLE001
            return True


# ── httpx HTML → text fallback ──────────────────────────────────────


def _html_to_text(html: str, base: str = "") -> tuple[str, str, List[str]]:
    """
    Minimal HTML → (title, text, links) extractor used only when
    crawl4ai is not installed. Not as good as crawl4ai's markdownify
    but produces workable input for the LLM extractor.
    """
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:  # noqa: BLE001
        # Last resort: strip tags with regex. Crude but functional.
        import re
        title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        title = (title_match.group(1).strip() if title_match else "")[:200]
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        hrefs = re.findall(r'href="([^"]+)"', html)
        links = [urljoin(base, h) for h in hrefs] if base else hrefs
        return title, text, links

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else "")[:200]
    text = " ".join(soup.get_text(" ").split())
    links: List[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if base:
            href = urljoin(base, href)
        links.append(href)
    return title, text, links
