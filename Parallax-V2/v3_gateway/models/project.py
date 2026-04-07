"""Project model — the top-level entity in V3."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Float, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Project(Base):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=lambda: f"prj_{uuid.uuid4().hex[:12]}"
    )
    name: Mapped[str] = mapped_column(String(256))
    description: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(
        String(32), default="academic"
    )  # academic | experiment | simulation | damd | hybrid
    template_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    owner_id: Mapped[str] = mapped_column(String(64), default="local")
    budget_cap_usd: Mapped[float] = mapped_column(Float, default=50.0)
    budget_spent_usd: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(
        String(32), default="active"
    )  # active | paused | completed | archived
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
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain,
            "template_id": self.template_id,
            "owner_id": self.owner_id,
            "budget_cap_usd": self.budget_cap_usd,
            "budget_spent_usd": self.budget_spent_usd,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
