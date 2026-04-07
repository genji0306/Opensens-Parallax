"""
PubMed/NCBI adapter — 36M+ biomedical literature records.

API: NCBI E-utilities (https://eutils.ncbi.nlm.nih.gov/entrez/eutils/)
Authentication: Free (optional NCBI_API_KEY for higher rate limits).
Rate limit: 3 req/s without key, 10 req/s with key.
Docs: https://www.ncbi.nlm.nih.gov/books/NBK25497/
"""

import logging
import os
import time
import uuid
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import requests

from ....models.research import AcademicSource
from ..pipeline import AcademicSourceAdapter, PaperMetadata

logger = logging.getLogger(__name__)


class PubMedSource(AcademicSourceAdapter):
    """PubMed/NCBI E-utilities adapter — biomedical and life sciences."""

    ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    MIN_REQUEST_INTERVAL = 0.35  # ~3 req/s

    def __init__(self):
        self.api_key = os.environ.get("NCBI_API_KEY", "")
        if self.api_key:
            self.MIN_REQUEST_INTERVAL = 0.11  # 10 req/s with key
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "OSSR/1.0 (academic research; mailto:research@opensens.io)",
        })
        self._last_request_time = 0.0

    def _rate_limit(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < self.MIN_REQUEST_INTERVAL:
            time.sleep(self.MIN_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    def search(self, query: str, date_from: str = None, date_to: str = None, max_results: int = 50) -> List[PaperMetadata]:
        # Step 1: ESearch to get PMIDs
        self._rate_limit()
        try:
            params = {
                "db": "pubmed",
                "term": query,
                "retmax": min(max_results, 200),
                "retmode": "json",
                "sort": "relevance",
            }
            if self.api_key:
                params["api_key"] = self.api_key
            if date_from:
                params["mindate"] = date_from.replace("-", "/")
                params["datetype"] = "pdat"
            if date_to:
                params["maxdate"] = date_to.replace("-", "/")
                params["datetype"] = "pdat"

            resp = self.session.get(self.ESEARCH_URL, params=params, timeout=20)
            if resp.status_code != 200:
                logger.warning("[PubMed] ESearch returned %d", resp.status_code)
                return []

            data = resp.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            if not pmids:
                return []

            # Step 2: EFetch to get full records in XML
            return self._fetch_records(pmids[:max_results])

        except Exception as e:
            logger.warning("[PubMed] Search failed: %s", e)
            return []

    def _fetch_records(self, pmids: List[str]) -> List[PaperMetadata]:
        self._rate_limit()
        results = []
        try:
            params = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "xml",
                "rettype": "abstract",
            }
            if self.api_key:
                params["api_key"] = self.api_key

            resp = self.session.get(self.EFETCH_URL, params=params, timeout=30)
            if resp.status_code != 200:
                return []

            root = ET.fromstring(resp.content)
            for article_el in root.findall(".//PubmedArticle"):
                paper = self._parse_article(article_el)
                if paper:
                    results.append(paper)

        except Exception as e:
            logger.warning("[PubMed] EFetch failed: %s", e)
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        records = self._fetch_records([identifier])
        return records[0] if records else None

    def get_citations(self, doi: str) -> List[str]:
        return []  # PubMed elink could do this but it's complex

    def _parse_article(self, article_el) -> Optional[PaperMetadata]:
        try:
            medline = article_el.find(".//MedlineCitation")
            article = medline.find(".//Article") if medline is not None else None
            if article is None:
                return None

            # Title
            title_el = article.find(".//ArticleTitle")
            title = (title_el.text or "").strip() if title_el is not None else ""
            if not title:
                return None

            # PMID
            pmid_el = medline.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            # DOI
            doi = ""
            for eid in article.findall(".//ELocationID"):
                if eid.get("EIdType") == "doi":
                    doi = (eid.text or "").strip()
                    break
            # Also check ArticleIdList
            if not doi:
                pub_data = article_el.find(".//PubmedData")
                if pub_data is not None:
                    for aid in pub_data.findall(".//ArticleId"):
                        if aid.get("IdType") == "doi":
                            doi = (aid.text or "").strip()
                            break
            if not doi:
                doi = f"pmid:{pmid}" if pmid else f"pubmed:{uuid.uuid4().hex[:8]}"

            # Abstract
            abstract_parts = []
            for ab_text in article.findall(".//Abstract/AbstractText"):
                label = ab_text.get("Label", "")
                text = (ab_text.text or "").strip()
                if label and text:
                    abstract_parts.append(f"{label}: {text}")
                elif text:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts)[:5000]

            # Authors
            authors = []
            for author_el in article.findall(".//AuthorList/Author"):
                last = author_el.findtext("LastName", "")
                fore = author_el.findtext("ForeName", author_el.findtext("Initials", ""))
                name = f"{fore} {last}".strip()
                aff_el = author_el.find(".//AffiliationInfo/Affiliation")
                affiliation = (aff_el.text or "").strip() if aff_el is not None else ""
                if name:
                    authors.append({"name": name, "affiliation": affiliation})

            # Date
            pub_date = ""
            date_el = article.find(".//Journal/JournalIssue/PubDate")
            if date_el is not None:
                year = date_el.findtext("Year", "")
                month = date_el.findtext("Month", "01")
                day = date_el.findtext("Day", "01")
                # Month might be text like "Jan"
                month_map = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
                             "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
                if month.lower() in month_map:
                    month = month_map[month.lower()]
                if year:
                    pub_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

            # Keywords (MeSH terms)
            keywords = []
            for mesh in medline.findall(".//MeshHeadingList/MeshHeading/DescriptorName"):
                if mesh.text:
                    keywords.append(mesh.text)
            # Also check keyword list
            for kw in medline.findall(".//KeywordList/Keyword"):
                if kw.text and kw.text not in keywords:
                    keywords.append(kw.text)

            # Journal name
            journal = article.findtext(".//Journal/Title", "")

            return PaperMetadata(
                doi=doi,
                title=title,
                abstract=abstract,
                authors=authors,
                publication_date=pub_date,
                source=AcademicSource.PUBMED,
                keywords=keywords[:20],
                citation_count=0,
                references=[],
                full_text_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
                metadata={"pmid": pmid, "journal": journal},
            )

        except Exception as e:
            logger.warning("[PubMed] Parse article failed: %s", e)
            return None
