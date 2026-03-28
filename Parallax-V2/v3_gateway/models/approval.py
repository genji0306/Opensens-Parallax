"""Approval requests — governance gates for risky or expensive actions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    approval_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"apr_{uuid.uuid4().hex[:12]}"
    )
    project_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("projects.project_id"), index=True
    )
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("workflow_runs.run_id")
    )
    phase_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("phases.phase_id")
    )
    reason: Mapped[str] = mapped_column(Text)
    risk_class: Mapped[str] = mapped_column(
        String(16), default="low"
    )  # low | medium | high | critical
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(
        String(16), default="pending"
    )  # pending | approved | denied | expired
    requested_by: Mapped[str] = mapped_column(String(64))  # agent_id
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)  # user_id
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict:
        return {
            "approval_id": self.approval_id,
            "project_id": self.project_id,
            "run_id": self.run_id,
            "phase_id": self.phase_id,
            "reason": self.reason,
            "risk_class": self.risk_class,
            "details": self.details,
            "status": self.status,
            "requested_by": self.requested_by,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
