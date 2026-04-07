"""
ACM Digital Library adapter for the OSSR academic ingestion pipeline.

Uses the ACM DL open search endpoint to retrieve paper metadata.
Rate limited to 1 request/second to respect robots.txt.
"""

import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

import requests

from ....models.research import AcademicSource
from ..pipeline import AcademicSourceAdapter, PaperMetadata

logger = logging.getLogger(__name__)


class ACMSource(AcademicSourceAdapter):
    """
    ACM Digital Library adapter.

    Uses the ACM DL open search API at https://dl.acm.org/action/doSearch
    to discover papers, then extracts metadata from the returned results.
    """

    SEARCH_URL = "https://dl.acm.org/action/doSearch"
    DOI_BASE = "https://dl.acm.org/doi/"
    MIN_REQUEST_INTERVAL = 1.0  # seconds between requests

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "OSSR/1.0 (academic research; mailto:research@opensens.io)",
            "Accept": "application/json",
        })
        self._last_request_time = 0.0

    def _rate_limit(self):
        """Enforce minimum interval between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def search(
        self,
        query: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 50,
    ) -> List[PaperMetadata]:
        """
        Search ACM Digital Library for papers matching the query.

        Uses the doSearch endpoint with JSON response format.
        Handles pagination via offset/pageSize parameters.
        """
        results: List[PaperMetadata] = []
        page_size = min(max_results, 20)
        offset = 0

        while len(results) < max_results:
            self._rate_limit()

            params: Dict[str, Any] = {
                "AllField": query,
                "pageSize": page_size,
                "startPage": offset // page_size,
                "sortBy": "relevancy",
            }

            # Apply date filters if provided
            if date_from:
                params["AfterYear"] = date_from[:4]
                params["AfterMonth"] = date_from[5:7] if len(date_from) >= 7 else "01"
            if date_to:
                params["BeforeYear"] = date_to[:4]
                params["BeforeMonth"] = date_to[5:7] if len(date_to) >= 7 else "12"

            try:
                resp = self.session.get(
                    self.SEARCH_URL,
                    params=params,
                    timeout=30,
                    headers={"Accept": "application/json"},
                )

                if resp.status_code == 429:
                    logger.warning("ACM DL rate limit hit -- backing off 5s")
                    time.sleep(5)
                    continue

                if resp.status_code == 403:
                    logger.warning("ACM DL returned 403 Forbidden -- stopping")
                    break

                resp.raise_for_status()

                # ACM returns HTML by default; attempt JSON parse, fallback to
                # scraping essential metadata from the HTML response.
                try:
                    data = resp.json()
                except ValueError:
                    # HTML response -- extract metadata from structured HTML
                    papers = self._parse_html_results(resp.text, max_results - len(results))
                    results.extend(papers)
                    if not papers:
                        break
                    offset += page_size
                    continue

                # JSON path: parse items from the response
                items = data.get("items", data.get("results", []))
                if not items:
                    break

                for item in items:
                    paper = self._parse_json_item(item)
                    if paper:
                        results.append(paper)
                    if len(results) >= max_results:
                        break

                # Check if we've exhausted results
                total = data.get("totalResults", data.get("total", 0))
                offset += page_size
                if offset >= total or not items:
                    break

            except requests.exceptions.Timeout:
                logger.warning("ACM DL request timed out at offset %d", offset)
                break
            except Exception as exc:
                logger.error("ACM DL API error: %s", exc)
                break

        logger.info("ACM DL: fetched %d papers for '%s'", len(results), query[:50])
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        """Get a single paper by DOI from ACM DL."""
        self._rate_limit()
        try:
            url = f"{self.DOI_BASE}{identifier}"
            resp = self.session.get(
                url,
                timeout=30,
                headers={"Accept": "application/json"},
            )
            if resp.status_code == 404:
                return None
            resp.raise_for_status()

            try:
                data = resp.json()
                return self._parse_json_item(data)
            except ValueError:
                return None

        except Exception as exc:
            logger.error("ACM DL get_paper error for '%s': %s", identifier, exc)
        return None

    def get_citations(self, doi: str) -> List[str]:
        """
        ACM DL does not expose a free citation API.
        Returns empty list; use Semantic Scholar for citation data.
        """
        return []

    @staticmethod
    def _parse_json_item(item: Dict[str, Any]) -> Optional[PaperMetadata]:
        """Parse a JSON item from the ACM search response into PaperMetadata."""
        doi = item.get("doi", item.get("DOI", ""))
        title = item.get("title", "").strip()
        if not title:
            return None

        # Authors
        authors = []
        author_list = item.get("authors", item.get("author", []))
        if isinstance(author_list, list):
            for a in author_list:
                if isinstance(a, dict):
                    name = a.get("name", a.get("given", "") + " " + a.get("family", ""))
                    authors.append({
                        "name": name.strip(),
                        "affiliation": a.get("affiliation", a.get("institution", "")),
                    })
                elif isinstance(a, str):
                    authors.append({"name": a, "affiliation": ""})

        # Publication date
        pub_date = item.get("publicationDate", item.get("published", ""))
        if not pub_date:
            year = item.get("year", item.get("publicationYear", ""))
            pub_date = f"{year}-01-01" if year else ""

        # Keywords
        keywords = item.get("keywords", [])
        if isinstance(keywords, dict):
            # ACM sometimes nests keywords under categories
            flat_kw = []
            for kw_list in keywords.values():
                if isinstance(kw_list, list):
                    flat_kw.extend(kw_list)
            keywords = flat_kw

        # Generate fallback DOI if missing
        if not doi:
            acm_id = item.get("id", item.get("articleId", uuid.uuid4().hex[:12]))
            doi = f"acm:{acm_id}"

        abstract = item.get("abstract", "")
        # Clean HTML tags from abstract
        if abstract:
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        return PaperMetadata(
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors,
            publication_date=pub_date,
            source=AcademicSource.ACM,
            keywords=keywords if isinstance(keywords, list) else [],
            citation_count=int(item.get("citationCount", item.get("citations", 0)) or 0),
            full_text_url=item.get("url", item.get("fullTextUrl", "")),
            metadata={
                "venue": item.get("venue", item.get("publicationName", "")),
                "content_type": item.get("type", item.get("contentType", "")),
                "acm_id": item.get("id", ""),
            },
        )

    @staticmethod
    def _parse_html_results(html: str, max_items: int) -> List[PaperMetadata]:
        """
        Fallback parser: extract paper metadata from ACM DL HTML search results.
        This handles the case where ACM returns HTML instead of JSON.
        """
        papers: List[PaperMetadata] = []

        # Extract DOI links from search result items
        doi_pattern = re.compile(r'href="/doi/(10\.\d{4,}/[^\s"]+)"')
        title_pattern = re.compile(
            r'class="hlFld-Title"[^>]*>.*?<a[^>]*href="/doi/[^"]*"[^>]*>(.*?)</a>',
            re.DOTALL,
        )

        doi_matches = doi_pattern.findall(html)
        title_matches = title_pattern.findall(html)

        for i, doi in enumerate(doi_matches[:max_items]):
            title = ""
            if i < len(title_matches):
                title = re.sub(r"<[^>]+>", "", title_matches[i]).strip()

            if not title:
                continue

            papers.append(
                PaperMetadata(
                    doi=doi,
                    title=title,
                    abstract="",
                    authors=[],
                    publication_date="",
                    source=AcademicSource.ACM,
                    keywords=[],
                    citation_count=0,
                    full_text_url=f"https://dl.acm.org/doi/{doi}",
                    metadata={"parsed_from": "html_fallback"},
                )
            )

        return papers
