"""Workflow models — WorkflowRun, Phase (DAG nodes), PhaseEdge (DAG edges)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Text, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    run_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"run_{uuid.uuid4().hex[:12]}"
    )
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_id"), index=True
    )
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending | running | paused | completed | failed
    budget_spent_usd: Mapped[float] = mapped_column(Float, default=0.0)
    # Link to V2 pipeline run (if this run delegates to V2)
    v2_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "project_id": self.project_id,
            "template_id": self.template_id,
            "config": self.config,
            "status": self.status,
            "budget_spent_usd": self.budget_spent_usd,
            "v2_run_id": self.v2_run_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Phase(Base):
    """A single node in the workflow DAG."""
    __tablename__ = "phases"

    phase_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"ph_{uuid.uuid4().hex[:12]}"
    )
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflow_runs.run_id"), index=True
    )
    phase_type: Mapped[str] = mapped_column(String(48))  # PhaseType enum value
    label: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(
        String(32), default="pending"
    )  # pending | running | completed | failed | skipped | invalidated | awaiting_approval
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    outputs: Mapped[dict] = mapped_column(JSON, default=dict)
    assigned_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_config_json: Mapped[dict] = mapped_column(JSON, default=dict)
    model_used: Mapped[str] = mapped_column(String(128), default="")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "phase_id": self.phase_id,
            "run_id": self.run_id,
            "phase_type": self.phase_type,
            "label": self.label,
            "status": self.status,
            "config": self.config,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "assigned_agent": self.assigned_agent,
            "model_config": self.model_config_json,
            "model_used": self.model_used,
            "cost_usd": self.cost_usd,
            "score": self.score,
            "error": self.error,
            "sort_order": self.sort_order,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class PhaseEdge(Base):
    """A directed edge in the workflow DAG."""
    __tablename__ = "phase_edges"

    edge_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"edge_{uuid.uuid4().hex[:12]}"
    )
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflow_runs.run_id"), index=True
    )
    source_phase_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("phases.phase_id"), index=True
    )
    target_phase_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("phases.phase_id"), index=True
    )
    edge_type: Mapped[str] = mapped_column(
        String(32)
    )  # dependency | conditional | optional | feedback | approval | branch | merge

    def to_dict(self) -> dict:
        return {
            "edge_id": self.edge_id,
            "run_id": self.run_id,
            "source_phase_id": self.source_phase_id,
            "target_phase_id": self.target_phase_id,
            "edge_type": self.edge_type,
        }
