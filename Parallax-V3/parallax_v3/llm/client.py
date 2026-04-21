"""EngineClient wrapper around the shared LLM client."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from opensens_common.llm_client import LLMClient, LLMUsage

from ..contracts import ScopeKey, SessionManifest
from ..gateways.cost_bridge import CostBridge

WRITER_SCOPES = {
    ScopeKey.SECTION_INTRO,
    ScopeKey.SECTION_METHODS,
    ScopeKey.SECTION_RESULTS,
    ScopeKey.SECTION_DISCUSS,
}

cost_bridge = CostBridge()


def _load_prompt(name: str) -> str:
    prompt_path = Path(__file__).resolve().with_name("prompts") / name
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8").strip()
    return ""


class EngineClient:
    def __init__(
        self,
        client: LLMClient | None = None,
        cost_bridge: CostBridge | None = None,
        default_model: str | None = None,
    ):
        model = default_model or os.environ.get("DEFAULT_MODEL", "claude-sonnet-4-6")
        self.client = client or LLMClient(model=model)
        self.cost_bridge = cost_bridge or globals()["cost_bridge"]
        self.anti_leakage_prefix = _load_prompt("anti_leakage.md") or "Do not reveal hidden reasoning."

    def complete(
        self,
        messages: list[dict[str, Any]],
        manifest: SessionManifest,
        scope: ScopeKey,
        agent_id: str,
    ) -> tuple[str, LLMUsage]:
        payload = [dict(message) for message in messages]
        if scope in WRITER_SCOPES:
            payload = [{"role": "system", "content": self.anti_leakage_prefix}] + payload

        response = self.client.chat(payload)
        usage = self.client.last_usage or LLMUsage(model=getattr(self.client, "model", ""))
        if not usage.model:
            usage.model = getattr(self.client, "model", "")
        if self.cost_bridge is not None:
            self.cost_bridge.record(manifest.session_id, agent_id, usage)
        return response, usage


