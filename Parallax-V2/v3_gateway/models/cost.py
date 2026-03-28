"""Unified cost ledger — every LLM call, compute job, and API cost recorded here."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class CostEntry(Base):
    __tablename__ = "cost_entries"

    entry_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"cost_{uuid.uuid4().hex[:12]}"
    )
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_id"), index=True
    )
    run_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("workflow_runs.run_id"), index=True, nullable=True
    )
    phase_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("phases.phase_id"), nullable=True
    )
    agent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_system: Mapped[str] = mapped_column(
        String(32), default="parallax"
    )  # parallax | oas | oae | damd | darklab
    cost_type: Mapped[str] = mapped_column(
        String(32), default="llm_call"
    )  # llm_call | compute | api | storage | energy
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "phase_id": self.phase_id,
            "agent_id": self.agent_id,
            "source_system": self.source_system,
            "cost_type": self.cost_type,
            "model_name": self.model_name,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
            "cost_usd": self.cost_usd,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
