"""
Europe PMC adapter — 44M+ life science articles with full-text access.

API: https://www.ebi.ac.uk/europepmc/webservices/rest/
Authentication: Free, no key required.
Rate limit: ~10 req/s.
Docs: https://europepmc.org/RestfulWebService
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import requests

from ....models.research import AcademicSource
from ..pipeline import AcademicSourceAdapter, PaperMetadata

logger = logging.getLogger(__name__)


class EuropePMCSource(AcademicSourceAdapter):
    """Europe PMC adapter — European life science literature aggregator."""

    API_BASE = "https://www.ebi.ac.uk/europepmc/webservices/rest"
    MIN_REQUEST_INTERVAL = 0.12

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
            search_query = query
            if date_from:
                year_from = date_from[:4]
                search_query += f" AND FIRST_PDATE:[{year_from} TO "
                if date_to:
                    search_query += f"{date_to[:4]}]"
                else:
                    search_query += "2030]"

            params = {
                "query": search_query,
                "format": "json",
                "pageSize": min(max_results, 100),
                "resultType": "core",
            }

            resp = self.session.get(f"{self.API_BASE}/search", params=params, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("resultList", {}).get("result", [])[:max_results]:
                    paper = self._parse_item(item)
                    if paper:
                        results.append(paper)
            else:
                logger.warning("[EuropePMC] Search returned %d", resp.status_code)
        except Exception as e:
            logger.warning("[EuropePMC] Search failed: %s", e)
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        self._rate_limit()
        try:
            # identifier can be DOI, PMID, or PMC ID
            resp = self.session.get(
                f"{self.API_BASE}/search",
                params={"query": f'DOI:"{identifier}" OR EXT_ID:"{identifier}"', "format": "json", "resultType": "core"},
                timeout=15,
            )
            if resp.status_code == 200:
                results = resp.json().get("resultList", {}).get("result", [])
                if results:
                    return self._parse_item(results[0])
        except Exception as e:
            logger.warning("[EuropePMC] get_paper failed: %s", e)
        return None

    def get_citations(self, doi: str) -> List[str]:
        self._rate_limit()
        try:
            resp = self.session.get(
                f"{self.API_BASE}/search",
                params={"query": f'CITES:"{doi}"', "format": "json", "pageSize": 50},
                timeout=15,
            )
            if resp.status_code == 200:
                citing = []
                for item in resp.json().get("resultList", {}).get("result", []):
                    d = item.get("doi")
                    if d:
                        citing.append(d)
                return citing
        except Exception as e:
            logger.warning("[EuropePMC] get_citations failed: %s", e)
        return []

    def _parse_item(self, item: Dict[str, Any]) -> Optional[PaperMetadata]:
        title = (item.get("title") or "").strip()
        if not title:
            return None

        doi = item.get("doi") or ""
        pmid = item.get("pmid") or ""
        pmcid = item.get("pmcid") or ""

        if not doi:
            if pmid:
                doi = f"pmid:{pmid}"
            elif pmcid:
                doi = f"pmc:{pmcid}"
            else:
                doi = f"epmc:{item.get('id', uuid.uuid4().hex[:8])}"

        # Authors
        authors = []
        author_str = item.get("authorString", "")
        if author_str:
            for name in author_str.split(", "):
                name = name.strip().rstrip(".")
                if name:
                    authors.append({"name": name, "affiliation": ""})
        # Use authorList if available (more structured)
        for a in item.get("authorList", {}).get("author", []):
            if isinstance(a, dict) and a.get("fullName"):
                aff = a.get("authorAffiliationDetailsList", {}).get("authorAffiliation", [{}])
                affiliation = aff[0].get("affiliation", "") if aff else ""
                # Don't duplicate if already from authorString
                if not any(x["name"] == a["fullName"] for x in authors):
                    authors.append({"name": a["fullName"], "affiliation": affiliation})

        # Date
        pub_date = ""
        first_pub = item.get("firstPublicationDate", "")
        if first_pub:
            pub_date = first_pub[:10]
        elif item.get("pubYear"):
            pub_date = f"{item['pubYear']}-01-01"

        # Abstract
        abstract = (item.get("abstractText") or "")[:5000]

        # Keywords
        keywords = []
        kw_list = item.get("keywordList", {}).get("keyword", [])
        if isinstance(kw_list, list):
            keywords = [k for k in kw_list if isinstance(k, str)][:20]
        mesh_terms = item.get("meshHeadingList", {}).get("meshHeading", [])
        for mesh in mesh_terms:
            if isinstance(mesh, dict) and mesh.get("descriptorName"):
                kw = mesh["descriptorName"]
                if kw not in keywords:
                    keywords.append(kw)

        # Citation count
        citation_count = item.get("citedByCount", 0) or 0

        # Full text
        full_text_url = None
        if item.get("isOpenAccess") == "Y" and pmcid:
            full_text_url = f"https://europepmc.org/article/pmc/{pmcid}"
        elif doi and doi.startswith("10."):
            full_text_url = f"https://doi.org/{doi}"

        return PaperMetadata(
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors[:50],
            publication_date=pub_date,
            source=AcademicSource.EUROPE_PMC,
            keywords=keywords[:20],
            citation_count=citation_count,
            references=[],
            full_text_url=full_text_url,
            metadata={
                "pmid": pmid,
                "pmcid": pmcid,
                "journal": item.get("journalTitle"),
                "is_open_access": item.get("isOpenAccess") == "Y",
                "source_type": item.get("source"),
            },
        )
