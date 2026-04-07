"""
OSSR LLM Response Cache
Exact-match caching layer for LLM responses to minimize API costs.
"""

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..db import get_connection

logger = logging.getLogger(__name__)


class LLMCache:
    """
    SQLite-backed cache for LLM responses.
    Key = SHA256(model + system_prompt + user_prompt).
    TTL configurable per entry.
    """

    DEFAULT_TTL = 86400  # 24 hours

    @staticmethod
    def _make_key(model: str, messages: List[Dict[str, str]]) -> str:
        content = json.dumps({"model": model, "messages": messages}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def get(model: str, messages: List[Dict[str, str]]) -> Optional[str]:
        key = LLMCache._make_key(model, messages)
        conn = get_connection()
        row = conn.execute(
            "SELECT response, created_at, ttl_seconds FROM llm_cache WHERE cache_key = ?",
            (key,),
        ).fetchone()
        if not row:
            return None

        # Check TTL
        created = datetime.fromisoformat(row["created_at"])
        if datetime.now() - created > timedelta(seconds=row["ttl_seconds"]):
            conn.execute("DELETE FROM llm_cache WHERE cache_key = ?", (key,))
            conn.commit()
            return None

        logger.debug(f"LLM cache hit: {key[:12]}...")
        return row["response"]

    @staticmethod
    def put(model: str, messages: List[Dict[str, str]], response: str,
            tokens_in: int = 0, tokens_out: int = 0,
            ttl_seconds: int = DEFAULT_TTL):
        key = LLMCache._make_key(model, messages)
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO llm_cache
               (cache_key, response, model, tokens_in, tokens_out, created_at, ttl_seconds)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (key, response, model, tokens_in, tokens_out,
             datetime.now().isoformat(), ttl_seconds),
        )
        conn.commit()

    @staticmethod
    def clear_expired():
        conn = get_connection()
        # Delete entries older than their TTL
        conn.execute("""
            DELETE FROM llm_cache
            WHERE datetime(created_at, '+' || ttl_seconds || ' seconds') < datetime('now')
        """)
        conn.commit()

    @staticmethod
    def stats() -> Dict[str, Any]:
        conn = get_connection()
        total = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
        return {"total_entries": total}
