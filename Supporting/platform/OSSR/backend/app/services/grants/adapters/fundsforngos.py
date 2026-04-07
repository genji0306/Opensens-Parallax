"""
FundsforNGOs adapter for the Grant Hunt crawler.

FundsforNGOs (www2.fundsforngos.org) is a hub site that lists grants
across many categories. Each listing page contains links to individual
grant write-up posts. Each post in turn contains an outbound link to
the real funder page.

This adapter enumerates a predefined set of category/tag pages and yields
all candidate grant post URLs found within them, with pagination support.

Usage:
    adapter = FundsforNGOsAdapter(crawler)
    urls = await adapter.enumerate_candidates(max_pages_per_tag=3)
"""

from __future__ import annotations

import logging
from typing import List
from urllib.parse import urlparse

from ..crawler import GrantCrawler

logger = logging.getLogger(__name__)


# ── Tag pages to crawl ───────────────────────────────────────────────

TAG_PAGES: List[str] = [
    "https://www2.fundsforngos.org/tag/startups/",
    "https://www2.fundsforngos.org/tag/researchers/",
    "https://www2.fundsforngos.org/tag/asia/",
    "https://www2.fundsforngos.org/tag/innovation/",
    "https://www2.fundsforngos.org/tag/climate/",
    "https://www2.fundsforngos.org/tag/artificial-intelligence/",
    "https://www2.fundsforngos.org/tag/education/",
]

FUNDSFORNGOS_HOST = "www2.fundsforngos.org"

import re

_GRANT_HINT_RE = re.compile(
    r"(grant|funding|call|tender|program[me]?|award|scheme|opportunity|rfp|rfa|fellowship|prize)",
    re.IGNORECASE,
)

_EXCLUDE_RE = re.compile(
    r"(login|register|subscribe|privacy|terms|sitemap|contact|about|#comment|/author/|/wp-admin/)",
    re.IGNORECASE,
)


class FundsforNGOsAdapter:
    """
    Enumerates grant candidate URLs from FundsforNGOs tag pages.

    For each tag page, fetches up to max_pages_per_tag paginated listing
    pages and collects all post URLs that match grant-hint patterns.
    """

    def __init__(self, crawler: GrantCrawler) -> None:
        self.crawler = crawler

    async def enumerate_candidates(
        self,
        tag_pages: List[str] = None,
        max_pages_per_tag: int = 3,
    ) -> List[str]:
        """
        Enumerate all candidate grant post URLs from the configured tag pages.

        Args:
            tag_pages: Override the default TAG_PAGES list.
            max_pages_per_tag: Maximum pagination depth per tag page.

        Returns:
            Deduplicated list of post URLs found across all tag pages.
        """
        if tag_pages is None:
            tag_pages = TAG_PAGES

        all_candidates: List[str] = []
        seen: set[str] = set()

        for tag_url in tag_pages:
            logger.info("FundsforNGOs adapter: crawling tag %s", tag_url)
            try:
                pages = await self.crawler.paginate_listing(
                    tag_url, max_pages=max_pages_per_tag
                )
                for page in pages:
                    candidates = self._extract_post_urls(tag_url, page.links)
                    for url in candidates:
                        if url not in seen:
                            seen.add(url)
                            all_candidates.append(url)
            except Exception as e:  # noqa: BLE001
                logger.warning("FundsforNGOs adapter failed for %s: %s", tag_url, e)

        logger.info(
            "FundsforNGOs adapter: found %d candidate URLs across %d tag pages",
            len(all_candidates),
            len(tag_pages),
        )
        return all_candidates

    def _extract_post_urls(self, tag_url: str, links: List[str]) -> List[str]:
        """
        Filter a list of links to those that look like FundsforNGOs grant posts.

        Keeps same-host links that:
        - Contain a grant-hint keyword in the path
        - Have a path depth ≥ 2 (e.g. /category/title/ not just /tag/)
        - Are not admin/nav/utility pages
        """
        out: List[str] = []
        for href in links:
            if not href:
                continue
            if _EXCLUDE_RE.search(href):
                continue
            parsed = urlparse(href)
            if not parsed.scheme.startswith("http"):
                continue
            if parsed.netloc != FUNDSFORNGOS_HOST:
                continue
            if parsed.path.count("/") < 2:
                continue
            if _GRANT_HINT_RE.search(parsed.path):
                out.append(href)
        return out

    async def follow_outbound_links(self, post_urls: List[str]) -> List[str]:
        """
        For each FundsforNGOs post URL, fetch the page and extract the primary
        outbound link to the real funder page. Returns a list of funder URLs.

        Each post typically has one prominent outbound link labelled "Apply Now"
        or "More Information". We take the first outbound link that matches grant
        hint patterns.
        """
        funder_urls: List[str] = []
        for post_url in post_urls:
            try:
                page = await self.crawler.fetch(post_url)
                if not page:
                    continue
                outbound = [
                    link for link in page.links
                    if link
                    and FUNDSFORNGOS_HOST not in link
                    and _GRANT_HINT_RE.search(link)
                    and link.startswith("http")
                ]
                if outbound:
                    funder_urls.append(outbound[0])
            except Exception as e:  # noqa: BLE001
                logger.warning("FundsforNGOs outbound follow failed for %s: %s", post_url, e)
        return funder_urls
