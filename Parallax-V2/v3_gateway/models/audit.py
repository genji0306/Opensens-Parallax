"""Audit log — append-only record of every significant action."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    entry_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"aud_{uuid.uuid4().hex[:12]}"
    )
    actor: Mapped[str] = mapped_column(String(64))  # user_id or agent_id
    action: Mapped[str] = mapped_column(String(128))  # e.g. "phase.started", "approval.granted"
    resource_type: Mapped[str] = mapped_column(String(64))  # project, phase, eip, job, artifact
    resource_id: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)  # Ed25519 (DarkLab)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    def to_dict(self) -> dict:
        return {
            "entry_id": self.entry_id,
            "actor": self.actor,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "details": self.details,
            "signature": self.signature,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }
