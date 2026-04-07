"""
DOAJ (Directory of Open Access Journals) adapter — 10M+ open access articles.

API: https://doaj.org/api/
Authentication: Free (optional API key for higher limits).
Rate limit: 2 req/s.
Docs: https://doaj.org/api/docs
"""

import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional

import requests

from ....models.research import AcademicSource
from ..pipeline import AcademicSourceAdapter, PaperMetadata

logger = logging.getLogger(__name__)


class DOAJSource(AcademicSourceAdapter):
    """DOAJ adapter — curated directory of open access journals."""

    API_BASE = "https://doaj.org/api"
    MIN_REQUEST_INTERVAL = 0.5

    def __init__(self):
        self.api_key = os.environ.get("DOAJ_API_KEY", "")
        self.session = requests.Session()
        headers = {
            "User-Agent": "OSSR/1.0 (academic research; mailto:research@opensens.io)",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Api-Key {self.api_key}"
        self.session.headers.update(headers)
        self._last_request_time = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def search(self, query: str, date_from: str = None, date_to: str = None, max_results: int = 50) -> List[PaperMetadata]:
        self._rate_limit()
        results = []
        try:
            params = {"q": query, "pageSize": min(max_results, 100), "page": 1}
            resp = self.session.get(f"{self.API_BASE}/search/articles/{query}", params={"pageSize": min(max_results, 100), "page": 1}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", [])[:max_results]:
                    paper = self._parse_item(item)
                    if paper:
                        # Date filter client-side (DOAJ API date filtering is limited)
                        if date_from and paper.publication_date and paper.publication_date < date_from:
                            continue
                        if date_to and paper.publication_date and paper.publication_date > date_to:
                            continue
                        results.append(paper)
            else:
                logger.warning("[DOAJ] Search returned %d", resp.status_code)
        except Exception as e:
            logger.warning("[DOAJ] Search failed: %s", e)
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        self._rate_limit()
        try:
            resp = self.session.get(f"{self.API_BASE}/articles/{identifier}", timeout=15)
            if resp.status_code == 200:
                return self._parse_item(resp.json())
        except Exception as e:
            logger.warning("[DOAJ] get_paper failed: %s", e)
        return None

    def get_citations(self, doi: str) -> List[str]:
        return []

    def _parse_item(self, item: Dict[str, Any]) -> Optional[PaperMetadata]:
        bibjson = item.get("bibjson", {})
        title = (bibjson.get("title") or "").strip()
        if not title:
            return None

        # DOI
        doi = ""
        for ident in bibjson.get("identifier", []):
            if ident.get("type") == "doi":
                doi = ident.get("id", "")
                break
        if not doi:
            doi = f"doaj:{item.get('id', uuid.uuid4().hex[:10])}"

        # Authors
        authors = []
        for a in bibjson.get("author", []):
            name = a.get("name", "")
            affiliation = a.get("affiliation", "")
            if name:
                authors.append({"name": name, "affiliation": affiliation})

        # Date
        pub_date = ""
        year = bibjson.get("year")
        month = bibjson.get("month", "01")
        if year:
            pub_date = f"{year}-{str(month).zfill(2)}-01"

        # Abstract
        abstract = (bibjson.get("abstract") or "")[:5000]

        # Keywords
        keywords = bibjson.get("keywords", [])[:20]

        # Full text link
        full_text_url = None
        for link in bibjson.get("link", []):
            if link.get("type") == "fulltext":
                full_text_url = link.get("url")
                break

        # Journal
        journal_title = bibjson.get("journal", {}).get("title", "")

        return PaperMetadata(
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors,
            publication_date=pub_date,
            source=AcademicSource.DOAJ,
            keywords=keywords,
            citation_count=0,
            references=[],
            full_text_url=full_text_url,
            metadata={"doaj_id": item.get("id"), "journal": journal_title, "license": bibjson.get("license", [{}])[0].get("type") if bibjson.get("license") else None},
        )
