"""FastAPI router for the V3 API scaffold."""

from __future__ import annotations

import inspect
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter

from ..observability.sse import EventSourceResponse
from ..runtime.conductor import Conductor
from .schemas import (
    AuditEntry,
    CreateSessionRequest,
    MemoryStatsResponse,
    RunPipelineRequest,
    RunPipelineResponse,
    SessionResponse,
)

router = APIRouter(prefix="/api/v3")
conductor = Conductor()


async def _maybe_await(result: Any) -> Any:
    if inspect.isawaitable(result):
        return await result
    return result


def _envelope(success: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"success": success, "data": data, "error": error}


@router.post("/sessions")
async def create_session(request: CreateSessionRequest) -> dict[str, Any]:
    try:
        data = await _maybe_await(conductor.create_session(request))
        return _envelope(True, SessionResponse.model_validate(data))
    except Exception as exc:
        return _envelope(False, None, str(exc))


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    try:
        data = await _maybe_await(conductor.get_session(session_id))
        return _envelope(True, SessionResponse.model_validate(data))
    except Exception as exc:
        return _envelope(False, None, str(exc))


@router.post("/run")
async def run_pipeline(request: RunPipelineRequest) -> dict[str, Any]:
    try:
        data = await _maybe_await(conductor.run_pipeline(request))
        return _envelope(True, RunPipelineResponse.model_validate(data))
    except Exception as exc:
        return _envelope(False, None, str(exc))


@router.get("/run/{run_id}/events")
async def get_run_events(run_id: str):
    async def stream():
        try:
            async for event in conductor.stream_events(run_id):
                yield event
        except Exception as exc:
            yield {"type": "error", "status": "failed", "error": str(exc)}

    return EventSourceResponse(stream())


@router.get("/run/{run_id}/audit")
async def get_run_audit(run_id: str) -> dict[str, Any]:
    try:
        data = await _maybe_await(conductor.get_run_audit(run_id))
        return _envelope(True, [AuditEntry.model_validate(item) for item in data])
    except Exception as exc:
        return _envelope(False, None, str(exc))


@router.get("/run/{run_id}/memory")
async def get_run_memory(run_id: str) -> dict[str, Any]:
    try:
        data = await _maybe_await(conductor.get_memory_stats(run_id))
        return _envelope(True, MemoryStatsResponse.model_validate(data))
    except Exception as exc:
        return _envelope(False, None, str(exc))


