"""Minimal cost recorder shim used by the V3 cost bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "default": {"input": 3.0, "output": 15.0},
}


@dataclass
class CostRecord:
    session_id: str
    agent_id: str
    model_name: str | None
    tokens_in: int
    tokens_out: int
    cost_usd: float
    cached: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class CostRecorder:
    def __init__(self):
        self.entries: list[CostRecord] = []

    def calculate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        return (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000

    def record_cost(
        self,
        *,
        session_id: str,
        agent_id: str,
        model_name: str | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float | None = None,
        cached: bool = False,
        **metadata: Any,
    ) -> CostRecord:
        if cached:
            cost_usd = 0.0
        elif cost_usd is None:
            cost_usd = self.calculate_cost(model_name or "default", tokens_in, tokens_out)
        record = CostRecord(
            session_id=session_id,
            agent_id=agent_id,
            model_name=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=float(cost_usd or 0.0),
            cached=cached,
            metadata=dict(metadata),
        )
        self.entries.append(record)
        return record

    async def record(self, *args: Any, **kwargs: Any) -> CostRecord:
        return self.record_cost(*args, **kwargs)


