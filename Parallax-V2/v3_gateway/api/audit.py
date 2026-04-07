"""Audit log query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import async_session
from ..models.audit import AuditEntry

router = APIRouter(prefix="/audit", tags=["audit"])


async def get_db():
    async with async_session() as session:
        async with session.begin():
            yield session


@router.get("")
async def list_audit_entries(
    resource_type: str | None = None,
    resource_id: str | None = None,
    action: str | None = None,
    actor: str | None = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """Query the audit log with optional filters."""
    query = select(AuditEntry).order_by(AuditEntry.timestamp.desc())
    if resource_type:
        query = query.where(AuditEntry.resource_type == resource_type)
    if resource_id:
        query = query.where(AuditEntry.resource_id == resource_id)
    if action:
        query = query.where(AuditEntry.action.contains(action))
    if actor:
        query = query.where(AuditEntry.actor == actor)
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    entries = result.scalars().all()
    return {"data": [e.to_dict() for e in entries]}
