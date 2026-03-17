"""
OSSR Academic Ingestion Service
Fetches, parses, and stores papers from bioRxiv, arXiv, and Semantic Scholar.
Implements the 5-stage pipeline: FETCH → PARSE → EXTRACT → ENRICH → STORE.
"""

import concurrent.futures
import hashlib
import logging
import math
import threading
import time
import uuid
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional
from urllib.parse import quote

import requests

from opensens_common.config import Config
from ..models.research import (
    AcademicSource,
    Citation,
    IngestionStatus,
    Paper,
    ResearchDataStore,
)
from opensens_common.task import TaskManager, TaskStatus
from opensens_common.llm_client import LLMClient

logger = logging.getLogger(__name__)


# ── Data Transfer Objects ──────────────────────────────────────────────


class PaperMetadata:
    """Lightweight intermediate object from a source adapter before full Paper creation."""

    def __init__(
        self,
        doi: str,
        title: str,
        abstract: str,
        authors: List[Dict[str, str]],
        publication_date: str,
        source: AcademicSource,
        keywords: Optional[List[str]] = None,
        citation_count: int = 0,
        references: Optional[List[str]] = None,
        full_text_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.doi = doi
        self.title = title
        self.abstract = abstract
        self.authors = authors
        self.publication_date = publication_date
        self.source = source
        self.keywords = keywords or []
        self.citation_count = citation_count
        self.references = references or []
        self.full_text_url = full_text_url
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "doi": self.doi,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "publication_date": self.publication_date,
            "source": self.source.value if isinstance(self.source, AcademicSource) else self.source,
            "keywords": self.keywords,
            "citation_count": self.citation_count,
            "references": self.references,
            "full_text_url": self.full_text_url,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PaperMetadata":
        source = data.get("source", AcademicSource.BIORXIV.value)
        if isinstance(source, str):
            source = AcademicSource(source)
        return cls(
            doi=data.get("doi", ""),
            title=data.get("title", ""),
            abstract=data.get("abstract", ""),
            authors=data.get("authors") or [],
            publication_date=data.get("publication_date", ""),
            source=source,
            keywords=data.get("keywords") or [],
            citation_count=data.get("citation_count", 0),
            references=data.get("references") or [],
            full_text_url=data.get("full_text_url"),
            metadata=data.get("metadata") or {},
        )


# ── Abstract Source Interface ──────────────────────────────────────────


class AcademicSourceAdapter(ABC):
    """Base interface for all academic data source adapters."""

    @abstractmethod
    def search(
        self,
        query: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 50,
    ) -> List[PaperMetadata]:
        """Search for papers matching query. Returns list of PaperMetadata."""
        ...

    @abstractmethod
    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        """Get a single paper by DOI or source-specific ID."""
        ...

    @abstractmethod
    def get_citations(self, doi: str) -> List[str]:
        """Get list of DOIs that cite the given paper."""
        ...


# ── bioRxiv / medRxiv Source ──────────────────────────────────────────


class BioRxivSource(AcademicSourceAdapter):
    """
    bioRxiv / medRxiv adapter using the public API.
    API docs: https://api.biorxiv.org/
    """

    BASE_URL = "https://api.biorxiv.org"

    def __init__(self, server: str = "biorxiv"):
        self.server = server  # "biorxiv" or "medrxiv"
        self.source = AcademicSource.BIORXIV if server == "biorxiv" else AcademicSource.MEDRXIV
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "OSSR/1.0 (academic research)"})

    # Max pages to scan (bioRxiv has no search API, only date-range dumps)
    MAX_PAGES = 5

    def search(
        self,
        query: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 50,
    ) -> List[PaperMetadata]:
        if not date_to:
            date_to = datetime.now().strftime("%Y-%m-%d")
        if not date_from:
            # Default to last 6 months instead of 5 years to avoid huge scans
            from datetime import timedelta
            d = datetime.now() - timedelta(days=180)
            date_from = d.strftime("%Y-%m-%d")

        results = []
        cursor = 0
        per_page = 100
        pages_scanned = 0
        query_terms = [t.lower() for t in query.lower().split() if len(t) > 2]

        while len(results) < max_results and pages_scanned < self.MAX_PAGES:
            url = (
                f"{self.BASE_URL}/details/{self.server}/{date_from}/{date_to}/{cursor}"
            )
            try:
                resp = self.session.get(url, timeout=20)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"bioRxiv API error at cursor {cursor}: {e}")
                break

            collection = data.get("collection", [])
            if not collection:
                break

            for item in collection:
                title = item.get("title", "")
                abstract = item.get("abstract", "")
                text = (title + " " + abstract).lower()
                # Require at least half of query terms to match
                matches = sum(1 for t in query_terms if t in text)
                if matches < max(len(query_terms) // 2, 1):
                    continue

                doi = item.get("doi", "")
                if not doi:
                    continue

                authors = self._parse_authors(item.get("authors", ""))
                pub_date = item.get("date", "")

                results.append(PaperMetadata(
                    doi=doi,
                    title=title,
                    abstract=abstract,
                    authors=authors,
                    publication_date=pub_date,
                    source=self.source,
                    keywords=[item.get("category", "")],
                    full_text_url=f"https://www.biorxiv.org/content/{doi}v{item.get('version', '1')}.full",
                    metadata={
                        "server": self.server,
                        "category": item.get("category", ""),
                        "version": item.get("version", "1"),
                        "type": item.get("type", ""),
                    },
                ))

                if len(results) >= max_results:
                    break

            pages_scanned += 1
            cursor += per_page
            messages_total = int(data.get("messages", [{}])[0].get("total", 0)) if data.get("messages") else 0
            if cursor >= messages_total:
                break

            time.sleep(0.5)  # rate limiting

        logger.info(f"bioRxiv: found {len(results)} papers for query '{query}' (scanned {pages_scanned} pages)")
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        url = f"{self.BASE_URL}/details/{self.server}/{identifier}"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            collection = data.get("collection", [])
            if not collection:
                return None
            item = collection[0]
            return PaperMetadata(
                doi=item.get("doi", identifier),
                title=item.get("title", ""),
                abstract=item.get("abstract", ""),
                authors=self._parse_authors(item.get("authors", "")),
                publication_date=item.get("date", ""),
                source=self.source,
                keywords=[item.get("category", "")],
            )
        except Exception as e:
            logger.warning(f"bioRxiv get_paper error for {identifier}: {e}")
            return None

    def get_citations(self, doi: str) -> List[str]:
        # bioRxiv API does not provide citation data directly
        return []

    @staticmethod
    def _parse_authors(authors_str: str) -> List[Dict[str, str]]:
        if not authors_str:
            return []
        return [{"name": a.strip()} for a in authors_str.split(";") if a.strip()]


# ── arXiv Source ──────────────────────────────────────────────────────


class ArXivSource(AcademicSourceAdapter):
    """
    arXiv adapter using the Atom API.
    API docs: https://info.arxiv.org/help/api/
    """

    BASE_URL = "http://export.arxiv.org/api/query"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "OSSR/1.0 (academic research)"})

    def search(
        self,
        query: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 50,
    ) -> List[PaperMetadata]:
        search_query = f"all:{query}"
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": min(max_results, 200),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=30)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"arXiv API error: {e}")
            return []

        return self._parse_atom_response(resp.text, date_from, date_to)

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        # arXiv IDs like "2411.11581" or DOIs
        arxiv_id = identifier.replace("arXiv:", "").strip()
        params = {"id_list": arxiv_id, "max_results": 1}
        try:
            resp = self.session.get(self.BASE_URL, params=params, timeout=15)
            resp.raise_for_status()
            results = self._parse_atom_response(resp.text)
            return results[0] if results else None
        except Exception as e:
            logger.warning(f"arXiv get_paper error for {identifier}: {e}")
            return None

    def get_citations(self, doi: str) -> List[str]:
        # arXiv API does not provide citation data
        return []

    def _parse_atom_response(
        self,
        xml_text: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[PaperMetadata]:
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        results = []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            logger.warning(f"arXiv XML parse error: {e}")
            return []

        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)

            title = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else ""
            abstract = summary_el.text.strip().replace("\n", " ") if summary_el is not None and summary_el.text else ""
            published = published_el.text[:10] if published_el is not None and published_el.text else ""

            if date_from and published < date_from:
                continue
            if date_to and published > date_to:
                continue

            # Extract arXiv ID and construct DOI-like identifier
            id_el = entry.find("atom:id", ns)
            arxiv_url = id_el.text if id_el is not None and id_el.text else ""
            arxiv_id = arxiv_url.split("/abs/")[-1] if "/abs/" in arxiv_url else ""

            # Check for actual DOI link
            doi = ""
            for link in entry.findall("atom:link", ns):
                href = link.get("href", "")
                if "doi.org" in href:
                    doi = href.replace("http://dx.doi.org/", "").replace("https://doi.org/", "")
                    break
            if not doi:
                doi = f"arXiv:{arxiv_id}" if arxiv_id else ""

            if not doi:
                continue

            authors = []
            for author in entry.findall("atom:author", ns):
                name_el = author.find("atom:name", ns)
                if name_el is not None and name_el.text:
                    authors.append({"name": name_el.text.strip()})

            categories = []
            for cat in entry.findall("arxiv:primary_category", ns):
                term = cat.get("term", "")
                if term:
                    categories.append(term)
            for cat in entry.findall("atom:category", ns):
                term = cat.get("term", "")
                if term and term not in categories:
                    categories.append(term)

            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "pdf":
                    pdf_url = link.get("href", "")
                    break

            results.append(PaperMetadata(
                doi=doi,
                title=title,
                abstract=abstract,
                authors=authors,
                publication_date=published,
                source=AcademicSource.ARXIV,
                keywords=categories,
                full_text_url=pdf_url,
                metadata={"arxiv_id": arxiv_id, "categories": categories},
            ))

        logger.info(f"arXiv: parsed {len(results)} papers")
        return results


# ── Semantic Scholar Source ────────────────────────────────────────────


class SemanticScholarSource(AcademicSourceAdapter):
    """
    Semantic Scholar adapter using the public API.
    API docs: https://api.semanticscholar.org/
    Rate limit: 100 requests/sec (unauthenticated).
    """

    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    FIELDS = "paperId,externalIds,title,abstract,authors,year,citationCount,references,url,fieldsOfStudy,publicationDate"

    def __init__(self, api_key: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "OSSR/1.0 (academic research)"})
        if api_key:
            self.session.headers["x-api-key"] = api_key

    def search(
        self,
        query: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 50,
    ) -> List[PaperMetadata]:
        results = []
        offset = 0
        per_page = min(max_results, 100)

        year_filter = ""
        if date_from or date_to:
            y_from = date_from[:4] if date_from else "2000"
            y_to = date_to[:4] if date_to else str(datetime.now().year)
            year_filter = f"&year={y_from}-{y_to}"

        while len(results) < max_results:
            url = (
                f"{self.BASE_URL}/paper/search"
                f"?query={quote(query)}"
                f"&fields={self.FIELDS}"
                f"&offset={offset}&limit={per_page}"
                f"{year_filter}"
            )
            try:
                resp = self.session.get(url, timeout=30)
                if resp.status_code == 429:
                    time.sleep(2)
                    continue
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"Semantic Scholar API error at offset {offset}: {e}")
                break

            papers = data.get("data", [])
            if not papers:
                break

            for item in papers:
                doi = (item.get("externalIds") or {}).get("DOI", "")
                s2_id = item.get("paperId", "")
                if not doi:
                    doi = f"S2:{s2_id}" if s2_id else ""
                if not doi:
                    continue

                abstract = item.get("abstract") or ""
                pub_date = item.get("publicationDate") or ""
                if not pub_date and item.get("year"):
                    pub_date = f"{item['year']}-01-01"

                if date_from and pub_date and pub_date < date_from:
                    continue
                if date_to and pub_date and pub_date > date_to:
                    continue

                authors = [
                    {"name": a.get("name", ""), "authorId": a.get("authorId", "")}
                    for a in (item.get("authors") or [])
                ]

                ref_dois = []
                for ref in (item.get("references") or []):
                    ref_doi = (ref.get("externalIds") or {}).get("DOI")
                    if ref_doi:
                        ref_dois.append(ref_doi)

                results.append(PaperMetadata(
                    doi=doi,
                    title=item.get("title", ""),
                    abstract=abstract,
                    authors=authors,
                    publication_date=pub_date,
                    source=AcademicSource.SEMANTIC_SCHOLAR,
                    keywords=item.get("fieldsOfStudy") or [],
                    citation_count=item.get("citationCount", 0),
                    references=ref_dois,
                    full_text_url=item.get("url", ""),
                    metadata={"s2_paper_id": s2_id},
                ))

                if len(results) >= max_results:
                    break

            offset += per_page
            total = data.get("total", 0)
            if offset >= total:
                break

            time.sleep(0.3)  # rate limiting

        logger.info(f"Semantic Scholar: found {len(results)} papers for query '{query}'")
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        url = f"{self.BASE_URL}/paper/{identifier}?fields={self.FIELDS}"
        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            item = resp.json()
            doi = (item.get("externalIds") or {}).get("DOI", identifier)
            return PaperMetadata(
                doi=doi,
                title=item.get("title", ""),
                abstract=item.get("abstract") or "",
                authors=[{"name": a.get("name", "")} for a in (item.get("authors") or [])],
                publication_date=item.get("publicationDate") or "",
                source=AcademicSource.SEMANTIC_SCHOLAR,
                keywords=item.get("fieldsOfStudy") or [],
                citation_count=item.get("citationCount", 0),
                metadata={"s2_paper_id": item.get("paperId", "")},
            )
        except Exception as e:
            logger.warning(f"Semantic Scholar get_paper error for {identifier}: {e}")
            return None

    def get_citations(self, doi: str) -> List[str]:
        url = f"{self.BASE_URL}/paper/{doi}/citations?fields=externalIds&limit=500"
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            citing_dois = []
            for item in data.get("data", []):
                citing = item.get("citingPaper", {})
                citing_doi = (citing.get("externalIds") or {}).get("DOI")
                if citing_doi:
                    citing_dois.append(citing_doi)
            return citing_dois
        except Exception as e:
            logger.warning(f"Semantic Scholar get_citations error for {doi}: {e}")
            return []


# ── OpenAlex Source ───────────────────────────────────────────────────


class OpenAlexSource(AcademicSourceAdapter):
    """
    OpenAlex adapter using the free public API.
    API docs: https://docs.openalex.org/
    No API key required; polite pool via mailto in User-Agent.
    """

    BASE_URL = "https://api.openalex.org"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "OSSR/1.0 (mailto:research@opensens.io)",
        })

    def search(
        self,
        query: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 50,
    ) -> List[PaperMetadata]:
        results = []
        per_page = min(max_results, 200)
        cursor = "*"

        # Build date filter
        date_filter = ""
        if date_from:
            date_filter += f",from_publication_date:{date_from}"
        if date_to:
            date_filter += f",to_publication_date:{date_to}"

        while len(results) < max_results:
            params = {
                "search": query,
                "per_page": per_page,
                "cursor": cursor,
                "select": "id,doi,title,abstract_inverted_index,authorships,publication_date,cited_by_count,referenced_works,concepts,primary_location,type",
                "filter": f"type:article{date_filter}",
                "sort": "relevance_score:desc",
            }

            try:
                resp = self.session.get(f"{self.BASE_URL}/works", params=params, timeout=30)
                if resp.status_code == 429:
                    time.sleep(2)
                    continue
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"OpenAlex API error: {e}")
                break

            works = data.get("results", [])
            if not works:
                break

            for item in works:
                paper = self._parse_work(item)
                if paper:
                    results.append(paper)
                if len(results) >= max_results:
                    break

            # Cursor pagination
            meta = data.get("meta", {})
            cursor = meta.get("next_cursor")
            if not cursor:
                break

            time.sleep(0.2)  # polite rate limiting

        logger.info(f"OpenAlex: found {len(results)} papers for query '{query}'")
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        # Accept DOI or OpenAlex ID
        if identifier.startswith("https://openalex.org/"):
            url = f"{self.BASE_URL}/works/{identifier.split('/')[-1]}"
        elif identifier.startswith("10."):
            url = f"{self.BASE_URL}/works/doi:{identifier}"
        else:
            url = f"{self.BASE_URL}/works/{identifier}"

        try:
            resp = self.session.get(url, timeout=15)
            resp.raise_for_status()
            return self._parse_work(resp.json())
        except Exception as e:
            logger.warning(f"OpenAlex get_paper error for {identifier}: {e}")
            return None

    def get_citations(self, doi: str) -> List[str]:
        url = f"{self.BASE_URL}/works"
        params = {
            "filter": f"cites:doi:{doi}",
            "select": "doi",
            "per_page": 200,
        }
        try:
            resp = self.session.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            citing_dois = []
            for item in data.get("results", []):
                raw_doi = item.get("doi", "")
                if raw_doi:
                    citing_dois.append(raw_doi.replace("https://doi.org/", ""))
            return citing_dois
        except Exception as e:
            logger.warning(f"OpenAlex get_citations error for {doi}: {e}")
            return []

    def _parse_work(self, item: Dict[str, Any]) -> Optional[PaperMetadata]:
        """Convert an OpenAlex work object to PaperMetadata."""
        raw_doi = item.get("doi", "") or ""
        doi = raw_doi.replace("https://doi.org/", "")
        openalex_id = (item.get("id", "") or "").replace("https://openalex.org/", "")

        if not doi:
            doi = f"openalex:{openalex_id}" if openalex_id else ""
        if not doi:
            return None

        title = item.get("title", "") or ""
        abstract = self._reconstruct_abstract(item.get("abstract_inverted_index"))

        authors = []
        for authorship in (item.get("authorships") or []):
            author_info = authorship.get("author", {})
            name = author_info.get("display_name", "")
            if name:
                inst = ""
                institutions = authorship.get("institutions") or []
                if institutions:
                    inst = institutions[0].get("display_name", "")
                authors.append({"name": name, "affiliation": inst})

        pub_date = item.get("publication_date", "") or ""

        keywords = []
        for concept in (item.get("concepts") or []):
            cname = concept.get("display_name", "")
            if cname and concept.get("score", 0) > 0.3:
                keywords.append(cname)

        # Full text URL from primary location
        full_text_url = ""
        primary_loc = item.get("primary_location") or {}
        if primary_loc.get("pdf_url"):
            full_text_url = primary_loc["pdf_url"]
        elif primary_loc.get("landing_page_url"):
            full_text_url = primary_loc["landing_page_url"]

        # References: OpenAlex IDs (not DOIs) — store for later resolution
        ref_works = item.get("referenced_works") or []

        return PaperMetadata(
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors,
            publication_date=pub_date,
            source=AcademicSource.OPENALEX,
            keywords=keywords[:15],
            citation_count=item.get("cited_by_count", 0),
            references=[],  # OpenAlex refs are IDs, not DOIs
            full_text_url=full_text_url,
            metadata={
                "openalex_id": openalex_id,
                "type": item.get("type", ""),
                "referenced_works_count": len(ref_works),
            },
        )

    @staticmethod
    def _reconstruct_abstract(inverted_index: Optional[Dict]) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return ""
        # inverted_index: {"word": [pos1, pos2], ...}
        word_positions = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(w for _, w in word_positions)


# ── OpenReview Source ────────────────────────────────────────────────


class OpenReviewSource(AcademicSourceAdapter):
    """
    OpenReview adapter using the V2 REST API.
    Fetches conference submissions + peer review metadata from venues
    like ICLR, NeurIPS, ICML, EMNLP, etc.

    API docs: https://docs.openreview.net/
    """

    API_V2 = "https://api2.openreview.net"

    # Major ML/AI venues with their OpenReview group IDs
    VENUES = [
        "ICLR.cc/2025/Conference",
        "ICLR.cc/2024/Conference",
        "NeurIPS.cc/2024/Conference",
        "NeurIPS.cc/2023/Conference",
        "ICML.cc/2024/Conference",
        "ICML.cc/2023/Conference",
        "EMNLP/2024/Conference",
        "aclweb.org/ACL/2024/Conference",
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "OSSR/1.0 (academic research)"})
        self._token = None

    def _get_token(self) -> Optional[str]:
        """Obtain a guest access token for the OpenReview API."""
        if self._token:
            return self._token
        try:
            resp = self.session.post(
                f"{self.API_V2}/login/guest",
                json={},
                timeout=10,
            )
            if resp.status_code == 200:
                self._token = resp.json().get("token")
                if self._token:
                    self.session.headers["Authorization"] = f"Bearer {self._token}"
                return self._token
        except Exception as e:
            logger.warning(f"OpenReview guest login failed: {e}")
        return None

    def search(
        self,
        query: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 50,
    ) -> List[PaperMetadata]:
        self._get_token()
        results = []

        # Search across relevant venues using the notes search endpoint
        try:
            params = {
                "query": query,
                "limit": min(max_results, 100),
                "offset": 0,
            }
            resp = self.session.get(
                f"{self.API_V2}/notes/search",
                params=params,
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                notes = data.get("notes", [])
                for note in notes:
                    pm = self._note_to_paper(note)
                    if pm:
                        if date_from and pm.publication_date < date_from:
                            continue
                        if date_to and pm.publication_date > date_to:
                            continue
                        results.append(pm)
        except Exception as e:
            logger.warning(f"OpenReview search failed: {e}")

        # If search returned few results, also try venue-specific queries
        if len(results) < max_results:
            query_lower = query.lower()
            for venue in self.VENUES[:4]:  # Limit venue scans
                if len(results) >= max_results:
                    break
                try:
                    params = {
                        "content.venue": venue,
                        "limit": min(max_results - len(results), 50),
                        "offset": 0,
                    }
                    resp = self.session.get(
                        f"{self.API_V2}/notes",
                        params=params,
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        for note in data.get("notes", []):
                            pm = self._note_to_paper(note)
                            if pm and self._matches_query(pm, query_lower):
                                if date_from and pm.publication_date < date_from:
                                    continue
                                if date_to and pm.publication_date > date_to:
                                    continue
                                results.append(pm)
                except Exception as e:
                    logger.debug(f"OpenReview venue scan failed for {venue}: {e}")

        # Deduplicate by DOI
        seen = set()
        unique = []
        for r in results:
            if r.doi not in seen:
                seen.add(r.doi)
                unique.append(r)
        results = unique[:max_results]

        logger.info(f"OpenReview: found {len(results)} papers for '{query}'")
        return results

    def get_paper(self, identifier: str) -> Optional[PaperMetadata]:
        self._get_token()
        try:
            resp = self.session.get(
                f"{self.API_V2}/notes",
                params={"id": identifier},
                timeout=10,
            )
            if resp.status_code == 200:
                notes = resp.json().get("notes", [])
                if notes:
                    return self._note_to_paper(notes[0])
        except Exception as e:
            logger.warning(f"OpenReview get_paper error for {identifier}: {e}")
        return None

    def get_citations(self, doi: str) -> List[str]:
        # OpenReview doesn't provide citation graphs
        return []

    def _note_to_paper(self, note: Dict[str, Any]) -> Optional[PaperMetadata]:
        """Convert an OpenReview note to PaperMetadata."""
        content = note.get("content", {})
        note_id = note.get("id", "")

        # V2 content fields are wrapped in {"value": ...}
        def val(field):
            v = content.get(field, {})
            return v.get("value", v) if isinstance(v, dict) else v

        title = val("title") or ""
        abstract = val("abstract") or ""

        if not title:
            return None

        # Authors — may be in content.authors or note.signatures
        authors_raw = val("authors") or []
        if isinstance(authors_raw, list):
            authors = [{"name": a} if isinstance(a, str) else a for a in authors_raw]
        else:
            authors = []

        # Venue / date
        venue = val("venue") or val("venueid") or ""
        cdate = note.get("cdate") or note.get("tcdate") or note.get("odate")
        if cdate and isinstance(cdate, (int, float)):
            pub_date = datetime.fromtimestamp(cdate / 1000).strftime("%Y-%m-%d")
        elif cdate and isinstance(cdate, str):
            pub_date = cdate[:10]
        else:
            pub_date = ""

        # Keywords
        keywords_raw = val("keywords") or []
        keywords = keywords_raw if isinstance(keywords_raw, list) else []

        # DOI — use note ID as fallback identifier
        doi = val("doi") or f"openreview:{note_id}" if note_id else ""
        if not doi:
            return None

        # PDF URL
        pdf = val("pdf") or ""
        pdf_url = f"https://openreview.net{pdf}" if pdf and pdf.startswith("/") else pdf

        # Decision (if available — unique to OpenReview)
        decision = val("decision") or ""

        return PaperMetadata(
            doi=doi,
            title=title,
            abstract=abstract,
            authors=authors,
            publication_date=pub_date,
            source=AcademicSource.OPENREVIEW,
            keywords=keywords,
            full_text_url=pdf_url,
            metadata={
                "openreview_id": note_id,
                "venue": venue,
                "decision": decision,
                "forum": note.get("forum", ""),
            },
        )

    @staticmethod
    def _matches_query(paper: PaperMetadata, query_lower: str) -> bool:
        """Basic keyword match against title and abstract."""
        text = f"{paper.title} {paper.abstract}".lower()
        terms = query_lower.split()
        return any(t in text for t in terms if len(t) > 2)


# ── Source Registry ───────────────────────────────────────────────────


SOURCES: Dict[AcademicSource, type] = {
    AcademicSource.BIORXIV: BioRxivSource,
    AcademicSource.MEDRXIV: BioRxivSource,
    AcademicSource.ARXIV: ArXivSource,
    AcademicSource.SEMANTIC_SCHOLAR: SemanticScholarSource,
    AcademicSource.OPENALEX: OpenAlexSource,
    AcademicSource.OPENREVIEW: OpenReviewSource,
}


def get_source(source_type: AcademicSource) -> AcademicSourceAdapter:
    """Factory: create a source adapter by type."""
    cls = SOURCES.get(source_type)
    if not cls:
        raise ValueError(f"Unsupported source: {source_type}")
    if source_type == AcademicSource.MEDRXIV:
        return cls(server="medrxiv")
    return cls()


# ── Ingestion Pipeline ────────────────────────────────────────────────


ENTITY_EXTRACTION_PROMPT = """You are an academic research analyst. Extract structured information from this paper abstract.

Return a JSON object with:
- "keywords": list of 5-10 key technical terms and concepts
- "methods": list of methodologies mentioned
- "findings": list of key findings or contributions (1-3 items)
- "research_questions": list of research questions addressed (1-2 items)
- "domain": the broad research domain (e.g., "Neuroscience", "Materials Science")
- "subfield": the specific subfield (e.g., "Electrochemical Impedance Spectroscopy")

Paper title: {title}
Abstract: {abstract}
"""


class IngestionPipeline:
    """
    Orchestrates the 5-stage academic paper ingestion pipeline.
    FETCH → PARSE → EXTRACT → ENRICH → STORE
    """

    FETCH_TIMEOUT_SECONDS = 45
    MAX_FETCH_WORKERS = 4
    CACHE_TTL_HOURS = {
        AcademicSource.ARXIV: 24 * 7,
        AcademicSource.BIORXIV: 24,
        AcademicSource.MEDRXIV: 24,
        AcademicSource.OPENALEX: 24,
        AcademicSource.SEMANTIC_SCHOLAR: 24,
    }

    def __init__(self):
        self.store = ResearchDataStore()
        self.task_manager = TaskManager()

    def ingest_async(
        self,
        query: str,
        sources: List[str],
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        max_results: int = 50,
    ) -> str:
        """
        Start an async ingestion job.
        Returns a task_id for tracking progress.
        """
        task_id = self.task_manager.create_task(
            task_type="research_ingestion",
            metadata={
                "query": query,
                "sources": sources,
                "date_from": date_from,
                "date_to": date_to,
                "max_results": max_results,
            },
        )

        thread = threading.Thread(
            target=self._ingest_worker,
            args=(task_id, query, sources, date_from, date_to, max_results),
            daemon=True,
        )
        thread.start()
        return task_id

    def _ingest_worker(
        self,
        task_id: str,
        query: str,
        sources: List[str],
        date_from: Optional[str],
        date_to: Optional[str],
        max_results: int,
    ):
        """Background worker for the ingestion pipeline."""
        self.task_manager.update_task(
            task_id, status=TaskStatus.PROCESSING, progress=0, message="Starting ingestion..."
        )

        try:
            # Stage 1: FETCH
            self.task_manager.update_task(
                task_id, progress=10, message="Fetching papers from academic APIs..."
            )
            all_metadata = self._fetch(query, sources, date_from, date_to, max_results)

            if not all_metadata:
                self.task_manager.complete_task(task_id, result={
                    "papers_ingested": 0,
                    "message": "No papers found matching query.",
                })
                return

            # Stage 2: PARSE (dedup + normalize)
            self.task_manager.update_task(
                task_id, progress=30, message=f"Parsing {len(all_metadata)} papers..."
            )
            new_papers = self._parse(all_metadata)

            # Stage 3: EXTRACT (LLM entity extraction)
            self.task_manager.update_task(
                task_id, progress=50, message=f"Extracting entities from {len(new_papers)} papers..."
            )
            enriched_papers = self._extract_entities(new_papers, task_id)

            # Stage 4: ENRICH (citation cross-referencing)
            self.task_manager.update_task(
                task_id, progress=75, message="Enriching citation data..."
            )
            self._enrich_citations(enriched_papers)

            # Stage 5: STORE
            self.task_manager.update_task(
                task_id, progress=85, message="Storing papers..."
            )
            stored_count = self._store(enriched_papers)

            # Stage 6: ZEP GRAPH (optional — only if Zep is configured)
            zep_graph_id = None
            if Config.ZEP_API_KEY:
                self.task_manager.update_task(
                    task_id, progress=90, message="Populating Zep knowledge graph..."
                )
                zep_graph_id = self._populate_zep_graph(enriched_papers, query)

            self.task_manager.complete_task(task_id, result={
                "papers_ingested": stored_count,
                "papers_skipped": len(all_metadata) - stored_count,
                "total_fetched": len(all_metadata),
                "zep_graph_id": zep_graph_id,
                "store_stats": self.store.stats(),
            })

        except Exception as e:
            logger.exception(f"Ingestion pipeline failed: {e}")
            self.task_manager.fail_task(task_id, str(e))

    def _fetch(
        self,
        query: str,
        sources: List[str],
        date_from: Optional[str],
        date_to: Optional[str],
        max_results: int,
    ) -> List[PaperMetadata]:
        """Stage 1: Fetch papers from all requested sources."""
        all_results = []
        if not sources:
            return all_results

        valid_sources = []
        for source_name in sources:
            try:
                valid_sources.append(AcademicSource(source_name))
            except ValueError:
                logger.warning(f"Skipping unsupported source '{source_name}'")

        if not valid_sources:
            return all_results

        per_source_limit = max(1, math.ceil(max_results / len(valid_sources)))
        executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=min(len(valid_sources), self.MAX_FETCH_WORKERS)
        )
        futures = {
            executor.submit(
                self._fetch_single_source,
                query,
                source_enum,
                date_from,
                date_to,
                per_source_limit,
            ): source_enum
            for source_enum in valid_sources
        }

        try:
            for future in concurrent.futures.as_completed(
                futures, timeout=self.FETCH_TIMEOUT_SECONDS + 15
            ):
                source_enum = futures[future]
                try:
                    fetch_result = future.result()
                except Exception as e:
                    logger.warning(f"Failed to fetch from {source_enum.value}: {e}")
                    continue

                all_results.extend(fetch_result["results"])
                cache_state = "cache hit" if fetch_result["cached"] else "live fetch"
                logger.info(
                    "Fetched %s papers from %s (%s, date_from=%s)",
                    len(fetch_result["results"]),
                    source_enum.value,
                    cache_state,
                    fetch_result["effective_date_from"] or "none",
                )
        except concurrent.futures.TimeoutError:
            for future, source_enum in futures.items():
                if not future.done():
                    logger.warning(
                        "Timed out fetching from %s after %ss",
                        source_enum.value,
                        self.FETCH_TIMEOUT_SECONDS,
                    )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        # Respect the caller's max_results limit across all sources
        if len(all_results) > max_results:
            all_results = all_results[:max_results]

        return all_results

    @staticmethod
    def _normalize_query(query: str) -> str:
        return " ".join(query.lower().split())

    def _build_cache_key(
        self,
        query: str,
        source: AcademicSource,
        date_from: Optional[str],
        date_to: Optional[str],
        max_results: int,
    ) -> str:
        raw_key = "|".join(
            [
                self._normalize_query(query),
                source.value,
                date_from or "",
                date_to or "",
                str(max_results),
            ]
        )
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def _resolve_effective_date_from(
        self,
        query: str,
        source: AcademicSource,
        explicit_date_from: Optional[str],
    ) -> Optional[str]:
        if explicit_date_from:
            return explicit_date_from
        normalized_query = self._normalize_query(query)
        return self.store.get_high_water_mark(source.value, normalized_query)

    def _fetch_single_source(
        self,
        query: str,
        source: AcademicSource,
        date_from: Optional[str],
        date_to: Optional[str],
        max_results: int,
    ) -> Dict[str, Any]:
        normalized_query = self._normalize_query(query)
        effective_date_from = self._resolve_effective_date_from(query, source, date_from)
        cache_key = self._build_cache_key(
            query=query,
            source=source,
            date_from=effective_date_from,
            date_to=date_to,
            max_results=max_results,
        )
        cache_entry = self.store.get_ingestion_cache(cache_key)
        if cache_entry:
            return {
                "source": source.value,
                "results": [PaperMetadata.from_dict(item) for item in cache_entry["payload"]],
                "cached": True,
                "effective_date_from": effective_date_from,
            }

        adapter = get_source(source)
        results = adapter.search(query, effective_date_from, date_to, max_results)

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=self.CACHE_TTL_HOURS.get(source, 24))
        self.store.set_ingestion_cache(
            cache_key=cache_key,
            query=normalized_query,
            source=source.value,
            date_from=effective_date_from or "",
            date_to=date_to or "",
            max_results=max_results,
            payload=[result.to_dict() for result in results],
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
        )

        latest_publication_date = max(
            (result.publication_date for result in results if result.publication_date and result.publication_date.strip()),
            default="",
        )
        if latest_publication_date and latest_publication_date.strip():
            self.store.update_high_water_mark(
                source=source.value,
                query=normalized_query,
                publication_date=latest_publication_date,
                fetched_at=now.isoformat(),
            )

        return {
            "source": source.value,
            "results": results,
            "cached": False,
            "effective_date_from": effective_date_from,
        }

    def _parse(self, metadata_list: List[PaperMetadata]) -> List[Paper]:
        """Stage 2: Deduplicate by DOI, normalize, create Paper objects."""
        seen_dois = set()
        papers = []

        for m in metadata_list:
            doi = m.doi.strip()
            if not doi or doi in seen_dois:
                continue
            if self.store.paper_exists(doi):
                seen_dois.add(doi)
                continue
            seen_dois.add(doi)

            paper = Paper(
                paper_id="",
                doi=doi,
                title=m.title.strip(),
                abstract=m.abstract.strip(),
                authors=m.authors,
                publication_date=m.publication_date,
                source=m.source,
                keywords=m.keywords,
                citation_count=m.citation_count,
                references=m.references,
                full_text_url=m.full_text_url,
                status=IngestionStatus.PARSED,
                metadata=m.metadata,
            )
            papers.append(paper)

        logger.info(f"Parsed {len(papers)} new papers (deduped from {len(metadata_list)})")
        return papers

    def _extract_entities(self, papers: List[Paper], task_id: str) -> List[Paper]:
        """Stage 3: Use LLM to extract structured entities from abstracts."""
        try:
            llm = LLMClient()
        except ValueError:
            logger.warning("LLM not configured — skipping entity extraction")
            for p in papers:
                p.status = IngestionStatus.EXTRACTED
            return papers

        for i, paper in enumerate(papers):
            if not paper.abstract:
                paper.status = IngestionStatus.EXTRACTED
                continue

            try:
                prompt = ENTITY_EXTRACTION_PROMPT.format(
                    title=paper.title, abstract=paper.abstract[:2000]
                )
                result = llm.chat_json(
                    messages=[
                        {"role": "system", "content": "You are an academic research analyst."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                )

                # Merge extracted keywords with existing ones
                extracted_kw = result.get("keywords", [])
                paper.keywords = list(set(paper.keywords + extracted_kw))

                # Store extraction results in metadata
                paper.metadata["extracted"] = {
                    "methods": result.get("methods", []),
                    "findings": result.get("findings", []),
                    "research_questions": result.get("research_questions", []),
                    "domain": result.get("domain", ""),
                    "subfield": result.get("subfield", ""),
                }
                paper.status = IngestionStatus.EXTRACTED

            except Exception as e:
                logger.warning(f"Entity extraction failed for {paper.doi}: {e}")
                paper.status = IngestionStatus.EXTRACTED  # Continue despite failure

            # Update progress within extraction stage (50% → 75%)
            if i % 10 == 0:
                pct = 50 + int(25 * (i / max(len(papers), 1)))
                self.task_manager.update_task(
                    task_id, progress=pct,
                    message=f"Extracting entities... ({i+1}/{len(papers)})",
                )

        return papers

    def _enrich_citations(self, papers: List[Paper]):
        """Stage 4: Cross-reference citations between ingested papers."""
        doi_to_paper_id = {}
        for p in papers:
            doi_to_paper_id[p.doi] = p.paper_id
        # Also include already-stored papers
        for existing in self.store.list_papers(limit=10000):
            doi_to_paper_id[existing.doi] = existing.paper_id

        for paper in papers:
            for ref_doi in paper.references:
                if ref_doi in doi_to_paper_id:
                    self.store.add_citation(Citation(
                        citing_paper_id=paper.paper_id,
                        cited_paper_id=doi_to_paper_id[ref_doi],
                        context="",
                    ))
            paper.status = IngestionStatus.ENRICHED

    def _store(self, papers: List[Paper]) -> int:
        """Stage 5: Persist papers to the data store."""
        count = 0
        for paper in papers:
            paper.status = IngestionStatus.STORED
            self.store.add_paper(paper)
            count += 1
        logger.info(f"Stored {count} papers")
        return count

    def _populate_zep_graph(self, papers: List[Paper], query: str) -> Optional[str]:
        """
        Stage 6: Push paper entities into a Zep knowledge graph.
        Creates a research-specific graph with ontology for papers, authors,
        topics, and their relationships. Each paper abstract is added as an
        episode so Zep extracts entities and edges automatically.
        """
        try:
            from zep_cloud.client import Zep
            from zep_cloud import EpisodeData
        except ImportError:
            logger.warning("zep_cloud not installed — skipping Zep graph population")
            return None

        try:
            client = Zep(api_key=Config.ZEP_API_KEY)

            # Create a research graph
            graph_id = f"ossr_{uuid.uuid4().hex[:12]}"
            client.graph.create(
                graph_id=graph_id,
                name=f"OSSR: {query[:60]}",
                description=f"Research knowledge graph for query: {query}",
            )

            # Set research-specific ontology
            self._set_research_ontology(client, graph_id)

            # Add paper abstracts as episodes in batches
            batch_size = 5
            episode_uuids = []
            for i in range(0, len(papers), batch_size):
                batch = papers[i : i + batch_size]
                episodes = []
                for paper in batch:
                    # Compose a rich text episode from paper metadata
                    authors_str = ", ".join(
                        a.get("name", "") for a in paper.authors[:5]
                    )
                    extracted = paper.metadata.get("extracted", {})
                    methods = ", ".join(extracted.get("methods", []))
                    findings = "; ".join(extracted.get("findings", []))

                    episode_text = (
                        f"Paper: {paper.title}\n"
                        f"Authors: {authors_str}\n"
                        f"DOI: {paper.doi}\n"
                        f"Date: {paper.publication_date}\n"
                        f"Keywords: {', '.join(paper.keywords[:10])}\n"
                    )
                    if methods:
                        episode_text += f"Methods: {methods}\n"
                    if findings:
                        episode_text += f"Findings: {findings}\n"
                    episode_text += f"Abstract: {paper.abstract[:1500]}\n"

                    ep_uuid = str(uuid.uuid4())
                    episodes.append(
                        EpisodeData(
                            episode_id=ep_uuid,
                            content=episode_text,
                            source="OSSR Academic Ingestion",
                            source_description=f"Paper from {paper.source.value}",
                        )
                    )
                    episode_uuids.append(ep_uuid)

                if episodes:
                    client.graph.add_batch(
                        graph_id=graph_id,
                        episodes=episodes,
                    )
                    time.sleep(0.5)  # Rate limit

            logger.info(
                f"Zep graph '{graph_id}' populated with {len(episode_uuids)} episodes"
            )
            return graph_id

        except Exception as e:
            logger.warning(f"Zep graph population failed (non-fatal): {e}")
            return None

    @staticmethod
    def _set_research_ontology(client, graph_id: str):
        """Set a research-domain ontology on the Zep graph."""
        import warnings
        from typing import Optional as Opt
        from pydantic import Field

        warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

        try:
            from zep_cloud.external_clients.ontology import (
                EntityModel,
                EntityText,
                EdgeModel,
            )
            from zep_cloud import EntityEdgeSourceTarget
        except ImportError:
            logger.warning("Zep ontology classes not available — using default ontology")
            return

        # Entity types
        class ResearchPaper(EntityModel):
            """A published academic paper or preprint."""
            doi: Opt[EntityText] = Field(description="Digital Object Identifier", default=None)
            publication_date: Opt[EntityText] = Field(description="Publication date", default=None)
            entity_source: Opt[EntityText] = Field(description="Academic source (bioRxiv, arXiv, etc.)", default=None)

        class Researcher(EntityModel):
            """An author or researcher."""
            affiliation: Opt[EntityText] = Field(description="Institutional affiliation", default=None)

        class ResearchTopic(EntityModel):
            """A research topic, method, or concept."""
            topic_level: Opt[EntityText] = Field(description="Hierarchy level: domain, subfield, or thread", default=None)

        class Method(EntityModel):
            """A research methodology or technique."""
            pass

        # Edge types
        class AuthoredBy(EdgeModel):
            """A paper authored by a researcher."""
            pass

        class Cites(EdgeModel):
            """One paper cites another."""
            pass

        class InvestigatesTopic(EdgeModel):
            """A paper investigates a research topic."""
            pass

        class UseMethod(EdgeModel):
            """A paper uses a method."""
            pass

        class CollaboratesWith(EdgeModel):
            """Two researchers collaborate."""
            pass

        entity_types = {
            "ResearchPaper": ResearchPaper,
            "Researcher": Researcher,
            "ResearchTopic": ResearchTopic,
            "Method": Method,
        }

        edge_definitions = {
            "authored_by": (
                AuthoredBy,
                [EntityEdgeSourceTarget(source="ResearchPaper", target="Researcher")],
            ),
            "cites": (
                Cites,
                [EntityEdgeSourceTarget(source="ResearchPaper", target="ResearchPaper")],
            ),
            "investigates_topic": (
                InvestigatesTopic,
                [EntityEdgeSourceTarget(source="ResearchPaper", target="ResearchTopic")],
            ),
            "uses_method": (
                UseMethod,
                [EntityEdgeSourceTarget(source="ResearchPaper", target="Method")],
            ),
            "collaborates_with": (
                CollaboratesWith,
                [EntityEdgeSourceTarget(source="Researcher", target="Researcher")],
            ),
        }

        client.graph.set_ontology(
            graph_ids=[graph_id],
            entities=entity_types,
            edges=edge_definitions,
        )
