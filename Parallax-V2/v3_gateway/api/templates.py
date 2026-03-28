"""Protocol template endpoints."""

from __future__ import annotations

from fastapi import APIRouter

from ..services.workflow_engine import V3WorkflowEngine

router = APIRouter(prefix="/templates", tags=["templates"])
engine = V3WorkflowEngine()


@router.get("")
async def list_templates():
    """List all available protocol templates."""
    return {"data": engine.list_templates()}
