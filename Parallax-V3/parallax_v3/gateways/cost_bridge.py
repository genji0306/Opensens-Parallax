"""Cost bridge to the V2/v3_gateway ledger."""

from __future__ import annotations

from dataclasses import dataclass

from opensens_common.llm_client import LLMUsage
from parallax_v2.v3_gateway.services.cost_recorder import CostRecorder

from ..errors import ParallaxV3Error


class CostBridgeError(ParallaxV3Error):
    """Raised when cost recording fails."""


class CostBridge:
    def __init__(self, recorder: CostRecorder | None = None):
        self.recorder = recorder or CostRecorder()

    def record(self, session_id: str, agent_id: str, usage: LLMUsage):
        payload = {
            "session_id": session_id,
            "agent_id": agent_id,
            "model_name": usage.model,
            "tokens_in": usage.input_tokens,
            "tokens_out": usage.output_tokens,
            "cached": usage.cached,
        }
        if hasattr(self.recorder, "record_cost"):
            return self.recorder.record_cost(**payload)
        return self.recorder.record(**payload)

