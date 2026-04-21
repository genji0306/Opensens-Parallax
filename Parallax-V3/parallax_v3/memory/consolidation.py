"""Between-stage consolidation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StageDigest:
    stage_name: str
    summary: str
    source_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsolidationAgent:
    """Lightweight digest builder for stage handoff."""

    def consolidate(self, stage_name: str, items: list[str]) -> StageDigest:
        summary = " ".join(items[:5])
        return StageDigest(
            stage_name=stage_name,
            summary=summary,
            source_count=len(items),
            metadata={"token_estimate": sum(len(item.split()) for item in items)},
        )

