"""Workflow run lifecycle endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import async_session
from ..models.project import Project
from ..models.workflow import WorkflowRun
from ..services.workflow_engine import V3WorkflowEngine, RESEARCH_TEMPLATES
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


def _requires_research_idea(template_id: str | None) -> bool:
    return (template_id or "") in RESEARCH_TEMPLATES


async def _validate_start_request(
    project_id: str,
    template_id: str | None,
    config: dict,
    db: AsyncSession,
) -> None:
    if _requires_research_idea(template_id) and not str(config.get("research_idea", "")).strip():
        raise HTTPException(400, "research_idea is required for research templates")

    from ..services.cost_recorder import CostRecorder

    budget = await CostRecorder().check_budget(db, project_id)
    if not budget["allowed"]:
        raise HTTPException(402, f"Budget exhausted: ${budget['spent_usd']} / ${budget['cap_usd']}")


async def _start_run(
    run: WorkflowRun,
    background_tasks: BackgroundTasks,
    db: AsyncSession,
    *,
    validate_request: bool = True,
) -> dict:
    if run.status not in ("pending", "paused", "failed"):
        raise HTTPException(400, f"Run is already {run.status}")

    config = run.config or {}
    if validate_request:
        await _validate_start_request(run.project_id, run.template_id, config, db)

    run.status = "running"

    await record_audit(db, "local", "run.started", "run", run.run_id, {
        "project_id": run.project_id,
        "template_id": run.template_id,
    })

    await event_bus.publish_event(
        "pipeline.started",
        project_id=run.project_id,
        run_id=run.run_id,
        payload={"template_id": run.template_id},
    )

    if (run.template_id or "") in RESEARCH_TEMPLATES:
        background_tasks.add_task(bridge.run_pipeline_background, run.run_id, run.project_id)

    return {"run_id": run.run_id, "status": "running", "message": "Pipeline started"}


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

    if body.auto_start:
        await _validate_start_request(body.project_id, body.template_id, body.config, db)

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

    if body.auto_start:
        await _start_run(run, background_tasks, db, validate_request=False)

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
    return {"data": await _start_run(run, background_tasks, db)}


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
