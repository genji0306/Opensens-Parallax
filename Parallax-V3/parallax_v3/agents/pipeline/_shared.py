"""Shared helpers for V2-parity pipeline agents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...contracts import AgentResult, ContextBundle, Phase, ScopeKey, SessionManifest
from ...llm.client import EngineClient
from ..base import Agent


def _prompt_for(name: str) -> str:
    prompt_path = Path(__file__).resolve().parents[2] / "llm" / "prompts" / f"{name}.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return f"You are the {name} agent."


class PipelineAgent(Agent):
    scope = ScopeKey.FULL_PIPELINE
    phase = Phase.EXPLORE
    allowed_tools = ["read", "grep", "citation_lookup"]
    prompt_name = ""

    def __init__(self, engine: EngineClient | None = None):
        self.engine = engine or EngineClient()

    @property
    def agent_id(self) -> str:
        return self.__class__.__name__.replace("Agent", "").lower()

    async def run(self, ctx: ContextBundle, manifest: SessionManifest) -> AgentResult:
        prompt = _prompt_for(self.prompt_name or self.agent_id)
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Scope: {ctx.scope.value}\nHot items: {ctx.hot_items}\nWarm summaries: {ctx.warm_summaries}\nCold paths: {[str(path) for path in ctx.cold_paths]}\nToken estimate: {ctx.token_estimate}\nResearch question: {manifest.research_question}",
            },
        ]
        response, usage = self.engine.complete(messages, manifest, self.scope, self.agent_id)
        return AgentResult(
            agent_id=self.agent_id,
            outputs={"response": response, "scope": ctx.scope.value},
            cost=usage,
            findings=[],
            status="success",
        )


