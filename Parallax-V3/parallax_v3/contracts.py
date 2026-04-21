"""Frozen interface contracts for Parallax V3."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, IntEnum
from pathlib import Path
from typing import Any, Literal

from opensens_common.llm_client import LLMUsage


class Phase(IntEnum):
    EXPLORE = 0
    PLAN = 1
    ACT = 2


class RiskLevel(str, Enum):
    SAFE_AUTO = "SAFE_AUTO"
    SAFE_CONFIRM = "SAFE_CONFIRM"
    ASK_USER = "ASK_USER"
    DANGER_BLOCK = "DANGER_BLOCK"


@dataclass(frozen=True)
class SessionManifest:
    session_id: str
    research_question: str
    target_venue: str
    citation_style: str
    max_refinement_iters: int = 3
    budget_usd: float = 0.0
    ethics_flags: list[str] = field(default_factory=list)
    refinement_policy: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TypedTool:
    name: str
    input_schema: type[Any]
    output_schema: type[Any]
    risk_level: RiskLevel
    phase_unlock: Phase


class ScopeKey(str, Enum):
    OUTLINE = "outline"
    SECTION_INTRO = "section.intro"
    SECTION_METHODS = "section.methods"
    SECTION_RESULTS = "section.results"
    SECTION_DISCUSS = "section.discussion"
    REVIEW = "review"
    CITE_CHECK = "cite_check"
    FULL_PIPELINE = "full_pipeline"


@dataclass
class ContextBundle:
    scope: ScopeKey
    hot_items: list[str]
    warm_summaries: list[str]
    cold_paths: list[Path]
    token_estimate: int


@dataclass
class ReviewFinding:
    section: str
    axis: str
    score: float
    comment: str
    suggested_edit: str | None = None


@dataclass
class AgentResult:
    agent_id: str
    outputs: dict[str, Any]
    cost: LLMUsage
    findings: list[ReviewFinding] = field(default_factory=list)
    status: Literal["success", "failed", "reverted"] = "success"


@dataclass
class RefinementState:
    iteration: int
    scores: list[float]
    prev_scores: list[float]
    plateau_count: int
    verdict: Literal["accept", "revert", "halt_plateau", "halt_cap", "halt_empty"]


# Compatibility helpers for older runtime scaffolds.


class HookPoint(str, Enum):
    LOAD_ENV = "load_env"
    SESSION_START = "session_start"
    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    STAGE_START = "stage_start"
    STAGE_END = "stage_end"
    SESSION_STOP = "session_stop"


@dataclass
class AuditRecord:
    timestamp: str
    session_id: str
    hook_point: str
    tool: str | None
    risk: str | None
    cost_usd: float | None
    agent_id: str | None
    detail: dict[str, Any] = field(default_factory=dict)


