"""
Springer Nature adapter for the OSSR academic ingestion pipeline.

Uses the free Springer Nature Metadata API (v2) to retrieve paper metadata.
Requires a SPRINGER_API_KEY environment variable; adapter is a no-op if missing.
API docs: https://dev.springernature.com/docs
Rate limited to 1 request/second.
"""

import logging
import os
import re
import time
import uuid
from typing import Any, Dict, List, Optional

import requests

from ....models.research import AcademicSource
from ..pipeline import AcademicSourceAdapter, PaperMetadata

logger = logging.getLogger(__name__)


class SpringerSource(AcademicSourceAdapter):
    """
    Springer Nature adapter using the free Metadata API v2.

    API endpoint: https://api.springernature.com/meta/v2/json
    Authentication: via api_key query parameter.
    Rate limit: 1 request/second (enforced client-side).
    """

    API_BASE = "https://api.springernature.com/meta/v2/json"
    MIN_REQUEST_INTERVAL = 1.0  # seconds between requests

    def __init__(self):
        self.api_key = os.environ.get("SPRINGER_API_KEY", "")
        if not self.api_key:
            logger.warning(
                "SPRINGER_API_KEY not configured -- Springer Nature adapter disabled"
            )
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
        Search Springer Nature for papers matching the query.

        Uses the Metadata API v2 with pagination via `s` (start) and `p` (pageSize).
        """
        if not self.api_key:
            return []

        results: List[PaperMetadata] = []
        page_size = min(max_results, 25)
        start = 1  # Springer uses 1-based start index

        while len(results) < max_results:
            self._rate_limit()

            # Build the constraint query
            q_parts = [f'keyword:"{query}"']
            if date_from:
                q_parts.append(f"onlinedatefrom:{date_from}")
            if date_to:
                q_parts.append(f"onlinedateto:{date_to}")
            q_string = " ".join(q_parts)

            params: Dict[str, Any] = {
                "q": q_string,
                "api_key": self.api_key,
                "s": start,
                "p": page_size,
            }

            try:
                resp = self.session.get(self.API_BASE, params=params, timeout=30)

                if resp.status_code == 403:
                    logger.warning(
                        "Springer API returned 403 -- check SPRINGER_API_KEY validity"
                    )
                    break

                if resp.status_code == 429:
                    logger.warning("Springer API rate limit hit -- backing off 5s")
                    time.sleep(5)
                    continue

                resp.raise_for_status()
                data = resp.json()

            except requests.exceptions.Timeout:
                logger.warning("Springer API request timed out at start=%d", start)
                break
            except Exception as exc:
                logger.error("Springer API error: %s", exc)
                break

            records = data.get("records", [])
            if not records:
                break

            for record in records:
                paper = self._parse_record(record)
                if paper:
                    results.append(paper)
                if len(results) >= max_results:
                    break

            # Check pagination bounds
            result_info = data.get("result", [{}])
            if isinstance(result_info, list) and result_info:
                result_info = result_info[0]
            total = int(result_info.get("total", 0))

            start += page_size
            if start > total or not records:
                break

        logger.info(
            "Springer Nature: fetched %d papers for '%s'", len(results), query[:50]
        )
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        """Get a single paper by DOI from the Springer Nature API."""
        if not self.api_key:
            return None

        self._rate_limit()
        try:
            params = {
                "q": f'doi:"{identifier}"',
                "api_key": self.api_key,
                "p": 1,
            }
            resp = self.session.get(self.API_BASE, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("records", [])
            if records:
                return self._parse_record(records[0])
        except Exception as exc:
            logger.error("Springer get_paper error for '%s': %s", identifier, exc)
        return None

    def get_citations(self, doi: str) -> List[str]:
        """
        Springer Nature Metadata API does not expose citation data.
        Returns empty list; use Semantic Scholar or OpenAlex for citation graphs.
        """
        return []

    @staticmethod
    def _parse_record(record: Dict[str, Any]) -> Optional[PaperMetadata]:
        """Parse a single record from the Springer Nature API response."""
        title = record.get("title", "").strip()
        if not title:
            return None

        # Clean HTML entities/tags from title
        title = re.sub(r"<[^>]+>", "", title).strip()

        # DOI
        doi = ""
        for url_entry in record.get("url", []):
            if url_entry.get("format") == "" or "doi.org" in url_entry.get("value", ""):
                raw = url_entry.get("value", "")
                # Extract DOI from URL: https://doi.org/10.xxxx/yyyy
                doi_match = re.search(r"(10\.\d{4,}/[^\s]+)", raw)
                if doi_match:
                    doi = doi_match.group(1)
                    break
        if not doi:
            doi = record.get("doi", record.get("identifier", ""))
        if not doi:
            doi = f"springer:{uuid.uuid4().hex[:12]}"

        # Authors / creators
        authors = []
        creators = record.get("creators", [])
        for creator in creators:
            name = creator.get("creator", "")
            if name:
                authors.append({"name": name, "affiliation": ""})

        # Publication date
        pub_date = record.get("publicationDate", record.get("onlineDate", ""))
        if not pub_date:
            year = record.get("publicationYear", "")
            pub_date = f"{year}-01-01" if year else ""

        # Abstract
        abstract = record.get("abstract", "")
        if abstract:
            abstract = re.sub(r"<[^>]+>", "", abstract).strip()

        # Keywords
        keywords = []
        kw_field = record.get("keyword", [])
        if isinstance(kw_field, list):
            keywords = [k.strip() for k in kw_field if isinstance(k, str) and k.strip()]
        elif isinstance(kw_field, str):
            keywords = [k.strip() for k in kw_field.split(",") if k.strip()]

        # Full text URL
        full_text_url = ""
        for url_entry in record.get("url", []):
            fmt = url_entry.get("format", "")
            if fmt == "pdf" or fmt == "html":
                full_text_url = url_entry.get("value", "")
                break
        if not full_text_url:
            for url_entry in record.get("url", []):
                full_text_url = url_entry.get("value", "")
                break

        # Venue / journal
        venue = record.get("publicationName", "")

        return PaperMetadata(
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors,
            publication_date=pub_date,
            source=AcademicSource.SPRINGER,
            keywords=keywords,
            citation_count=0,  # Springer Metadata API does not return citation counts
            full_text_url=full_text_url,
            metadata={
                "venue": venue,
                "content_type": record.get("contentType", ""),
                "publisher": record.get("publisher", "Springer Nature"),
                "issn": record.get("issn", ""),
                "isbn": record.get("isbn", ""),
                "volume": record.get("volume", ""),
                "number": record.get("number", ""),
                "start_page": record.get("startingPage", ""),
                "end_page": record.get("endingPage", ""),
                "open_access": record.get("openaccess", "false"),
            },
        )
