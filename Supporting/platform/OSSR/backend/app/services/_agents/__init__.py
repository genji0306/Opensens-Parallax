"""
Shared agent foundation layer for Parallax V2.

Provides a common interface, retry/timeout/rollout helpers, a prompt-card
loader (LabClaw SKILL.md format), and standardised Pydantic-lite schemas
used across every AIS / knowledge / review / translation / handoff agent.

This layer is deliberately thin — it wraps the existing ``LLMClient`` from
``opensens_common`` and the existing cost-tracking + cache hooks without
replacing them. Individual agents opt in by subclassing ``BaseAgent`` or
by calling the helpers directly.
"""

from .base import AgentError, AgentResult, BaseAgent
from .prompt_loader import SkillCard, load_skill
from .rollout import RolloutCandidate, rollout_and_aggregate
from .schema import Annotation, ReviewerPersona3D, ToolCall, Triple

__all__ = [
    "AgentError",
    "AgentResult",
    "BaseAgent",
    "SkillCard",
    "load_skill",
    "RolloutCandidate",
    "rollout_and_aggregate",
    "Annotation",
    "ReviewerPersona3D",
    "ToolCall",
    "Triple",
]
