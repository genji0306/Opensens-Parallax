"""
CrossRef adapter — 150M+ DOI metadata records.

API: https://api.crossref.org/
Authentication: Free (polite pool with mailto header).
Rate limit: 50 req/s polite pool.
Docs: https://www.crossref.org/documentation/retrieve-metadata/rest-api/
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import requests

from ....models.research import AcademicSource
from ..pipeline import AcademicSourceAdapter, PaperMetadata

logger = logging.getLogger(__name__)


class CrossRefSource(AcademicSourceAdapter):
    """CrossRef adapter — comprehensive DOI metadata registry."""

    API_BASE = "https://api.crossref.org"
    MIN_REQUEST_INTERVAL = 0.05  # 50ms = polite pool rate

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "OSSR/1.0 (academic research; mailto:research@opensens.io)",
            "Accept": "application/json",
        })
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
            params = {
                "query": query,
                "rows": min(max_results, 100),
                "sort": "relevance",
                "order": "desc",
                "select": "DOI,title,abstract,author,published-print,published-online,subject,is-referenced-by-count,reference,link",
            }
            if date_from:
                params["filter"] = f"from-pub-date:{date_from}"
                if date_to:
                    params["filter"] += f",until-pub-date:{date_to}"
            elif date_to:
                params["filter"] = f"until-pub-date:{date_to}"

            resp = self.session.get(f"{self.API_BASE}/works", params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("message", {}).get("items", [])[:max_results]:
                    paper = self._parse_item(item)
                    if paper:
                        results.append(paper)
            else:
                logger.warning("[CrossRef] Search returned %d", resp.status_code)
        except Exception as e:
            logger.warning("[CrossRef] Search failed: %s", e)
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        self._rate_limit()
        try:
            resp = self.session.get(f"{self.API_BASE}/works/{identifier}", timeout=15)
            if resp.status_code == 200:
                return self._parse_item(resp.json().get("message", {}))
        except Exception as e:
            logger.warning("[CrossRef] get_paper failed: %s", e)
        return None

    def get_citations(self, doi: str) -> List[str]:
        self._rate_limit()
        try:
            resp = self.session.get(f"{self.API_BASE}/works/{doi}", params={"select": "is-referenced-by-count"}, timeout=10)
            if resp.status_code == 200:
                # CrossRef doesn't list citing DOIs directly, only count
                return []
        except Exception:
            pass
        return []

    def _parse_item(self, item: Dict[str, Any]) -> Optional[PaperMetadata]:
        titles = item.get("title", [])
        title = titles[0] if titles else ""
        if not title:
            return None

        doi = item.get("DOI", "")
        if not doi:
            return None

        # Authors
        authors = []
        for a in item.get("author", []):
            name_parts = []
            if a.get("given"):
                name_parts.append(a["given"])
            if a.get("family"):
                name_parts.append(a["family"])
            name = " ".join(name_parts)
            affiliation = ""
            if a.get("affiliation"):
                aff_list = a["affiliation"]
                if isinstance(aff_list, list) and aff_list:
                    affiliation = aff_list[0].get("name", "") if isinstance(aff_list[0], dict) else str(aff_list[0])
            if name:
                authors.append({"name": name, "affiliation": affiliation})

        # Publication date
        pub_date = ""
        for date_key in ("published-print", "published-online", "created"):
            dp = item.get(date_key, {}).get("date-parts", [[]])
            if dp and dp[0]:
                parts = dp[0]
                year = str(parts[0]) if len(parts) > 0 else ""
                month = f"{parts[1]:02d}" if len(parts) > 1 else "01"
                day = f"{parts[2]:02d}" if len(parts) > 2 else "01"
                if year:
                    pub_date = f"{year}-{month}-{day}"
                    break

        # Abstract
        abstract = item.get("abstract", "") or ""
        # CrossRef abstracts sometimes have JATS XML tags
        import re
        abstract = re.sub(r"<[^>]+>", "", abstract)[:5000]

        # Keywords / subjects
        keywords = item.get("subject", [])[:20]

        # References
        refs = []
        for ref in item.get("reference", [])[:50]:
            ref_doi = ref.get("DOI")
            if ref_doi:
                refs.append(ref_doi)

        # Full text link
        full_text_url = None
        for link in item.get("link", []):
            if link.get("content-type") == "application/pdf":
                full_text_url = link.get("URL")
                break
            if not full_text_url and link.get("URL"):
                full_text_url = link.get("URL")

        return PaperMetadata(
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors,
            publication_date=pub_date,
            source=AcademicSource.CROSSREF,
            keywords=keywords,
            citation_count=item.get("is-referenced-by-count", 0) or 0,
            references=refs,
            full_text_url=full_text_url,
            metadata={
                "publisher": item.get("publisher"),
                "container_title": item.get("container-title", [None])[0] if item.get("container-title") else None,
                "type": item.get("type"),
                "issn": item.get("ISSN", []),
            },
        )
