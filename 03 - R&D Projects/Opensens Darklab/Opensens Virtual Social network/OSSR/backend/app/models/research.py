"""
OSSR Research Data Models
Paper, Topic, Citation, and PaperTopic models for academic data.
Uses dataclass pattern consistent with existing SocialSense models.
SQLite-backed persistence via app.db module.
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

from ..db import get_connection


class AcademicSource(str, Enum):
    """Academic data source identifiers."""
    BIORXIV = "biorxiv"
    MEDRXIV = "medrxiv"
    ARXIV = "arxiv"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    PUBMED = "pubmed"
    OPENALEX = "openalex"
    OPENREVIEW = "openreview"


class TopicLevel(int, Enum):
    """Topic hierarchy levels."""
    DOMAIN = 1       # e.g., Neuroscience, Materials Science
    SUBFIELD = 2     # e.g., Neural Interfaces, EIS
    THREAD = 3       # e.g., "Wearable EIT for cardiac monitoring"


class IngestionStatus(str, Enum):
    """Paper ingestion pipeline status."""
    FETCHED = "fetched"
    PARSED = "parsed"
    EXTRACTED = "extracted"
    ENRICHED = "enriched"
    STORED = "stored"
    FAILED = "failed"


@dataclass
class Paper:
    """Academic paper record."""
    paper_id: str
    doi: str
    title: str
    abstract: str
    authors: List[Dict[str, str]]   # [{"name": "...", "affiliation": "..."}]
    publication_date: str            # ISO format YYYY-MM-DD
    source: AcademicSource
    keywords: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)     # LLM-assigned topic IDs
    citation_count: int = 0
    references: List[str] = field(default_factory=list)  # list of DOIs
    full_text_url: Optional[str] = None
    status: IngestionStatus = IngestionStatus.FETCHED
    ingested_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.paper_id:
            self.paper_id = str(uuid.uuid4())
        if not self.ingested_at:
            self.ingested_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "doi": self.doi,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "publication_date": self.publication_date,
            "source": self.source.value if isinstance(self.source, AcademicSource) else self.source,
            "keywords": self.keywords,
            "topics": self.topics,
            "citation_count": self.citation_count,
            "references": self.references,
            "full_text_url": self.full_text_url,
            "status": self.status.value if isinstance(self.status, IngestionStatus) else self.status,
            "ingested_at": self.ingested_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Paper':
        source = data.get("source", "biorxiv")
        if isinstance(source, str):
            try:
                source = AcademicSource(source)
            except ValueError:
                source = AcademicSource.BIORXIV

        status = data.get("status", "fetched")
        if isinstance(status, str):
            try:
                status = IngestionStatus(status)
            except ValueError:
                status = IngestionStatus.FETCHED

        return cls(
            paper_id=data.get("paper_id", ""),
            doi=data["doi"],
            title=data.get("title", ""),
            abstract=data.get("abstract", ""),
            authors=data.get("authors", []),
            publication_date=data.get("publication_date", ""),
            source=source,
            keywords=data.get("keywords", []),
            topics=data.get("topics", []),
            citation_count=data.get("citation_count", 0),
            references=data.get("references", []),
            full_text_url=data.get("full_text_url"),
            status=status,
            ingested_at=data.get("ingested_at", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Topic:
    """Research topic in the hierarchical tree."""
    topic_id: str
    name: str
    level: TopicLevel
    description: str = ""
    parent_id: Optional[str] = None
    paper_count: int = 0
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.topic_id:
            self.topic_id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic_id": self.topic_id,
            "name": self.name,
            "level": self.level.value if isinstance(self.level, TopicLevel) else self.level,
            "description": self.description,
            "parent_id": self.parent_id,
            "paper_count": self.paper_count,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Topic':
        level = data.get("level", 1)
        if isinstance(level, int):
            level = TopicLevel(level)
        return cls(
            topic_id=data.get("topic_id", ""),
            name=data["name"],
            level=level,
            description=data.get("description", ""),
            parent_id=data.get("parent_id"),
            paper_count=data.get("paper_count", 0),
            created_at=data.get("created_at", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class PaperTopic:
    """Junction: links a paper to a topic with relevance score."""
    paper_id: str
    topic_id: str
    relevance_score: float = 0.0  # 0.0 to 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "paper_id": self.paper_id,
            "topic_id": self.topic_id,
            "relevance_score": self.relevance_score,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PaperTopic':
        return cls(
            paper_id=data["paper_id"],
            topic_id=data["topic_id"],
            relevance_score=data.get("relevance_score", 0.0),
        )


@dataclass
class Citation:
    """Citation relationship between two papers."""
    citing_paper_id: str
    cited_paper_id: str
    context: str = ""  # text surrounding the citation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "citing_paper_id": self.citing_paper_id,
            "cited_paper_id": self.cited_paper_id,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Citation':
        return cls(
            citing_paper_id=data["citing_paper_id"],
            cited_paper_id=data["cited_paper_id"],
            context=data.get("context", ""),
        )


class ResearchDataStore:
    """
    SQLite-backed store for OSSR research data.
    Singleton pattern — same API surface as the original in-memory version.
    Thread-safe via SQLite WAL mode + thread-local connections.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # --- Helpers ---

    @staticmethod
    def _row_to_paper(row) -> Paper:
        return Paper(
            paper_id=row["paper_id"],
            doi=row["doi"],
            title=row["title"],
            abstract=row["abstract"],
            authors=json.loads(row["authors"]),
            publication_date=row["publication_date"],
            source=AcademicSource(row["source"]) if row["source"] else AcademicSource.BIORXIV,
            keywords=json.loads(row["keywords"]),
            topics=json.loads(row["topics"]),
            citation_count=row["citation_count"],
            references=json.loads(row["references_list"]),
            full_text_url=row["full_text_url"],
            status=IngestionStatus(row["status"]) if row["status"] else IngestionStatus.FETCHED,
            ingested_at=row["ingested_at"],
            metadata=json.loads(row["metadata"]),
        )

    @staticmethod
    def _row_to_topic(row) -> 'Topic':
        return Topic(
            topic_id=row["topic_id"],
            name=row["name"],
            level=TopicLevel(row["level"]),
            description=row["description"],
            parent_id=row["parent_id"],
            paper_count=row["paper_count"],
            created_at=row["created_at"],
            metadata=json.loads(row["metadata"]),
        )

    # --- Papers ---

    def add_paper(self, paper: Paper) -> Paper:
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO papers
               (paper_id, doi, title, abstract, authors, publication_date,
                source, keywords, topics, citation_count, references_list,
                full_text_url, status, ingested_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                paper.paper_id, paper.doi, paper.title, paper.abstract,
                json.dumps(paper.authors), paper.publication_date,
                paper.source.value if isinstance(paper.source, AcademicSource) else paper.source,
                json.dumps(paper.keywords), json.dumps(paper.topics),
                paper.citation_count, json.dumps(paper.references),
                paper.full_text_url,
                paper.status.value if isinstance(paper.status, IngestionStatus) else paper.status,
                paper.ingested_at, json.dumps(paper.metadata),
            ),
        )
        conn.commit()
        return paper

    def update_paper(self, paper: Paper) -> Paper:
        """Update an existing paper. Use when services mutate paper fields in-place."""
        return self.add_paper(paper)  # INSERT OR REPLACE handles upsert

    def get_paper(self, doi: str) -> Optional[Paper]:
        conn = get_connection()
        row = conn.execute("SELECT * FROM papers WHERE doi = ?", (doi,)).fetchone()
        return self._row_to_paper(row) if row else None

    def get_paper_by_id(self, paper_id: str) -> Optional[Paper]:
        conn = get_connection()
        row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
        return self._row_to_paper(row) if row else None

    def list_papers(
        self,
        source: Optional[AcademicSource] = None,
        status: Optional[IngestionStatus] = None,
        topic_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Paper]:
        conn = get_connection()
        query = "SELECT * FROM papers WHERE 1=1"
        params: list = []

        if source:
            query += " AND source = ?"
            params.append(source.value if isinstance(source, AcademicSource) else source)
        if status:
            query += " AND status = ?"
            params.append(status.value if isinstance(status, IngestionStatus) else status)
        if topic_id:
            query += " AND paper_id IN (SELECT paper_id FROM paper_topics WHERE topic_id = ?)"
            params.append(topic_id)

        query += " ORDER BY ingested_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_paper(r) for r in rows]

    def paper_count(self) -> int:
        conn = get_connection()
        return conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]

    def paper_exists(self, doi: str) -> bool:
        conn = get_connection()
        row = conn.execute("SELECT 1 FROM papers WHERE doi = ? LIMIT 1", (doi,)).fetchone()
        return row is not None

    # --- Topics ---

    def add_topic(self, topic: Topic) -> Topic:
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO topics
               (topic_id, name, level, description, parent_id, paper_count, created_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                topic.topic_id, topic.name,
                topic.level.value if isinstance(topic.level, TopicLevel) else topic.level,
                topic.description, topic.parent_id, topic.paper_count,
                topic.created_at, json.dumps(topic.metadata),
            ),
        )
        conn.commit()
        return topic

    def get_topic(self, topic_id: str) -> Optional[Topic]:
        conn = get_connection()
        row = conn.execute("SELECT * FROM topics WHERE topic_id = ?", (topic_id,)).fetchone()
        return self._row_to_topic(row) if row else None

    def list_topics(
        self,
        level: Optional[TopicLevel] = None,
        parent_id: Optional[str] = None,
    ) -> List[Topic]:
        conn = get_connection()
        query = "SELECT * FROM topics WHERE 1=1"
        params: list = []

        if level is not None:
            query += " AND level = ?"
            params.append(level.value if isinstance(level, TopicLevel) else level)
        if parent_id is not None:
            query += " AND parent_id = ?"
            params.append(parent_id)

        query += " ORDER BY paper_count DESC"
        rows = conn.execute(query, params).fetchall()
        return [self._row_to_topic(r) for r in rows]

    def get_topic_tree(self) -> List[Dict[str, Any]]:
        """Return hierarchical topic tree (Level 1 -> 2 -> 3)."""
        domains = self.list_topics(level=TopicLevel.DOMAIN)
        tree = []
        for domain in domains:
            d = domain.to_dict()
            subfields = self.list_topics(parent_id=domain.topic_id)
            d["children"] = []
            for sf in subfields:
                sf_dict = sf.to_dict()
                threads = self.list_topics(parent_id=sf.topic_id)
                sf_dict["children"] = [t.to_dict() for t in threads]
                d["children"].append(sf_dict)
            tree.append(d)
        return tree

    # --- Paper-Topic links ---

    def link_paper_topic(self, paper_id: str, topic_id: str, relevance: float = 1.0):
        conn = get_connection()
        result = conn.execute(
            "INSERT OR IGNORE INTO paper_topics (paper_id, topic_id, relevance_score) VALUES (?, ?, ?)",
            (paper_id, topic_id, relevance),
        )
        if result.rowcount > 0:
            conn.execute(
                "UPDATE topics SET paper_count = paper_count + 1 WHERE topic_id = ?",
                (topic_id,),
            )
        conn.commit()

    def get_paper_topics(self, paper_id: str) -> List[PaperTopic]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM paper_topics WHERE paper_id = ?", (paper_id,)
        ).fetchall()
        return [PaperTopic(r["paper_id"], r["topic_id"], r["relevance_score"]) for r in rows]

    def get_topic_papers(self, topic_id: str) -> List[str]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT paper_id FROM paper_topics WHERE topic_id = ?", (topic_id,)
        ).fetchall()
        return [r["paper_id"] for r in rows]

    # --- Citations ---

    def add_citation(self, citation: Citation):
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO citations (citing_paper_id, cited_paper_id, context) VALUES (?, ?, ?)",
            (citation.citing_paper_id, citation.cited_paper_id, citation.context),
        )
        conn.commit()

    def get_citations_for(self, paper_id: str) -> List[Citation]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM citations WHERE cited_paper_id = ?", (paper_id,)
        ).fetchall()
        return [Citation(r["citing_paper_id"], r["cited_paper_id"], r["context"]) for r in rows]

    def get_references_of(self, paper_id: str) -> List[Citation]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM citations WHERE citing_paper_id = ?", (paper_id,)
        ).fetchall()
        return [Citation(r["citing_paper_id"], r["cited_paper_id"], r["context"]) for r in rows]

    def citation_count(self) -> int:
        conn = get_connection()
        return conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]

    # --- Ingestion cache ---

    def get_ingestion_cache(self, cache_key: str, now_iso: Optional[str] = None) -> Optional[Dict[str, Any]]:
        conn = get_connection()
        now_iso = now_iso or datetime.now(timezone.utc).isoformat()
        row = conn.execute(
            """
            SELECT cache_key, query, source, date_from, date_to, max_results,
                   payload, created_at, expires_at
            FROM ingestion_cache
            WHERE cache_key = ? AND expires_at > ?
            """,
            (cache_key, now_iso),
        ).fetchone()
        if not row:
            conn.execute("DELETE FROM ingestion_cache WHERE cache_key = ? AND expires_at <= ?", (cache_key, now_iso))
            conn.commit()
            return None
        return {
            "cache_key": row["cache_key"],
            "query": row["query"],
            "source": row["source"],
            "date_from": row["date_from"],
            "date_to": row["date_to"],
            "max_results": row["max_results"],
            "payload": json.loads(row["payload"]),
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
        }

    def set_ingestion_cache(
        self,
        cache_key: str,
        query: str,
        source: str,
        date_from: str,
        date_to: str,
        max_results: int,
        payload: List[Dict[str, Any]],
        created_at: str,
        expires_at: str,
    ):
        conn = get_connection()
        conn.execute(
            """
            INSERT OR REPLACE INTO ingestion_cache
            (cache_key, query, source, date_from, date_to, max_results, payload, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cache_key,
                query,
                source,
                date_from,
                date_to,
                max_results,
                json.dumps(payload),
                created_at,
                expires_at,
            ),
        )
        conn.commit()

    def get_high_water_mark(self, source: str, query: str) -> Optional[str]:
        conn = get_connection()
        row = conn.execute(
            """
            SELECT last_publication_date
            FROM ingestion_high_water_marks
            WHERE source = ? AND query = ?
            """,
            (source, query),
        ).fetchone()
        if not row or not row["last_publication_date"]:
            return None
        return row["last_publication_date"]

    def update_high_water_mark(
        self,
        source: str,
        query: str,
        publication_date: str,
        fetched_at: Optional[str] = None,
    ):
        if not publication_date:
            return

        conn = get_connection()
        current = conn.execute(
            """
            SELECT last_publication_date
            FROM ingestion_high_water_marks
            WHERE source = ? AND query = ?
            """,
            (source, query),
        ).fetchone()

        latest_publication_date = publication_date
        if current and current["last_publication_date"]:
            latest_publication_date = max(current["last_publication_date"], publication_date)

        conn.execute(
            """
            INSERT OR REPLACE INTO ingestion_high_water_marks
            (source, query, last_publication_date, last_fetched_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                source,
                query,
                latest_publication_date,
                fetched_at or datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()

    # --- Bulk operations ---

    def clear(self):
        """Clear all research data tables."""
        conn = get_connection()
        for table in ("paper_topics", "citations", "papers", "topics"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()

    def stats(self) -> Dict[str, int]:
        conn = get_connection()
        return {
            "papers": conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
            "topics": conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0],
            "paper_topic_links": conn.execute("SELECT COUNT(*) FROM paper_topics").fetchone()[0],
            "citations": conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0],
        }
