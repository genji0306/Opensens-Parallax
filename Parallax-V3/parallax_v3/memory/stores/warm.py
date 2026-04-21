"""
parallax_v3/memory/stores/warm.py
===================================
Pattern #3 — Tiered Memory: WARM tier.

Warm store uses SQLite for durability and sentence-transformers for semantic
retrieval across pipeline stages. Embeddings are stored as BLOB (float32 bytes).

Schema:
  chunks(id TEXT PK, session_id TEXT, scope TEXT, text TEXT, embedding BLOB,
         created_at REAL, metadata TEXT)

Retrieval is cosine similarity via numpy. All operations are async-safe via
asyncio.to_thread for the CPU-bound embedding calls.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import numpy as np

_model = None
_MODEL_NAME = "all-MiniLM-L6-v2"
_FALLBACK_DIM = 256


class _FallbackEmbeddingModel:
    def encode(self, text: str, convert_to_numpy: bool = True, normalize_embeddings: bool = True):
        vec = np.zeros(_FALLBACK_DIM, dtype=np.float32)
        for token in text.lower().split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            slot = int.from_bytes(digest[:4], "big") % _FALLBACK_DIM
            vec[slot] += 1.0
        if normalize_embeddings:
            norm = float(np.linalg.norm(vec))
            if norm:
                vec /= norm
        return vec if convert_to_numpy else vec.tolist()


def _get_model():
    global _model
    if _model is None:
        try:  # pragma: no cover - optional dependency
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415

            _model = SentenceTransformer(_MODEL_NAME)
        except Exception:  # pragma: no cover - fallback path
            _model = _FallbackEmbeddingModel()
    return _model


def _embed(text: str) -> np.ndarray:
    """Synchronous embedding (run inside asyncio.to_thread)."""
    model = _get_model()
    vec = model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
    return np.asarray(vec, dtype=np.float32)


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity for already-normalised vectors (dot product suffices)."""
    return float(np.dot(a, b))


_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS chunks (
    id         TEXT    PRIMARY KEY,
    session_id TEXT    NOT NULL,
    scope      TEXT,
    text       TEXT    NOT NULL,
    embedding  BLOB    NOT NULL,
    created_at REAL    NOT NULL,
    metadata   TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_chunks_session ON chunks(session_id);
CREATE INDEX IF NOT EXISTS idx_chunks_scope   ON chunks(session_id, scope);
"""


class WarmStore:
    """
    SQLite + sentence-transformers warm store for one session.

    Thread model: SQLite connection is created per call (check_same_thread=False
    is fine for concurrent async because all DB calls are inside to_thread).
    """

    def __init__(self, session_id: str, db_dir: Path) -> None:
        self.session_id = session_id
        db_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = db_dir / "warm_store.db"
        # Initialise schema synchronously at construction time
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(_CREATE_TABLE)
            conn.commit()
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def add(
        self,
        key: str,
        text: str,
        *,
        scope: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Embed text and upsert into SQLite."""
        vec = await asyncio.to_thread(_embed, text)
        blob = vec.tobytes()
        meta_str = json.dumps(metadata or {})
        now = time.time()

        def _write() -> None:
            conn = self._connect()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO chunks
                       (id, session_id, scope, text, embedding, created_at, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (key, self.session_id, scope, text, blob, now, meta_str),
                )
                conn.commit()
            finally:
                conn.close()

        await asyncio.to_thread(_write)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        top_k: int = 5,
        scope_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Semantic search: embed query, compute cosine similarity against all stored
        chunks (optionally filtered by scope), return top_k ranked results.
        """
        q_vec = await asyncio.to_thread(_embed, query)

        def _fetch() -> list[sqlite3.Row]:
            conn = self._connect()
            try:
                if scope_filter is not None:
                    cur = conn.execute(
                        "SELECT * FROM chunks WHERE session_id=? AND scope=?",
                        (self.session_id, scope_filter),
                    )
                else:
                    cur = conn.execute(
                        "SELECT * FROM chunks WHERE session_id=?",
                        (self.session_id,),
                    )
                return cur.fetchall()
            finally:
                conn.close()

        rows = await asyncio.to_thread(_fetch)
        if not rows:
            return []

        scored: list[tuple[float, sqlite3.Row]] = []
        for row in rows:
            stored_vec = np.frombuffer(row["embedding"], dtype=np.float32)
            score = _cosine(q_vec, stored_vec)
            scored.append((score, row))

        scored.sort(key=lambda x: x[0], reverse=True)

        return [
            {
                "key": row["id"],
                "score": score,
                "text": row["text"],
                "scope": row["scope"],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"],
            }
            for score, row in scored[:top_k]
        ]

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    async def count(self, scope_filter: str | None = None) -> int:
        def _count() -> int:
            conn = self._connect()
            try:
                if scope_filter:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM chunks WHERE session_id=? AND scope=?",
                        (self.session_id, scope_filter),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM chunks WHERE session_id=?",
                        (self.session_id,),
                    ).fetchone()
                return row[0]
            finally:
                conn.close()

        return await asyncio.to_thread(_count)

    async def delete_scope(self, scope: str) -> None:
        def _delete() -> None:
            conn = self._connect()
            try:
                conn.execute(
                    "DELETE FROM chunks WHERE session_id=? AND scope=?",
                    (self.session_id, scope),
                )
                conn.commit()
            finally:
                conn.close()
        await asyncio.to_thread(_delete)
