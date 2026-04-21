"""Pydantic schemas for the V3 API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ..contracts import RiskLevel


class ApiModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class CreateSessionRequest(ApiModel):
    research_question: str
    target_venue: str
    citation_style: str
    budget_usd: float
    max_refinement_iters: int


class SessionResponse(ApiModel):
    session_id: str
    status: str
    manifest: dict[str, Any]
    created_at: datetime


class RunPipelineRequest(ApiModel):
    session_id: str
    pipeline: Literal["paper_orchestra", "full_research", "revision", "grant"]
    idea_path: str
    log_path: str


class RunPipelineResponse(ApiModel):
    run_id: str
    session_id: str
    status: str
    started_at: datetime


class AuditEntry(ApiModel):
    timestamp: datetime
    hook_point: str
    tool_name: str | None
    risk_level: RiskLevel | None
    cost_usd: float | None
    detail: dict[str, Any] | None = None


class MemoryStatsResponse(ApiModel):
    hot_keys: int
    warm_entries: int
    cold_files: int
    token_estimate: int


