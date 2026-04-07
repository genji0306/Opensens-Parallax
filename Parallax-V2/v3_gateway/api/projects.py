"""Project CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.base import async_session
from ..models.project import Project
from ..middleware.audit import record_audit

router = APIRouter(prefix="/projects", tags=["projects"])


# ── Dependencies ─────────────────────────────────────────────────


async def get_db():
    async with async_session() as session:
        async with session.begin():
            yield session


# ── Schemas ──────────────────────────────────────────────────────


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str = ""
    domain: str = "academic"
    template_id: str | None = None
    budget_cap_usd: float = 50.0


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    budget_cap_usd: float | None = None


# ── Routes ───────────────────────────────────────────────────────


@router.post("", status_code=201)
async def create_project(body: ProjectCreate, db: AsyncSession = Depends(get_db)):
    project = Project(
        name=body.name,
        description=body.description,
        domain=body.domain,
        template_id=body.template_id,
        budget_cap_usd=body.budget_cap_usd,
    )
    db.add(project)
    await db.flush()

    await record_audit(db, "local", "project.created", "project", project.project_id, {
        "name": body.name, "domain": body.domain, "template_id": body.template_id,
    })

    return {"data": project.to_dict()}


@router.get("")
async def list_projects(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Project).order_by(Project.created_at.desc())
    if status:
        query = query.where(Project.status == status)
    result = await db.execute(query)
    projects = result.scalars().all()
    return {"data": [p.to_dict() for p in projects]}


@router.get("/{project_id}")
async def get_project(project_id: str, db: AsyncSession = Depends(get_db)):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, f"Project not found: {project_id}")
    return {"data": project.to_dict()}


@router.patch("/{project_id}")
async def update_project(
    project_id: str,
    body: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
):
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(404, f"Project not found: {project_id}")

    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(project, k, v)

    await record_audit(db, "local", "project.updated", "project", project_id, updates)
    return {"data": project.to_dict()}
