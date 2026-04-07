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

Additional capabilities (v2):
    - Sitemap-aware crawling: checks /sitemap.xml and /sitemap_index.xml
      before falling back to listing-page link extraction.
    - Pagination traversal: detects ?page=N and /page/N/ patterns and
      follows up to max_pages pages.
    - Incremental crawl cache: skips pages whose content hash hasn't
      changed since last crawl (checked via grant_crawl_cache table).

Guardrails:
    - polite rate limiting (min interval between requests per host)
    - max pages per crawl
    - robots.txt respected when crawl4ai is available (it honours it by
      default); fallback httpx path also checks robots.txt
    - all network calls wrapped in timeouts
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse, urlencode, parse_qs, urlunparse
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

# Grant-hint patterns for sitemap URL filtering
_GRANT_HINT_SITEMAP_RE = re.compile(
    r"(grant|funding|call|tender|program[me]?|award|scheme|opportunity|rfp|rfa|foa|fellowship|prize)",
    re.IGNORECASE,
)


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

    Supports:
    - Sitemap-aware discovery (A.2)
    - Pagination traversal up to max_pages (A.3)
    - Incremental content-hash cache to skip unchanged pages (A.6)

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

    async def fetch(self, url: str, skip_cache: bool = False) -> Optional[CrawledPage]:
        """Fetch a single page with all guardrails applied."""
        if not self._allowed(url):
            logger.info("robots.txt disallows %s", url)
            return None
        host = urlparse(url).netloc
        await self.rate.wait(host)

        # Incremental cache check
        if not skip_cache:
            cached_hash = _get_crawl_cache(url)
            # We'll compare after fetching; we can't skip before we have text.
            # The check happens after fetching in fetch_with_cache_check below.

        if _HAS_CRAWL4AI:
            page = await self._fetch_crawl4ai(url)
            if page is not None:
                return page
        if _HAS_HTTPX:
            return await self._fetch_httpx(url)
        logger.warning("No HTTP backend available (need crawl4ai or httpx)")
        return None

    async def fetch_with_cache_skip(self, url: str) -> Optional[CrawledPage]:
        """
        Fetch a page but skip it (return None) if content hasn't changed
        since last crawl, according to grant_crawl_cache.
        """
        if not self._allowed(url):
            return None
        host = urlparse(url).netloc
        await self.rate.wait(host)

        page = None
        if _HAS_CRAWL4AI:
            page = await self._fetch_crawl4ai(url)
        if page is None and _HAS_HTTPX:
            page = await self._fetch_httpx(url)

        if page is None:
            return None

        new_hash = _content_hash(page.text)
        old_hash = _get_crawl_cache(url)
        if old_hash and old_hash == new_hash:
            logger.debug("Cache hit (unchanged): %s", url)
            return None  # Skip — content unchanged

        # Update cache
        _update_crawl_cache(url, new_hash)
        return page

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

    async def discover_sitemap_urls(self, base_url: str) -> List[str]:
        """
        Try to discover grant-related URLs from the site's sitemap.

        Checks /sitemap_index.xml first, then /sitemap.xml. Parses the XML
        to extract <loc> URLs that match grant-hint patterns. Returns the
        filtered list, or an empty list if no sitemap is found.
        """
        parsed = urlparse(base_url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        candidates = [
            urljoin(root, "/sitemap_index.xml"),
            urljoin(root, "/sitemap.xml"),
        ]
        for sitemap_url in candidates:
            urls = await self._parse_sitemap(sitemap_url)
            if urls:
                logger.info("Sitemap found at %s: %d URLs", sitemap_url, len(urls))
                return urls
        logger.debug("No sitemap found for %s", base_url)
        return []

    async def paginate_listing(self, listing_url: str, max_pages: int = 5) -> List[CrawledPage]:
        """
        Fetch listing_url and follow pagination links up to max_pages.

        Detects two pagination patterns:
        - Query param: ?page=N  (increments N)
        - Path segment: /page/N/ (increments N)

        Returns all fetched pages including the first.
        """
        pages: List[CrawledPage] = []
        first = await self.fetch(listing_url)
        if not first:
            return pages
        pages.append(first)

        # Detect pagination style from first page links
        style, base = _detect_pagination_style(listing_url, first.links)
        if style == "none" or not base:
            return pages

        visited: Set[str] = {listing_url, first.url}
        for page_num in range(2, max_pages + 1):
            next_url = _build_page_url(style, base, page_num)
            if not next_url or next_url in visited:
                break
            visited.add(next_url)
            try:
                page = await self.fetch(next_url)
                if not page:
                    break
                pages.append(page)
                # Stop if page has no new links (reached end)
                new_links = [l for l in page.links if l not in visited]
                if not new_links:
                    break
            except Exception as e:  # noqa: BLE001
                logger.warning("Pagination fetch failed for %s: %s", next_url, e)
                break
        return pages

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

    async def _parse_sitemap(self, sitemap_url: str) -> List[str]:
        """
        Fetch a sitemap XML URL and return grant-hint-filtered <loc> URLs.
        Handles sitemap index files recursively (one level deep).
        """
        page = await self._fetch_httpx(sitemap_url)
        if not page or not page.html:
            return []

        xml = page.html
        # Find all <loc> entries
        locs = re.findall(r"<loc>\s*(https?://[^<]+)\s*</loc>", xml)
        if not locs:
            return []

        # Check if this is a sitemap index (contains sub-sitemaps)
        if "<sitemapindex" in xml:
            # Recurse into sub-sitemaps (max 3)
            all_urls: List[str] = []
            for sub_url in locs[:3]:
                sub_urls = await self._parse_sitemap(sub_url.strip())
                all_urls.extend(sub_urls)
            return all_urls

        # Filter to grant-hint URLs
        return [
            loc.strip() for loc in locs
            if _GRANT_HINT_SITEMAP_RE.search(loc)
        ]

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
                rp = None  # type: ignore[assignment]
            self._robots_cache[host] = rp  # type: ignore[assignment]
        if rp is None:
            return True
        try:
            return rp.can_fetch(USER_AGENT, url)
        except Exception:  # noqa: BLE001
            return True


# ── Pagination helpers ───────────────────────────────────────────────


def _detect_pagination_style(listing_url: str, links: List[str]) -> tuple[str, str]:
    """
    Detect which pagination pattern the listing page uses.

    Returns:
        (style, base) where style is "query", "path", or "none"
        and base is the base URL template.
    """
    # Look for ?page=2 or ?p=2
    query_re = re.compile(r"[?&](page|p)=(\d+)", re.IGNORECASE)
    for link in links:
        m = query_re.search(link)
        if m and int(m.group(2)) >= 2:
            # Strip the page param to get base
            base = re.sub(r"([?&])(page|p)=\d+", "", link, flags=re.IGNORECASE)
            base = base.rstrip("?&")
            return ("query", base)

    # Look for /page/2/ or /page/2
    path_re = re.compile(r"(/page/)(\d+)/?")
    for link in links:
        m = path_re.search(link)
        if m and int(m.group(2)) >= 2:
            # Base is everything before /page/N
            base = link[: m.start()]
            return ("path", base.rstrip("/"))

    return ("none", "")


def _build_page_url(style: str, base: str, page_num: int) -> str:
    """Construct the URL for page_num given the detected pagination style."""
    if style == "query":
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}page={page_num}"
    if style == "path":
        return f"{base}/page/{page_num}/"
    return ""


# ── Crawl cache (incremental) ────────────────────────────────────────


def _content_hash(text: str) -> str:
    """SHA-256 hex digest of page text for incremental crawl deduplication."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _get_crawl_cache(url: str) -> Optional[str]:
    """
    Return the stored content hash for a URL, or None if not cached.
    Uses the grant_crawl_cache table.
    """
    try:
        from ...db import get_connection
        row = get_connection().execute(
            "SELECT content_hash FROM grant_crawl_cache WHERE url = ?", (url,)
        ).fetchone()
        return row["content_hash"] if row else None
    except Exception as e:  # noqa: BLE001
        logger.debug("Crawl cache lookup failed for %s: %s", url, e)
        return None


def _update_crawl_cache(url: str, content_hash: str) -> None:
    """Insert or replace the content hash for a crawled URL."""
    try:
        from ...db import get_connection
        from datetime import datetime
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO grant_crawl_cache (url, content_hash, last_seen_at)
               VALUES (?, ?, ?)""",
            (url, content_hash, datetime.now().isoformat()),
        )
        conn.commit()
    except Exception as e:  # noqa: BLE001
        logger.debug("Crawl cache update failed for %s: %s", url, e)


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
        import re as _re
        title_match = _re.search(r"<title>(.*?)</title>", html, _re.IGNORECASE | _re.DOTALL)
        title = (title_match.group(1).strip() if title_match else "")[:200]
        text = _re.sub(r"<[^>]+>", " ", html)
        text = _re.sub(r"\s+", " ", text).strip()
        hrefs = _re.findall(r'href="([^"]+)"', html)
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
