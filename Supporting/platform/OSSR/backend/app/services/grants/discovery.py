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
    save_opportunities(...)

This module is synchronous-friendly: it exposes discover_source() which
wraps the async crawler in asyncio.run() so API handlers stay simple.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import List

from .crawler import CrawledPage, GrantCrawler
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
    """Run a full crawl → extract for one source."""
    result = DiscoveryResult()
    crawler = GrantCrawler(max_pages=max_pages)
    extractor = OpportunityExtractor(model=model)

    # Stage 1: fetch listing
    listing = await crawler.fetch(source.listing_url)
    if not listing:
        result.errors.append(f"listing fetch failed: {source.listing_url}")
        return result
    result.visited += 1

    # Stage 1b: select candidates
    selector = selector_for(source.kind)
    candidates = deduplicate(selector(source.listing_url, listing.links))
    result.candidates = len(candidates)
    if not candidates:
        logger.info("No candidates found on %s", source.listing_url)
        return result

    # Stage 2: fetch each candidate page (one hop; hub-exit candidates
    # are already the funder page for external links, or the post page
    # for same-host fundsforngos posts which we extract from directly).
    pages: List[CrawledPage] = []
    for candidate in candidates[:max_pages]:
        page = await crawler.fetch(candidate.url)
        if page:
            pages.append(page)
            result.visited += 1

    # Stage 2b: for fundsforngos same-host posts, there's an additional
    # hop to the real funder page. We extract from whichever yields a
    # richer signal; the extractor is prompt-driven and handles both.
    follow_up_urls: List[str] = []
    if source.kind == "fundsforngos":
        for page in pages:
            outbound = [
                link for link in page.links
                if link and "fundsforngos.org" not in link
                and _looks_like_call(link)
            ]
            follow_up_urls.extend(outbound[:1])  # take top outbound per post
    if follow_up_urls:
        logger.info("Following %d fundsforngos outbound links", len(follow_up_urls))
        extra = await crawler.fetch_many(follow_up_urls)
        pages.extend(extra)
        result.visited += len(extra)

    # Stage 3: extract structured opportunities
    for page in pages:
        try:
            opp = extractor.extract(page, source_id=source.source_id)
            if opp and opp.title:
                result.opportunities.append(opp)
        except Exception as e:  # noqa: BLE001
            logger.warning("extract failed for %s: %s", page.url, e)
            result.errors.append(f"extract failed: {page.url}")

    # Persist
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
            # If called from an already-running loop, schedule on a new one
            return asyncio.run_coroutine_threadsafe(
                discover_source_async(source, max_pages, model), loop
            ).result()
    except RuntimeError:
        pass
    return asyncio.run(discover_source_async(source, max_pages, model))


def discover_all(sources: List[GrantSource], max_pages_per_source: int = 30, model: str = "") -> List[DiscoveryResult]:
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
