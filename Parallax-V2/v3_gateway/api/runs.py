"""Workflow run lifecycle endpoints."""

from __future__ import annotations

import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import async_session
from ..models.project import Project
from ..models.workflow import WorkflowRun
from ..services.workflow_engine import V3WorkflowEngine
from ..services.v2_bridge import V2Bridge
from ..services import event_bus
from ..middleware.audit import record_audit

router = APIRouter(prefix="/runs", tags=["runs"])
engine = V3WorkflowEngine()
bridge = V2Bridge()


async def get_db():
    async with async_session() as session:
        async with session.begin():
            yield session


class RunCreate(BaseModel):
    project_id: str
    template_id: str = "academic_research"
    config: dict = Field(default_factory=dict)
    auto_start: bool = True


class RunAction(BaseModel):
    action: str  # "start" | "pause" | "resume"


@router.post("", status_code=201)
async def create_run(
    body: RunCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create a workflow run from a template and optionally start it."""
    project = await db.get(Project, body.project_id)
    if not project:
        raise HTTPException(404, f"Project not found: {body.project_id}")

    # Create run
    run = WorkflowRun(
        project_id=body.project_id,
        template_id=body.template_id,
        config=body.config,
        status="pending",
    )
    db.add(run)
    await db.flush()

    # Create phase DAG from template
    try:
        phases, edges = await engine.create_from_template(
            db, run.run_id, body.template_id,
            config_overrides=body.config.get("step_settings", {}),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    await record_audit(db, "local", "run.created", "run", run.run_id, {
        "project_id": body.project_id,
        "template_id": body.template_id,
        "phase_count": len(phases),
    })

    await event_bus.publish_event(
        "pipeline.created",
        project_id=body.project_id,
        run_id=run.run_id,
        payload={"template_id": body.template_id, "phase_count": len(phases)},
    )

    result = run.to_dict()
    result["phases"] = [p.to_dict() for p in phases]
    result["edges"] = [e.to_dict() for e in edges]

    return {"data": result}


@router.get("")
async def list_runs(
    project_id: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(WorkflowRun).order_by(WorkflowRun.created_at.desc())
    if project_id:
        query = query.where(WorkflowRun.project_id == project_id)
    if status:
        query = query.where(WorkflowRun.status == status)
    result = await db.execute(query)
    runs = result.scalars().all()
    return {"data": [r.to_dict() for r in runs]}


@router.get("/{run_id}")
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(404, f"Run not found: {run_id}")
    return {"data": run.to_dict()}


@router.post("/{run_id}/start", status_code=202)
async def start_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Start executing a workflow run.

    For academic research templates: delegates to V2 SDK in a background thread.
    Events stream back via DRVP SSE. Costs are recorded to the unified ledger.

    Returns 202 Accepted immediately — poll /runs/{id} or /runs/{id}/graph for status.
    """
    run = await db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(404, f"Run not found: {run_id}")
    if run.status not in ("pending", "paused", "failed"):
        raise HTTPException(400, f"Run is already {run.status}")

    # Check budget
    from ..services.cost_recorder import CostRecorder
    budget = await CostRecorder().check_budget(db, run.project_id)
    if not budget["allowed"]:
        raise HTTPException(402, f"Budget exhausted: ${budget['spent_usd']} / ${budget['cap_usd']}")

    # Mark as running
    run.status = "running"

    await record_audit(db, "local", "run.started", "run", run_id, {
        "project_id": run.project_id,
        "template_id": run.template_id,
    })

    await event_bus.publish_event(
        "pipeline.started",
        project_id=run.project_id,
        run_id=run_id,
        payload={"template_id": run.template_id},
    )

    # Determine execution strategy
    template = run.template_id or ""
    if template in ("academic_research", "full_research_experiment") and run.config.get("research_idea"):
        # Delegate to V2 SDK in background
        project_id = run.project_id
        background_tasks.add_task(_execute_v2_pipeline, run_id, project_id, run.config)
    else:
        # Non-V2 templates: mark as running, phases must be executed individually
        pass

    return {"data": {"run_id": run_id, "status": "running", "message": "Pipeline started"}}


async def _execute_v2_pipeline(run_id: str, project_id: str, config: dict):
    """Background task: run V2 pipeline and sync results back."""
    async with async_session() as session:
        async with session.begin():
            run = await session.get(WorkflowRun, run_id)
            if not run:
                return

    try:
        v2_run_id = await bridge.start_research_pipeline(run, project_id)

        await event_bus.publish_event(
            "pipeline.completed",
            source_system="v3_gateway",
            project_id=project_id,
            run_id=run_id,
            payload={"v2_run_id": v2_run_id},
        )
    except Exception as e:
        async with async_session() as session:
            async with session.begin():
                await session.execute(
                    select(WorkflowRun).where(WorkflowRun.run_id == run_id)
                )
                from sqlalchemy import update as sql_update
                await session.execute(
                    sql_update(WorkflowRun)
                    .where(WorkflowRun.run_id == run_id)
                    .values(status="failed")
                )

        await event_bus.publish_event(
            "pipeline.failed",
            source_system="v3_gateway",
            project_id=project_id,
            run_id=run_id,
            payload={"error": str(e)},
        )


@router.get("/{run_id}/graph")
async def get_run_graph(run_id: str, db: AsyncSession = Depends(get_db)):
    """Get full DAG state for a workflow run."""
    run = await db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(404, f"Run not found: {run_id}")
    graph = await engine.get_graph_state(db, run_id)
    return {"data": graph}


@router.post("/{run_id}/restart/{phase_id}")
async def restart_from_phase(
    run_id: str,
    phase_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Restart a run from a specific phase, invalidating downstream."""
    run = await db.get(WorkflowRun, run_id)
    if not run:
        raise HTTPException(404, f"Run not found: {run_id}")

    result = await engine.restart_from_phase(db, run_id, phase_id)

    await record_audit(db, "local", "run.restarted", "run", run_id, {
        "from_phase": phase_id,
        "invalidated_count": result["invalidated_count"],
    })

    await event_bus.publish_event(
        "phase.restarted",
        project_id=run.project_id,
        run_id=run_id,
        phase_id=phase_id,
        payload=result,
    )

    return {"data": result}
