"""Semantic Scholar citation lookup with a local cache."""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...contracts import Phase, RiskLevel, TypedTool
from ...errors import ParallaxV3Error

try:  # pragma: no cover - optional dependency
    import Levenshtein

    def _similarity(a: str, b: str) -> float:
        return float(Levenshtein.ratio(a, b))
except Exception:  # pragma: no cover - fallback
    from difflib import SequenceMatcher

    def _similarity(a: str, b: str) -> float:
        return float(SequenceMatcher(None, a, b).ratio())


class CitationLookupError(ParallaxV3Error):
    """Raised when citation lookup fails."""


def _normalize_title(title: str) -> str:
    return " ".join(title.lower().split())


@dataclass
class CitationLookup(TypedTool):
    workspace_path: Path
    session_id: str | None = None
    base_url: str = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, workspace_path: Path, session_id: str | None = None, base_url: str | None = None):
        TypedTool.__init__(
            self,
            name="citation_lookup",
            input_schema=dict,
            output_schema=list,
            risk_level=RiskLevel.SAFE_AUTO,
            phase_unlock=Phase.EXPLORE,
        )
        root = Path(workspace_path)
        object.__setattr__(self, "workspace_path", (root / session_id) if session_id else root)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "base_url", base_url or self.base_url)
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        self._cache_path = self.workspace_path / "citations" / "s2_cache.json"
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._cache = self._load_cache()

    def _load_cache(self) -> dict[str, Any]:
        if self._cache_path.exists():
            try:
                return json.loads(self._cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {"queries": {}, "pool": []}

    def _save_cache(self) -> None:
        self._cache_path.write_text(json.dumps(self._cache, indent=2, sort_keys=True), encoding="utf-8")

    def _query_key(self, query: str, limit: int) -> str:
        return f"{query.strip().lower()}::{limit}"

    def _fetch_remote(self, query: str, limit: int) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "query": query,
                "limit": limit,
                "fields": "paperId,title,year,venue,url,abstract,authors,externalIds,citationCount",
            }
        )
        url = f"{self.base_url.rstrip('/')}/paper/search?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Parallax-V3"})
        api_key = os.environ.get("S2_API_KEY")
        if api_key:
            req.add_header("x-api-key", api_key)
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("data", [])

    def _dedupe(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        pool = self._cache.setdefault("pool", [])
        accepted: list[dict[str, Any]] = []
        for item in items:
            title = _normalize_title(str(item.get("title", "")))
            if not title:
                continue
            duplicate = False
            for existing in pool + accepted:
                existing_title = _normalize_title(str(existing.get("title", "")))
                if not existing_title:
                    continue
                if item.get("paperId") and existing.get("paperId") and item["paperId"] == existing["paperId"]:
                    duplicate = True
                    break
                if _similarity(title, existing_title) > 0.85:
                    duplicate = True
                    break
            if duplicate:
                continue
            accepted.append(item)
        return accepted

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        key = self._query_key(query, limit)
        cached = self._cache.get("queries", {}).get(key)
        if cached is not None:
            return list(cached)
        results = self._fetch_remote(query, limit)
        deduped = self._dedupe(results)[:limit]
        self._cache.setdefault("queries", {})[key] = deduped
        pool = self._cache.setdefault("pool", [])
        pool.extend(deduped)
        self._save_cache()
        return deduped


