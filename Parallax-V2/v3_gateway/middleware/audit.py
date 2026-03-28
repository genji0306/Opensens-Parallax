"""Audit middleware — records every significant action to the audit log."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit import AuditEntry


async def record_audit(
    session: AsyncSession,
    actor: str,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
) -> AuditEntry:
    """Record an audit entry. Called by API routes after mutations."""
    entry = AuditEntry(
        actor=actor,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    session.add(entry)
    return entry
