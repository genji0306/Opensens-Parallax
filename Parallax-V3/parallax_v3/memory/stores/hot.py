"""
parallax_v3/memory/stores/hot.py
=================================
Pattern #3 — Tiered Memory: HOT tier.

Hot store holds the current-turn working set in memory.
Entries are evicted after a TTL (default 300 s) or when the session ends.
This is the fastest tier — no disk, no embedding, no network.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class _Entry:
    value: Any
    expires_at: float  # unix timestamp


class HotStore:
    """
    In-process dict with TTL eviction.

    Only holds lightweight items: short strings, small dicts.
    Agents MUST NOT put large objects (PDFs, full paper text) here.
    """

    DEFAULT_TTL = 300  # seconds

    def __init__(self, ttl_seconds: float = DEFAULT_TTL, ttl: float | None = None) -> None:
        self._ttl = ttl if ttl is not None else ttl_seconds
        self._data: dict[str, _Entry] = {}

    def set(
        self,
        key: str,
        value: Any,
        *,
        ttl_seconds: float | None = None,
        ttl: float | None = None,
    ) -> None:
        ttl_value = ttl_seconds if ttl_seconds is not None else ttl
        expires = time.monotonic() + (ttl_value if ttl_value is not None else self._ttl)
        self._data[key] = _Entry(value=value, expires_at=expires)

    def get(self, key: str, default: Any = None) -> Any:
        entry = self._data.get(key)
        if entry is None:
            return default
        if time.monotonic() > entry.expires_at:
            del self._data[key]
            return default
        return entry.value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)

    def evict_expired(self) -> int:
        """Remove all expired entries. Returns count of evicted items."""
        now = time.monotonic()
        expired = [k for k, e in self._data.items() if now > e.expires_at]
        for k in expired:
            del self._data[k]
        return len(expired)

    def clear(self) -> None:
        """Discard all entries (called at session_stop)."""
        self._data.clear()

    def items(self) -> list[tuple[str, Any]]:
        self.evict_expired()
        return [(key, entry.value) for key, entry in self._data.items()]

    def keys(self) -> list[str]:
        self.evict_expired()
        return list(self._data.keys())

    def __len__(self) -> int:
        self.evict_expired()
        return len(self._data)
