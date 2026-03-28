"""Cost query endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import async_session
from ..models.cost import CostEntry
from ..services.cost_recorder import CostRecorder

router = APIRouter(prefix="/costs", tags=["costs"])
recorder = CostRecorder()


async def get_db():
    async with async_session() as session:
        async with session.begin():
            yield session


@router.get("/project/{project_id}")
async def get_project_cost(project_id: str, db: AsyncSession = Depends(get_db)):
    """Get total cost for a project."""
    result = await recorder.get_project_cost(db, project_id)
    return {"data": result}


@router.get("/run/{run_id}")
async def get_run_cost(run_id: str, db: AsyncSession = Depends(get_db)):
    """Get cost breakdown for a workflow run."""
    result = await recorder.get_run_cost(db, run_id)
    return {"data": result}


@router.get("/project/{project_id}/budget")
async def check_budget(project_id: str, db: AsyncSession = Depends(get_db)):
    """Check budget status for a project."""
    result = await recorder.check_budget(db, project_id)
    return {"data": result}


@router.get("/project/{project_id}/entries")
async def list_cost_entries(
    project_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List cost entries for a project."""
    result = await db.execute(
        select(CostEntry)
        .where(CostEntry.project_id == project_id)
        .order_by(CostEntry.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    entries = result.scalars().all()
    return {"data": [e.to_dict() for e in entries]}
