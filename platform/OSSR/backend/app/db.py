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

        -- ═══════════════════════════════════════════════════════════════
        -- Mirofish Research Console tables (Orchestrator / Graph / Score)
        -- ═══════════════════════════════════════════════════════════════

        -- Graph events: append-only log of all graph mutations
        CREATE TABLE IF NOT EXISTS graph_events (
            event_id TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            turn_id INTEGER,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL DEFAULT '{}',
            timestamp TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id)
        );

        CREATE INDEX IF NOT EXISTS idx_graph_events_sim_round
            ON graph_events(simulation_id, round_num);

        -- Graph snapshots: full graph state per round
        CREATE TABLE IF NOT EXISTS graph_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            nodes TEXT NOT NULL DEFAULT '[]',
            edges TEXT NOT NULL DEFAULT '[]',
            clusters TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id),
            UNIQUE(simulation_id, round_num)
        );

        -- Debate frames: orchestrator pre-debate structured output
        CREATE TABLE IF NOT EXISTS debate_frames (
            frame_id TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            topic TEXT NOT NULL DEFAULT '',
            frame_data TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id)
        );

        -- Scoreboards: per-round scoring state
        CREATE TABLE IF NOT EXISTS scoreboards (
            scoreboard_id TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            scoreboard_data TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id),
            UNIQUE(simulation_id, round_num)
        );

        -- Analyst feed: per-round narrative explanations
        CREATE TABLE IF NOT EXISTS analyst_feed (
            feed_id TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            narrative TEXT NOT NULL DEFAULT '',
            key_events TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id),
            UNIQUE(simulation_id, round_num)
        );

        -- Agent stances: per agent per option per round
        CREATE TABLE IF NOT EXISTS agent_stances (
            stance_id TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            agent_id TEXT NOT NULL,
            option_id TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            position REAL NOT NULL DEFAULT 0.0,
            confidence REAL NOT NULL DEFAULT 0.5,
            reasoning TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id),
            UNIQUE(simulation_id, agent_id, option_id, round_num)
        );

        CREATE INDEX IF NOT EXISTS idx_agent_stances_sim_round
            ON agent_stances(simulation_id, round_num);

        -- LLM response cache for cost optimization
        CREATE TABLE IF NOT EXISTS llm_cache (
            cache_key TEXT PRIMARY KEY,
            response TEXT NOT NULL DEFAULT '',
            model TEXT NOT NULL DEFAULT '',
            tokens_in INTEGER NOT NULL DEFAULT 0,
            tokens_out INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT '',
            ttl_seconds INTEGER NOT NULL DEFAULT 86400
        );

        -- Session snapshots for research → live mode handoff
        CREATE TABLE IF NOT EXISTS session_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            simulation_id TEXT NOT NULL,
            snapshot_data TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT '',
            FOREIGN KEY (simulation_id) REFERENCES simulations(simulation_id)
        );

        -- ═══════════════════════════════════════════════════════════════
        -- Agent AiS tables (AI Scientist pipeline)
        -- ═══════════════════════════════════════════════════════════════

        CREATE TABLE IF NOT EXISTS research_ideas (
            idea_id TEXT PRIMARY KEY,
            set_id TEXT NOT NULL,
            run_id TEXT,
            data TEXT NOT NULL,
            score REAL NOT NULL DEFAULT 0.0,
            created_at TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_research_ideas_set ON research_ideas(set_id);
        CREATE INDEX IF NOT EXISTS idx_research_ideas_run ON research_ideas(run_id);

        CREATE TABLE IF NOT EXISTS paper_drafts (
            draft_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            data TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS ais_pipeline_runs (
            run_id TEXT PRIMARY KEY,
            research_idea TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            current_stage INTEGER NOT NULL DEFAULT 1,
            stage_results TEXT NOT NULL DEFAULT '{}',
            config TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            error TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_ais_runs_status ON ais_pipeline_runs(status);

        CREATE TABLE IF NOT EXISTS experiment_specs (
            spec_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            idea_id TEXT NOT NULL,
            template TEXT NOT NULL DEFAULT '',
            seed_ideas TEXT NOT NULL DEFAULT '[]',
            config TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS experiment_results (
            result_id TEXT PRIMARY KEY,
            spec_id TEXT NOT NULL,
            run_id TEXT NOT NULL,
            metrics TEXT NOT NULL DEFAULT '{}',
            artifacts TEXT NOT NULL DEFAULT '[]',
            log_summary TEXT NOT NULL DEFAULT '',
            paper_path TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            started_at TEXT,
            completed_at TEXT,
            error TEXT
        );

        CREATE TABLE IF NOT EXISTS autoresearch_runs (
            auto_run_id TEXT PRIMARY KEY,
            idea_id TEXT NOT NULL,
            run_id TEXT,
            node TEXT NOT NULL DEFAULT 'local',
            branch TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'queued',
            iterations INTEGER NOT NULL DEFAULT 0,
            best_metric REAL,
            metric_name TEXT NOT NULL DEFAULT 'val_bpb',
            results_tsv TEXT NOT NULL DEFAULT '',
            config TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT '',
            error TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_autoresearch_status ON autoresearch_runs(status);
        CREATE INDEX IF NOT EXISTS idx_experiment_specs_run ON experiment_specs(run_id);
        CREATE INDEX IF NOT EXISTS idx_experiment_results_spec ON experiment_results(spec_id);

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
