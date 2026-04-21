"""Append-only JSONL audit log."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from ..contracts import RiskLevel
from ..errors import ParallaxV3Error


class AuditLogError(ParallaxV3Error):
    """Raised when audit logging fails."""


@dataclass
class AuditLog:
    session_id: str
    workspace_path: Path

    def __post_init__(self) -> None:
        root = Path(self.workspace_path)
        if root.name != self.session_id:
            root = root / self.session_id
        root.mkdir(parents=True, exist_ok=True)
        self.file_path = root / "audit.jsonl"
        self._fh: TextIO = self.file_path.open("a", encoding="utf-8")

    def log(
        self,
        hook_point: str,
        tool_name: str | None,
        risk_level: RiskLevel | None,
        cost_usd: float | None,
        detail: dict | None,
    ) -> dict[str, Any]:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "hook_point": hook_point,
            "tool_name": tool_name,
            "risk_level": risk_level.value if isinstance(risk_level, RiskLevel) else risk_level,
            "cost_usd": cost_usd,
            "detail": detail or {},
        }
        self._fh.write(json.dumps(entry, sort_keys=True) + "\n")
        self._fh.flush()
        return entry

    def close(self) -> None:
        if not self._fh.closed:
            self._fh.flush()
            self._fh.close()

    def __enter__(self) -> "AuditLog":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


