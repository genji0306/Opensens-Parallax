"""
Grant crawler.

Tiered fetcher cascade (v2.1 — Scrapling integration):

    1. Scrapling ``Fetcher``        (fast path: TLS-fingerprint HTTP, HTTP/3)
    2. Scrapling ``StealthyFetcher`` (Cloudflare Turnstile bypass, stealth browser)
    3. Scrapling ``DynamicFetcher``  (full Playwright for JS-heavy portals)
    4. crawl4ai ``AsyncWebCrawler``  (legacy fallback, markdownify)
    5. httpx + BeautifulSoup         (last-resort minimal fallback)

The cascade is opt-in per source via ``metadata.stealth_level``:

    "fast"     → tries the cheap HTTP path only (default, majority of sources)
    "stealth"  → skips fast path, goes straight to stealth browser (grants.gov,
                 CORDIS, Horizon Europe — known Cloudflare/anti-bot walls)
    "dynamic"  → full JS rendering (for portals that only populate via XHR)

Why Scrapling over crawl4ai/httpx?
    - Tiered costs: HTTP-level fetch for static pages, browser only when needed.
    - TLS-fingerprint impersonation (Chrome/Firefox/Safari) defeats naive WAFs.
    - Adaptive selectors (``adaptive=True``) auto-relocate elements when funder
      sites redesign — we use this to extract a stable "call card" block per
      source kind without having to patch the selector each redesign.
    - Single dependency for HTTP + browser + parser, replacing the
      crawl4ai+Playwright+BS4 glue stack.

Two-stage crawl:
    1. Fetch the listing page of a source and extract candidate call URLs.
    2. For each candidate, fetch the target page and return cleaned text.

Additional capabilities (v2):
    - Sitemap-aware crawling: /sitemap.xml + /sitemap_index.xml probe first.
    - Pagination traversal: ?page=N and /page/N/ up to ``max_pages``.
    - Incremental crawl cache: skip pages whose content hash is unchanged.
    - Adaptive extraction: per-source CSS/XPath hints (crawler_hints) so new
      adapters plug in with zero parser changes.

Guardrails:
    - Polite rate limiting (min interval per host)
    - Max pages per crawl
    - robots.txt respected across every backend
    - All network calls wrapped in timeouts
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

# Try to import Scrapling — the primary backend (v2.1+).
# https://github.com/D4Vinci/Scrapling — tiered HTTP/stealth/dynamic fetch
# with TLS-fingerprint impersonation and adaptive element relocation.
try:  # pragma: no cover - import guard
    from scrapling.fetchers import Fetcher as _ScraplingFetcher  # type: ignore
    _HAS_SCRAPLING_FAST = True
except Exception:  # noqa: BLE001
    _ScraplingFetcher = None  # type: ignore
    _HAS_SCRAPLING_FAST = False

try:  # pragma: no cover - import guard
    from scrapling.fetchers import StealthyFetcher as _ScraplingStealthy  # type: ignore
    _HAS_SCRAPLING_STEALTH = True
except Exception:  # noqa: BLE001
    _ScraplingStealthy = None  # type: ignore
    _HAS_SCRAPLING_STEALTH = False

try:  # pragma: no cover - import guard
    from scrapling.fetchers import DynamicFetcher as _ScraplingDynamic  # type: ignore
    _HAS_SCRAPLING_DYNAMIC = True
except Exception:  # noqa: BLE001
    _ScraplingDynamic = None  # type: ignore
    _HAS_SCRAPLING_DYNAMIC = False

_HAS_SCRAPLING = _HAS_SCRAPLING_FAST or _HAS_SCRAPLING_STEALTH or _HAS_SCRAPLING_DYNAMIC

# Legacy fallback — crawl4ai (v0.1 backend). Still used when Scrapling is
# unavailable so minimal environments keep working.
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


_VALID_STEALTH = {"fast", "stealth", "dynamic"}


class GrantCrawler:
    """
    Tiered async crawler (Scrapling → crawl4ai → httpx).

    Supports:
    - Sitemap-aware discovery (A.2)
    - Pagination traversal up to max_pages (A.3)
    - Incremental content-hash cache to skip unchanged pages (A.6)
    - Per-source stealth escalation (v2.1 Scrapling integration)

    ``stealth_level`` chooses the cascade entry point:

        "fast"     → Scrapling Fetcher (TLS impersonation) → crawl4ai → httpx
        "stealth"  → Scrapling StealthyFetcher → DynamicFetcher → crawl4ai → httpx
        "dynamic"  → Scrapling DynamicFetcher → StealthyFetcher → crawl4ai → httpx

    Callers can pass ``stealth_level`` via :meth:`fetch` to override per request
    (e.g. discovery.py does this when a source's metadata requests stealth).

    Call :meth:`crawl` from sync code via asyncio.run() or from an async context.
    """

    def __init__(
        self,
        max_pages: int = DEFAULT_MAX_PAGES,
        interval_s: float = POLITE_INTERVAL_S,
        stealth_level: str = "fast",
    ) -> None:
        self.max_pages = max_pages
        self.rate = HostRateLimiter(interval_s)
        self._robots_cache: dict[str, RobotFileParser] = {}
        if stealth_level not in _VALID_STEALTH:
            stealth_level = "fast"
        self.stealth_level = stealth_level

    # ── Public API ───────────────────────────────────────────────

    async def fetch(
        self,
        url: str,
        skip_cache: bool = False,
        stealth_level: Optional[str] = None,
    ) -> Optional[CrawledPage]:
        """
        Fetch a single page with all guardrails applied.

        ``stealth_level`` overrides the per-instance default and picks where
        the cascade starts. ``fast`` is the cheap path and should handle
        ~80% of grant sources. ``stealth`` escalates immediately for sources
        with Cloudflare/anti-bot walls. ``dynamic`` forces full JS rendering.
        """
        if not self._allowed(url):
            logger.info("robots.txt disallows %s", url)
            return None
        host = urlparse(url).netloc
        await self.rate.wait(host)

        level = stealth_level or self.stealth_level
        if level not in _VALID_STEALTH:
            level = "fast"

        page = await self._cascade_fetch(url, level)
        return page

    async def _cascade_fetch(self, url: str, level: str) -> Optional[CrawledPage]:
        """
        Walk the backend cascade starting at the requested stealth level.

        Each rung returns the first non-None page. Exceptions in one rung are
        logged and the cascade continues to the next.
        """
        # Build the ordered list of rungs for this level. Scrapling rungs
        # are first, then legacy crawl4ai, then httpx as last resort.
        rungs: List[tuple[str, callable]] = []

        if level == "fast":
            if _HAS_SCRAPLING_FAST:
                rungs.append(("scrapling-fast", self._fetch_scrapling_fast))
            if _HAS_SCRAPLING_STEALTH:
                rungs.append(("scrapling-stealth", self._fetch_scrapling_stealth))
        elif level == "stealth":
            if _HAS_SCRAPLING_STEALTH:
                rungs.append(("scrapling-stealth", self._fetch_scrapling_stealth))
            if _HAS_SCRAPLING_DYNAMIC:
                rungs.append(("scrapling-dynamic", self._fetch_scrapling_dynamic))
        elif level == "dynamic":
            if _HAS_SCRAPLING_DYNAMIC:
                rungs.append(("scrapling-dynamic", self._fetch_scrapling_dynamic))
            if _HAS_SCRAPLING_STEALTH:
                rungs.append(("scrapling-stealth", self._fetch_scrapling_stealth))

        # Legacy fallbacks always at the bottom of the cascade.
        if _HAS_CRAWL4AI:
            rungs.append(("crawl4ai", self._fetch_crawl4ai))
        if _HAS_HTTPX:
            rungs.append(("httpx", self._fetch_httpx))

        if not rungs:
            logger.warning("No HTTP backend available — install scrapling, crawl4ai, or httpx")
            return None

        for name, impl in rungs:
            try:
                page = await impl(url)
            except Exception as e:  # noqa: BLE001
                logger.info("%s rung failed for %s: %s", name, url, e)
                continue
            if page is not None:
                logger.debug("%s rung produced page for %s", name, url)
                return page
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

    async def fetch_many(
        self,
        urls: List[str],
        concurrency: int = 4,
    ) -> List[CrawledPage]:
        """
        Fetch a list of URLs concurrently with a bounded semaphore.

        Concurrency is capped by ``concurrency`` (default 4). Per-host
        politeness is still enforced by :class:`HostRateLimiter`, so
        parallel requests to the *same* host are serialized by the
        rate gate while requests to *different* hosts run in parallel.
        This gives us the throughput of concurrent I/O without
        hammering a single funder site.

        Failures are logged and do not block sibling fetches. Results
        are returned in original URL order (failures skipped).

        Bounded by ``self.max_pages``.
        """
        bounded = urls[: self.max_pages]
        if not bounded:
            return []

        concurrency = max(1, int(concurrency))
        sem = asyncio.Semaphore(concurrency)

        async def _one(u: str, idx: int) -> tuple[int, Optional[CrawledPage]]:
            async with sem:
                try:
                    return idx, await self.fetch(u)
                except Exception as e:  # noqa: BLE001
                    logger.warning("fetch failed for %s: %s", u, e)
                    return idx, None

        tasks = [_one(u, i) for i, u in enumerate(bounded)]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Preserve input order and drop failures.
        results.sort(key=lambda r: r[0])
        return [page for _, page in results if page is not None]

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

    # ── Scrapling backends ───────────────────────────────────────

    async def _fetch_scrapling_fast(self, url: str) -> Optional[CrawledPage]:
        """
        Fast path: Scrapling ``Fetcher`` — HTTP-level request with TLS
        fingerprint impersonation. Handles most static grant pages.

        Scrapling's fetchers are synchronous, so we offload to a worker
        thread to keep our async call sites non-blocking. This costs one
        thread per fetch but we're rate-limited anyway.
        """
        if not _HAS_SCRAPLING_FAST or _ScraplingFetcher is None:
            return None

        def _sync() -> Optional[CrawledPage]:
            try:
                resp = _ScraplingFetcher.get(
                    url,
                    timeout=REQUEST_TIMEOUT_S,
                    follow_redirects=True,
                    impersonate="chrome",
                    stealthy_headers=True,
                )
            except TypeError:
                # Older Scrapling versions used a different kwarg surface.
                try:
                    resp = _ScraplingFetcher.get(url)  # type: ignore[call-arg]
                except Exception as e:  # noqa: BLE001
                    logger.info("scrapling.Fetcher.get failed for %s: %s", url, e)
                    return None
            except Exception as e:  # noqa: BLE001
                logger.info("scrapling.Fetcher.get failed for %s: %s", url, e)
                return None
            return _scrapling_response_to_page(resp, url)

        return await asyncio.to_thread(_sync)

    async def _fetch_scrapling_stealth(self, url: str) -> Optional[CrawledPage]:
        """
        Stealth browser path via Scrapling ``StealthyFetcher``.

        Bypasses Cloudflare Turnstile and anti-bot JS challenges. Slower
        than the fast path (~3-8s per fetch) because it launches a stealth
        browser, but still cheaper than a full Playwright render.
        """
        if not _HAS_SCRAPLING_STEALTH or _ScraplingStealthy is None:
            return None

        def _sync() -> Optional[CrawledPage]:
            try:
                resp = _ScraplingStealthy.fetch(
                    url,
                    timeout=REQUEST_TIMEOUT_S,
                    headless=True,
                    humanize=True,
                    solve_cloudflare=True,
                )
            except TypeError:
                try:
                    resp = _ScraplingStealthy.fetch(url)  # type: ignore[call-arg]
                except Exception as e:  # noqa: BLE001
                    logger.info("scrapling.StealthyFetcher.fetch failed for %s: %s", url, e)
                    return None
            except Exception as e:  # noqa: BLE001
                logger.info("scrapling.StealthyFetcher.fetch failed for %s: %s", url, e)
                return None
            return _scrapling_response_to_page(resp, url)

        return await asyncio.to_thread(_sync)

    async def _fetch_scrapling_dynamic(self, url: str) -> Optional[CrawledPage]:
        """
        Full JS rendering via Scrapling ``DynamicFetcher`` (Playwright backend).

        Reserved for portals that render all content client-side via XHR
        (Horizon Europe funding portal, the EU SEDIA app, etc.). Slowest
        rung — prefer stealth when it's enough.
        """
        if not _HAS_SCRAPLING_DYNAMIC or _ScraplingDynamic is None:
            return None

        def _sync() -> Optional[CrawledPage]:
            try:
                resp = _ScraplingDynamic.fetch(
                    url,
                    timeout=REQUEST_TIMEOUT_S,
                    headless=True,
                    network_idle=True,
                )
            except TypeError:
                try:
                    resp = _ScraplingDynamic.fetch(url)  # type: ignore[call-arg]
                except Exception as e:  # noqa: BLE001
                    logger.info("scrapling.DynamicFetcher.fetch failed for %s: %s", url, e)
                    return None
            except Exception as e:  # noqa: BLE001
                logger.info("scrapling.DynamicFetcher.fetch failed for %s: %s", url, e)
                return None
            return _scrapling_response_to_page(resp, url)

        return await asyncio.to_thread(_sync)

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


# ── Scrapling response → CrawledPage adapter ────────────────────────


def _scrapling_response_to_page(resp: object, url: str) -> Optional[CrawledPage]:
    """
    Convert a Scrapling response (``Response`` / ``Adaptor`` object) into a
    ``CrawledPage``. Scrapling's API surface has shifted across releases, so
    we use duck typing: anything exposing ``.html_content``/``.body``/``.text``
    plus ``.css()`` or ``.urljoin()`` is treated as a page.

    The critical data we need downstream is:
        - ``text``: plain text for the LLM extractor
        - ``html``: raw HTML for sitemap/XML parsing
        - ``links``: outbound absolute URLs for link selectors
        - ``title``: first ``<title>`` or ``h1``
        - ``status``: HTTP status code (default 200)

    When the Scrapling object exposes an adaptive parser, we use it — this
    is how the v2.1 crawler gets "adaptive selectors survive redesigns" for
    free. Otherwise we route through ``_html_to_text`` for the plain path.
    """
    if resp is None:
        return None

    # Status code (some responses expose .status, others .status_code, some both).
    status = 200
    for attr in ("status_code", "status"):
        value = getattr(resp, attr, None)
        if isinstance(value, int):
            status = value
            break
    if status >= 400:
        return None

    # Raw HTML body — try several known attribute names in priority order.
    html = ""
    for attr in ("html_content", "body", "content", "text", "html"):
        value = getattr(resp, attr, None)
        if isinstance(value, bytes):
            try:
                html = value.decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                html = ""
            if html:
                break
        if isinstance(value, str) and value.strip():
            html = value
            break

    if not html:
        return None

    # Prefer Scrapling's adaptive parser when available — it gives us a
    # stable body extraction even when the page redesigns.
    title = ""
    text = ""
    links: List[str] = []

    css = getattr(resp, "css", None)
    if callable(css):
        try:
            title_node = css("title", auto_match=True)
        except TypeError:
            title_node = None
        except Exception:  # noqa: BLE001
            title_node = None
        if title_node is not None:
            title_text = getattr(title_node, "text", None)
            if callable(title_text):
                try:
                    title = str(title_text()).strip()
                except Exception:  # noqa: BLE001
                    title = ""
            elif title_text is not None:
                title = str(title_text).strip()

        try:
            main_text_node = css("main, article, body", auto_match=True)
        except TypeError:
            main_text_node = None
        except Exception:  # noqa: BLE001
            main_text_node = None
        if main_text_node is not None:
            mt = getattr(main_text_node, "text", None)
            if callable(mt):
                try:
                    text = str(mt()).strip()
                except Exception:  # noqa: BLE001
                    text = ""
            elif mt is not None:
                text = str(mt).strip()

    # Fall back to our own HTML → text extractor when Scrapling didn't
    # give us usable strings. This also populates ``links``.
    if not text or not links:
        alt_title, alt_text, alt_links = _html_to_text(html, base=url)
        if not title:
            title = alt_title
        if not text:
            text = alt_text
        links = alt_links

    return CrawledPage(
        url=url,
        title=title[:300],
        text=text,
        html=html,
        links=links,
        status=status,
    )


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
        # Accept single or double quotes around href values.
        hrefs = _re.findall(r"""href\s*=\s*['"]([^'"]+)['"]""", html)
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
