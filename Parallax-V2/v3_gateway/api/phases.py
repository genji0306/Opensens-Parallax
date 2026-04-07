"""Phase execution and management endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.approval import ApprovalRequest
from ..models.base import async_session
from ..models.workflow import WorkflowRun, Phase, PhaseEdge
from ..services.workflow_engine import V3WorkflowEngine, RESEARCH_TEMPLATES
from ..services.v2_bridge import V2Bridge
from ..services.cost_recorder import CostRecorder
from ..services import event_bus
from ..middleware.audit import record_audit

router = APIRouter(prefix="/phases", tags=["phases"])
engine = V3WorkflowEngine()
bridge = V2Bridge()
cost_recorder = CostRecorder()

logger = logging.getLogger(__name__)


class PhaseCompleteBody(BaseModel):
    outputs: dict = Field(default_factory=dict)
    score: Optional[float] = None
    model_used: str = ""
    cost_usd: float = 0.0


class PhaseFailBody(BaseModel):
    error: str = "Unknown error"


async def get_db():
    async with async_session() as session:
        async with session.begin():
            yield session


class PhaseModelUpdate(BaseModel):
    model: str


class PhaseSettingsUpdate(BaseModel):
    settings: dict


# ── Phase Queries ────────────────────────────────────────────────


@router.get("/run/{run_id}")
async def list_phases(run_id: str, db: AsyncSession = Depends(get_db)):
    """List all phases for a workflow run."""
    result = await db.execute(
        select(Phase).where(Phase.run_id == run_id).order_by(Phase.sort_order)
    )
    phases = result.scalars().all()
    return {"data": [p.to_dict() for p in phases]}


@router.get("/{phase_id}")
async def get_phase(phase_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single phase by ID."""
    phase = await db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(404, f"Phase not found: {phase_id}")
    return {"data": phase.to_dict()}


# ── Phase Execution ──────────────────────────────────────────────


@router.post("/run/{run_id}/execute-next")
async def execute_next_phases(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Find and execute the next ready phases in the DAG.
    Research phases delegate to V2. Others return pending status for future backends.
    """
    run = await db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(404, f"Run not found: {run_id}")

    # Check budget
    budget = await cost_recorder.check_budget(db, run.project_id)
    if not budget["allowed"]:
        raise HTTPException(402, f"Budget exhausted: ${budget['spent_usd']} / ${budget['cap_usd']}")

    ready = await engine.get_next_executable(db, run_id)
    if not ready:
        return {"data": {"message": "No phases ready to execute", "ready": []}}

    executed = []
    launched_research_backend = False
    uses_research_bridge = (run.template_id or "") in RESEARCH_TEMPLATES
    for phase in ready:
        if phase.phase_type == "approval_gate":
            # Approval gates pause — don't auto-execute
            approval = ApprovalRequest(
                project_id=run.project_id,
                run_id=run_id,
                phase_id=phase.phase_id,
                reason=f"Approval required for {phase.label}",
                risk_class="medium",
                details={"phase_type": phase.phase_type, "config": phase.config or {}},
                requested_by="system",
            )
            db.add(approval)
            await db.flush()
            await db.execute(
                update(Phase)
                .where(Phase.phase_id == phase.phase_id)
                .values(status="awaiting_approval")
            )
            await event_bus.publish_event(
                "approval.required",
                project_id=run.project_id,
                run_id=run_id,
                phase_id=phase.phase_id,
                payload={
                    "phase_type": phase.phase_type,
                    "label": phase.label,
                    "approval_id": approval.approval_id,
                },
            )
            executed.append({
                "phase_id": phase.phase_id,
                "status": "awaiting_approval",
                "approval_id": approval.approval_id,
            })
        elif uses_research_bridge and bridge.can_handle(phase.phase_type):
            if not str((run.config or {}).get("research_idea", "")).strip():
                raise HTTPException(400, "research_idea is required for research templates")
            # Mark running
            await engine.mark_phase_running(db, phase.phase_id)
            await event_bus.publish_event(
                "phase.started",
                project_id=run.project_id,
                run_id=run_id,
                phase_id=phase.phase_id,
                payload={"phase_type": phase.phase_type},
            )
            executed.append({"phase_id": phase.phase_id, "status": "running", "backend": "v2"})
            if not launched_research_backend and run.status != "running":
                background_tasks.add_task(bridge.run_pipeline_background, run_id, run.project_id)
                launched_research_backend = True
        else:
            # Non-V2 phases (experiment_execute, compute_*, simulate_*) — mark as pending
            # These will be handled by future execution backends
            executed.append({
                "phase_id": phase.phase_id,
                "status": "pending",
                "backend": "not_yet_implemented",
                "phase_type": phase.phase_type,
            })

    # Update run status
    if any(e["status"] == "running" for e in executed):
        await db.execute(
            update(WorkflowRun).where(WorkflowRun.run_id == run_id).values(status="running")
        )

    return {"data": {"executed": executed, "count": len(executed)}}


@router.post("/{phase_id}/complete")
async def complete_phase(
    phase_id: str,
    body: PhaseCompleteBody,
    db: AsyncSession = Depends(get_db),
):
    """
    Manually complete a phase with outputs.
    Used by execution backends to report results, or for testing.
    """
    phase = await db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(404, f"Phase not found: {phase_id}")

    outputs = body.outputs
    score = body.score
    model_used = body.model_used
    cost_usd = body.cost_usd

    await engine.complete_phase(db, phase_id, outputs, score=score, model_used=model_used, cost_usd=cost_usd)

    # Record cost
    run = await db.get(WorkflowRun, phase.run_id)
    if run and cost_usd > 0:
        await cost_recorder.record(
            db,
            project_id=run.project_id,
            run_id=phase.run_id,
            phase_id=phase_id,
            source_system="v3_gateway",
            model_name=model_used,
            cost_usd=cost_usd,
        )

    await record_audit(db, "system", "phase.completed", "phase", phase_id, {
        "phase_type": phase.phase_type, "score": score, "cost_usd": cost_usd,
    })

    await event_bus.publish_event(
        "phase.completed",
        project_id=run.project_id if run else None,
        run_id=phase.run_id,
        phase_id=phase_id,
        payload={"phase_type": phase.phase_type, "score": score, **outputs},
    )

    # Check if pipeline is complete
    graph = await engine.get_graph_state(db, phase.run_id)
    if graph["summary"]["progress_pct"] == 100.0:
        await db.execute(
            update(WorkflowRun).where(WorkflowRun.run_id == phase.run_id).values(status="completed")
        )
        await event_bus.publish_event(
            "pipeline.completed",
            project_id=run.project_id if run else None,
            run_id=phase.run_id,
            payload=graph["summary"],
        )

    return {"data": {"phase_id": phase_id, "status": "completed"}}


@router.post("/{phase_id}/fail")
async def fail_phase(
    phase_id: str,
    body: PhaseFailBody,
    db: AsyncSession = Depends(get_db),
):
    """Mark a phase as failed."""
    phase = await db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(404, f"Phase not found: {phase_id}")

    error = body.error
    await engine.fail_phase(db, phase_id, error)

    await event_bus.publish_event(
        "phase.failed",
        run_id=phase.run_id,
        phase_id=phase_id,
        payload={"phase_type": phase.phase_type, "error": error},
    )

    return {"data": {"phase_id": phase_id, "status": "failed"}}


# ── Phase Configuration ──────────────────────────────────────────


@router.put("/{phase_id}/model")
async def set_phase_model(
    phase_id: str,
    body: PhaseModelUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Set the model for a specific phase."""
    phase = await db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(404, f"Phase not found: {phase_id}")

    await db.execute(
        update(Phase)
        .where(Phase.phase_id == phase_id)
        .values(model_config_json={"model": body.model})
    )

    await record_audit(db, "local", "phase.model_changed", "phase", phase_id, {"model": body.model})
    return {"data": {"phase_id": phase_id, "model": body.model}}


@router.put("/{phase_id}/settings")
async def set_phase_settings(
    phase_id: str,
    body: PhaseSettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update advanced settings for a phase."""
    phase = await db.get(Phase, phase_id)
    if not phase:
        raise HTTPException(404, f"Phase not found: {phase_id}")

    merged = {**(phase.config or {}), **body.settings}
    await db.execute(
        update(Phase).where(Phase.phase_id == phase_id).values(config=merged)
    )

    await record_audit(db, "local", "phase.settings_changed", "phase", phase_id, body.settings)
    return {"data": {"phase_id": phase_id, "config": merged}}
