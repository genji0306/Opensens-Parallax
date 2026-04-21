"""Read-only section critic."""

from __future__ import annotations

from dataclasses import dataclass

from opensens_common.llm_client import LLMUsage

from ...contracts import AgentResult, ContextBundle, Phase, ScopeKey, SessionManifest
from ..base import Agent


@dataclass
class SectionCritic(Agent):
    scope: ScopeKey = ScopeKey.REVIEW
    phase: Phase = Phase.ACT
    allowed_tools: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.allowed_tools is None:
            self.allowed_tools = ["read", "grep"]

    async def run(self, ctx: ContextBundle, manifest: SessionManifest) -> AgentResult:
        return AgentResult(
            agent_id="section_critic",
            outputs={"scope": ctx.scope.value},
            cost=LLMUsage(model="mock"),
            findings=[],
            status="success",
        )

