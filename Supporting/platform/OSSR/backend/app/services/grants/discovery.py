"""
Discovery orchestrator.

Combines the crawler + source adapters + LLM extractor to turn a
configured GrantSource into a set of structured GrantOpportunity rows.

Two-stage flow per source:

    fetch(listing_url)
        → adapter.selector picks candidate links
        → for each candidate:
            fetch(candidate) (one extra hop for hub sources like fundsforngos
              if is_hub_exit, because the first candidate is the write-up
              which itself links out to the real funder page; the extractor
              is tolerant of either)
        → extractor.extract_opportunity(page) → GrantOpportunity
    deduplicate_opportunities(results)
    save_opportunities(...)

Additional V2 capabilities:
    - FundsforNGOs sources (kind="fundsforngos") use the FundsforNGOsAdapter
      to enumerate tag pages with pagination, then follow outbound funder
      links for two-stage resolution.
    - Incremental crawl cache: content-unchanged pages are skipped.

This module is synchronous-friendly: it exposes discover_source() which
wraps the async crawler in asyncio.run() so API handlers stay simple.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List

from .adapters.fundsforngos import FundsforNGOsAdapter
from .crawler import CrawledPage, GrantCrawler
from .dedup import deduplicate_opportunities
from .extractor import OpportunityExtractor
from .models import GrantOpportunity, GrantSource
from .sources import LinkCandidate, deduplicate, selector_for  # noqa: F401
from .store import save_opportunities, save_source

logger = logging.getLogger(__name__)


class DiscoveryResult:
    def __init__(self) -> None:
        self.opportunities: List[GrantOpportunity] = []
        self.visited: int = 0
        self.candidates: int = 0
        self.errors: List[str] = []

    def to_dict(self) -> dict:
        return {
            "opportunity_count": len(self.opportunities),
            "visited": self.visited,
            "candidates": self.candidates,
            "errors": self.errors,
        }


async def discover_source_async(
    source: GrantSource,
    max_pages: int = 30,
    model: str = "",
) -> DiscoveryResult:
    """Run a full crawl → extract → dedup for one source."""
    result = DiscoveryResult()

    # Pick up the per-source stealth level from metadata. Sources with known
    # anti-bot walls (grants.gov, CORDIS, Horizon Europe) tag themselves with
    # ``stealth_level: "stealth"`` or ``"dynamic"`` and route through the
    # Scrapling browser rung. Defaults to the cheap HTTP path.
    stealth_level = str((source.metadata or {}).get("stealth_level") or "fast").lower()
    if stealth_level not in ("fast", "stealth", "dynamic"):
        stealth_level = "fast"

    crawler = GrantCrawler(max_pages=max_pages, stealth_level=stealth_level)
    extractor = OpportunityExtractor(model=model)

    pages: List[CrawledPage] = []

    # ── FundsforNGOs: use tag-page adapter ───────────────────────
    if source.kind == "fundsforngos":
        adapter = FundsforNGOsAdapter(crawler)
        meta = source.metadata or {}
        tag_pages = None
        # Single-source override: use the listing_url as the single tag page
        if source.listing_url:
            tag_pages = [source.listing_url]
        post_urls = await adapter.enumerate_candidates(
            tag_pages=tag_pages,
            max_pages_per_tag=3,
        )
        result.candidates = len(post_urls)

        # Fetch all post pages
        post_pages = await crawler.fetch_many(post_urls)
        result.visited += len(post_pages)

        # Two-stage resolution: also fetch outbound funder URLs
        if meta.get("follow_outbound", True):
            funder_urls = await adapter.follow_outbound_links(post_urls)
            extra = await crawler.fetch_many(funder_urls)
            pages.extend(extra)
            result.visited += len(extra)

        pages.extend(post_pages)

    else:
        # ── Standard sources ──────────────────────────────────────

        # Try sitemap discovery first
        sitemap_urls = await crawler.discover_sitemap_urls(source.listing_url)

        if sitemap_urls:
            logger.info(
                "Source %s: using sitemap (%d grant URLs)",
                source.source_id,
                len(sitemap_urls),
            )
            result.candidates = len(sitemap_urls)
            pages = await crawler.fetch_many(sitemap_urls[:max_pages])
            result.visited = len(pages)
        else:
            # Fall back to listing-page link discovery
            listing = await crawler.fetch(source.listing_url)
            if not listing:
                result.errors.append(f"listing fetch failed: {source.listing_url}")
                return result
            result.visited += 1

            selector = selector_for(source.kind)
            candidates = deduplicate(selector(source.listing_url, listing.links))
            result.candidates = len(candidates)

            if not candidates:
                logger.info("No candidates found on %s", source.listing_url)
                return result

            for candidate in candidates[:max_pages]:
                page = await crawler.fetch(candidate.url)
                if page:
                    pages.append(page)
                    result.visited += 1

    # ── Extract structured opportunities ─────────────────────────
    raw_opps: List[GrantOpportunity] = []
    for page in pages:
        try:
            opp = extractor.extract(
                page,
                source_id=source.source_id,
                kind=source.kind or "generic",
            )
            if opp and opp.title:
                raw_opps.append(opp)
        except Exception as e:  # noqa: BLE001
            logger.warning("extract failed for %s: %s", page.url, e)
            result.errors.append(f"extract failed: {page.url}")

    # ── Deduplication ─────────────────────────────────────────────
    result.opportunities = deduplicate_opportunities(raw_opps)

    # ── Persist ──────────────────────────────────────────────────
    save_opportunities(result.opportunities)

    # Mark source crawled
    source.last_crawled_at = datetime.now().isoformat()
    save_source(source)

    return result


def discover_source(source: GrantSource, max_pages: int = 30, model: str = "") -> DiscoveryResult:
    """Synchronous wrapper for API handlers."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():  # pragma: no cover - unlikely in Flask sync handler
            return asyncio.run_coroutine_threadsafe(
                discover_source_async(source, max_pages, model), loop
            ).result()
    except RuntimeError:
        pass
    return asyncio.run(discover_source_async(source, max_pages, model))


def discover_all(
    sources: List[GrantSource],
    max_pages_per_source: int = 30,
    model: str = "",
) -> List[DiscoveryResult]:
    """Run discovery for all enabled sources sequentially."""
    results: List[DiscoveryResult] = []
    for src in sources:
        if not src.enabled:
            continue
        try:
            results.append(discover_source(src, max_pages_per_source, model))
        except Exception as e:  # noqa: BLE001
            logger.exception("discover_source failed for %s: %s", src.source_id, e)
            err = DiscoveryResult()
            err.errors.append(str(e))
            results.append(err)
    return results


def _looks_like_call(url: str) -> bool:
    lowered = url.lower()
    return any(
        kw in lowered
        for kw in (
            "grant", "funding", "call", "tender", "program",
            "award", "scheme", "opportunity", "apply", "rfp",
        )
    )
