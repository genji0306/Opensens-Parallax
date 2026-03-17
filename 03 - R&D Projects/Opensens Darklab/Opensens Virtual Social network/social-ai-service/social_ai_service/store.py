from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any, Dict, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SocialPostStore:
    def __init__(self, db_path: Optional[str] = None):
        default_path = Path(__file__).resolve().parents[1] / "data" / "social_ai.db"
        self.db_path = Path(db_path) if db_path else default_path
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = getattr(self._local, "connection", None)
        if conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            self._local.connection = conn
        return conn

    def _init_db(self):
        conn = self._get_connection()
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS post_jobs (
                job_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                action TEXT NOT NULL,
                state TEXT NOT NULL,
                author TEXT NOT NULL DEFAULT '',
                content TEXT NOT NULL DEFAULT '',
                media_urls TEXT NOT NULL DEFAULT '[]',
                scheduled_for TEXT NOT NULL DEFAULT '',
                external_id TEXT NOT NULL DEFAULT '',
                metadata TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL DEFAULT '',
                updated_at TEXT NOT NULL DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_post_jobs_platform ON post_jobs(platform);
            CREATE INDEX IF NOT EXISTS idx_post_jobs_state ON post_jobs(state);
            CREATE INDEX IF NOT EXISTS idx_post_jobs_created_at ON post_jobs(created_at DESC);
            """
        )
        conn.commit()

    def create_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO post_jobs
            (job_id, platform, action, state, author, content, media_urls, scheduled_for,
             external_id, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["job_id"],
                job["platform"],
                job["action"],
                job["state"],
                job.get("author", ""),
                job.get("content", ""),
                json.dumps(job.get("media_urls") or []),
                job.get("scheduled_for", ""),
                job.get("external_id", ""),
                json.dumps(job.get("metadata") or {}),
                job["created_at"],
                job["updated_at"],
            ),
        )
        conn.commit()
        return self.get_job(job["job_id"])

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_connection()
        row = conn.execute("SELECT * FROM post_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def list_jobs(
        self,
        platform: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        conn = self._get_connection()
        query = "SELECT * FROM post_jobs WHERE 1=1"
        params: List[Any] = []

        if platform:
            query += " AND platform = ?"
            params.append(platform)
        if state:
            query += " AND state = ?"
            params.append(state)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [self._row_to_job(row) for row in rows]

    @staticmethod
    def _row_to_job(row: sqlite3.Row) -> Dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "platform": row["platform"],
            "action": row["action"],
            "state": row["state"],
            "author": row["author"],
            "content": row["content"],
            "media_urls": json.loads(row["media_urls"]),
            "scheduled_for": row["scheduled_for"] or None,
            "external_id": row["external_id"],
            "metadata": json.loads(row["metadata"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
