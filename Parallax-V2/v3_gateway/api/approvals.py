"""Approval management endpoints — governance gates for risky actions."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import async_session
from ..models.approval import ApprovalRequest
from ..models.workflow import Phase
from ..services import event_bus
from ..middleware.audit import record_audit

router = APIRouter(prefix="/approvals", tags=["approvals"])


async def get_db():
    async with async_session() as session:
        async with session.begin():
            yield session


class ApprovalDecision(BaseModel):
    decision: str  # "approved" | "denied"
    decided_by: str = "local"
    reason: str = ""


@router.get("")
async def list_approvals(
    project_id: str | None = None,
    status: str = "pending",
    db: AsyncSession = Depends(get_db),
):
    """List approval requests, defaulting to pending."""
    query = select(ApprovalRequest).order_by(ApprovalRequest.created_at.desc())
    if project_id:
        query = query.where(ApprovalRequest.project_id == project_id)
    if status:
        query = query.where(ApprovalRequest.status == status)
    result = await db.execute(query)
    approvals = result.scalars().all()
    return {"data": [a.to_dict() for a in approvals]}


@router.get("/{approval_id}")
async def get_approval(approval_id: str, db: AsyncSession = Depends(get_db)):
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval:
        raise HTTPException(404, f"Approval not found: {approval_id}")
    return {"data": approval.to_dict()}


@router.post("/{approval_id}/decide")
async def decide_approval(
    approval_id: str,
    body: ApprovalDecision,
    db: AsyncSession = Depends(get_db),
):
    """Approve or deny an approval request."""
    approval = await db.get(ApprovalRequest, approval_id)
    if not approval:
        raise HTTPException(404, f"Approval not found: {approval_id}")
    if approval.status != "pending":
        raise HTTPException(400, f"Approval already decided: {approval.status}")

    if body.decision not in ("approved", "denied"):
        raise HTTPException(400, "Decision must be 'approved' or 'denied'")

    now = datetime.now(timezone.utc)
    approval.status = body.decision
    approval.decided_by = body.decided_by
    approval.decided_at = now

    await record_audit(db, body.decided_by, f"approval.{body.decision}", "approval", approval_id, {
        "phase_id": approval.phase_id,
        "risk_class": approval.risk_class,
        "reason": body.reason,
    })

    # If approved, mark the gated phase as completed so downstream can proceed
    if body.decision == "approved":
        phase = await db.get(Phase, approval.phase_id)
        if phase:
            await db.execute(
                update(Phase)
                .where(Phase.phase_id == approval.phase_id)
                .values(
                    status="completed",
                    outputs={"approved_by": body.decided_by, "approved_at": now.isoformat()},
                    completed_at=now,
                )
            )

        await event_bus.publish_event(
            "approval.granted",
            project_id=approval.project_id,
            run_id=approval.run_id,
            phase_id=approval.phase_id,
            payload={"decided_by": body.decided_by},
        )
    else:
        await event_bus.publish_event(
            "approval.denied",
            project_id=approval.project_id,
            run_id=approval.run_id,
            phase_id=approval.phase_id,
            payload={"decided_by": body.decided_by, "reason": body.reason},
        )

    return {"data": approval.to_dict()}
