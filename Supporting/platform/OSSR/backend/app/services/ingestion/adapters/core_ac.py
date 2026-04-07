"""
CORE (core.ac.uk) adapter — 300M+ open access research outputs.

API: https://api.core.ac.uk/v3/
Authentication: Free API key (optional, higher rate limits with key).
Rate limit: 10 req/s without key, 150 req/s with key.
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


class CORESource(AcademicSourceAdapter):
    """CORE.ac.uk adapter — world's largest collection of open access research."""

    API_BASE = "https://api.core.ac.uk/v3"
    MIN_REQUEST_INTERVAL = 0.15

    def __init__(self):
        self.api_key = os.environ.get("CORE_API_KEY", "")
        self.session = requests.Session()
        headers = {
            "User-Agent": "OSSR/1.0 (academic research; mailto:research@opensens.io)",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
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
            params = {"q": query, "limit": min(max_results, 100), "offset": 0}
            if date_from:
                params["q"] += f" AND publishedDate>={date_from}"
            if date_to:
                params["q"] += f" AND publishedDate<={date_to}"

            resp = self.session.get(f"{self.API_BASE}/search/works", params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("results", [])[:max_results]:
                    paper = self._parse_item(item)
                    if paper:
                        results.append(paper)
            else:
                logger.warning("[CORE] Search returned %d: %s", resp.status_code, resp.text[:200])
        except Exception as e:
            logger.warning("[CORE] Search failed: %s", e)
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        self._rate_limit()
        try:
            resp = self.session.get(f"{self.API_BASE}/works/{identifier}", timeout=15)
            if resp.status_code == 200:
                return self._parse_item(resp.json())
        except Exception as e:
            logger.warning("[CORE] get_paper failed: %s", e)
        return None

    def get_citations(self, doi: str) -> List[str]:
        return []  # CORE API doesn't provide citation lists

    def _parse_item(self, item: Dict[str, Any]) -> Optional[PaperMetadata]:
        title = (item.get("title") or "").strip()
        if not title:
            return None

        doi = ""
        for ident in item.get("identifiers", []):
            if isinstance(ident, str) and ident.startswith("10."):
                doi = ident
                break
        if not doi:
            doi = item.get("doi") or f"core:{item.get('id', uuid.uuid4().hex[:10])}"

        authors = []
        for a in item.get("authors", []):
            if isinstance(a, dict):
                authors.append({"name": a.get("name", ""), "affiliation": ""})
            elif isinstance(a, str):
                authors.append({"name": a, "affiliation": ""})

        pub_date = item.get("publishedDate") or item.get("yearPublished") or ""
        if isinstance(pub_date, int):
            pub_date = f"{pub_date}-01-01"

        return PaperMetadata(
            doi=doi,
            title=title,
            abstract=(item.get("abstract") or "")[:5000],
            authors=authors,
            publication_date=str(pub_date)[:10],
            source=AcademicSource.CORE,
            keywords=item.get("subjects", [])[:20] if isinstance(item.get("subjects"), list) else [],
            citation_count=item.get("citationCount", 0) or 0,
            references=[],
            full_text_url=item.get("downloadUrl") or item.get("sourceFulltextUrls", [None])[0] if isinstance(item.get("sourceFulltextUrls"), list) and item.get("sourceFulltextUrls") else None,
            metadata={"core_id": item.get("id"), "language": item.get("language", {}).get("code") if isinstance(item.get("language"), dict) else None},
        )
