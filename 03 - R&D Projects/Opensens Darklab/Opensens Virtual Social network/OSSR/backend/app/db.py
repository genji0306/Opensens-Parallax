"""
OSSR SQLite Database Module
Connection factory, schema initialization, and WAL mode configuration.
"""

import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "ossr.db"

# Thread-local storage for connections
_local = threading.local()


def get_connection() -> sqlite3.Connection:
    """
    Return a thread-local SQLite connection with Row factory and WAL mode.
    Each thread gets its own connection (SQLite requirement for thread safety).
    """
    conn = getattr(_local, "connection", None)
    if conn is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.connection = conn
    return conn


def init_db():
    """Create all tables and indexes if they don't exist. Called once at app startup."""
    conn = get_connection()
    conn.executescript("""
        -- Core research data (fully normalized for filtered queries)

        CREATE TABLE IF NOT EXISTS papers (
            paper_id TEXT PRIMARY KEY,
            doi TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            abstract TEXT NOT NULL DEFAULT '',
            authors TEXT NOT NULL DEFAULT '[]',
            publication_date TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'biorxiv',
            keywords TEXT NOT NULL DEFAULT '[]',
            topics TEXT NOT NULL DEFAULT '[]',
            citation_count INTEGER NOT NULL DEFAULT 0,
            references_list TEXT NOT NULL DEFAULT '[]',
            full_text_url TEXT,
            status TEXT NOT NULL DEFAULT 'fetched',
            ingested_at TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT '{}'
        );

        CREATE TABLE IF NOT EXISTS topics (
            topic_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            level INTEGER NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            parent_id TEXT,
            paper_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (parent_id) REFERENCES topics(topic_id)
        );

        CREATE TABLE IF NOT EXISTS paper_topics (
            paper_id TEXT NOT NULL,
            topic_id TEXT NOT NULL,
            relevance_score REAL NOT NULL DEFAULT 0.0,
            PRIMARY KEY (paper_id, topic_id),
            FOREIGN KEY (paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE,
            FOREIGN KEY (topic_id) REFERENCES topics(topic_id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS citations (
            citing_paper_id TEXT NOT NULL,
            cited_paper_id TEXT NOT NULL,
            context TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (citing_paper_id, cited_paper_id)
        );

        -- JSON-blob stores (simple get/add/list operations)

        CREATE TABLE IF NOT EXISTS researcher_profiles (
            agent_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS simulations (
            simulation_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reports (
            report_id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ingestion_cache (
            cache_key TEXT PRIMARY KEY,
            query TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            date_from TEXT NOT NULL DEFAULT '',
            date_to TEXT NOT NULL DEFAULT '',
            max_results INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT '',
            expires_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS ingestion_high_water_marks (
            source TEXT NOT NULL,
            query TEXT NOT NULL DEFAULT '',
            last_publication_date TEXT NOT NULL DEFAULT '',
            last_fetched_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (source, query)
        );

        -- API key authentication

        CREATE TABLE IF NOT EXISTS api_keys (
            key_hash TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT '',
            expires_at TEXT NOT NULL DEFAULT '',
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_api_keys_name ON api_keys(name);

        -- Debate sessions (Agent Office visual mode link)

        CREATE TABLE IF NOT EXISTS debate_sessions (
            debate_id TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'text',
            shared_config TEXT NOT NULL DEFAULT '{}',
            social_posts TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT '{}',
            FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id)
        );

        -- Debate feedback from scientific community

        CREATE TABLE IF NOT EXISTS debate_feedback (
            feedback_id TEXT PRIMARY KEY,
            debate_id TEXT NOT NULL,
            author_name TEXT NOT NULL DEFAULT '',
            affiliation TEXT NOT NULL DEFAULT '',
            comment TEXT NOT NULL DEFAULT '',
            rating INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (debate_id) REFERENCES debate_sessions(debate_id)
        );

        -- Indexes for common query patterns

        CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
        CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source);
        CREATE INDEX IF NOT EXISTS idx_papers_status ON papers(status);
        CREATE INDEX IF NOT EXISTS idx_papers_ingested ON papers(ingested_at DESC);
        CREATE INDEX IF NOT EXISTS idx_topics_level ON topics(level);
        CREATE INDEX IF NOT EXISTS idx_topics_parent ON topics(parent_id);
        CREATE INDEX IF NOT EXISTS idx_pt_topic ON paper_topics(topic_id);
        CREATE INDEX IF NOT EXISTS idx_citations_cited ON citations(cited_paper_id);
        CREATE INDEX IF NOT EXISTS idx_ingestion_cache_lookup ON ingestion_cache(source, query, expires_at);
        CREATE INDEX IF NOT EXISTS idx_ingestion_hwm_lookup ON ingestion_high_water_marks(source, query);
    """)
    conn.commit()


def close_connection():
    """Close the thread-local connection if it exists."""
    conn = getattr(_local, "connection", None)
    if conn is not None:
        conn.close()
        _local.connection = None
