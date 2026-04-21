"""Simple trace tree helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass
class TraceSpan:
    span_id: str
    name: str
    parent_id: str | None
    started_at: str
    ended_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceTree:
    session_id: str
    spans: list[TraceSpan] = field(default_factory=list)

    def start_span(self, name: str, parent_id: str | None = None, **metadata: Any) -> TraceSpan:
        span = TraceSpan(
            span_id=uuid4().hex,
            name=name,
            parent_id=parent_id,
            started_at=datetime.now(timezone.utc).isoformat(),
            metadata=dict(metadata),
        )
        self.spans.append(span)
        return span

    def end_span(self, span_id: str, **metadata: Any) -> None:
        for span in reversed(self.spans):
            if span.span_id == span_id:
                span.ended_at = datetime.now(timezone.utc).isoformat()
                span.metadata.update(metadata)
                return
        raise KeyError(f"Unknown span: {span_id}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "spans": [
                {
                    "span_id": span.span_id,
                    "name": span.name,
                    "parent_id": span.parent_id,
                    "started_at": span.started_at,
                    "ended_at": span.ended_at,
                    "metadata": dict(span.metadata),
                }
                for span in self.spans
            ],
        }

