"""
Unified Cost Recorder — tracks every dollar spent across all subsystems.

Records costs to the PostgreSQL cost_entries table and updates
project/run budget counters. Emits budget warning/exhaustion events.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.cost import CostEntry
from ..models.project import Project
from ..models.workflow import WorkflowRun
from . import event_bus

logger = logging.getLogger(__name__)

# Model pricing (USD per 1M tokens) — same as V2 CostTracker
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-opus-4-20250514": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.0},
    "gpt-4o": {"input": 2.50, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "default": {"input": 3.0, "output": 15.0},
}


class CostRecorder:
    """Records costs and enforces budget limits."""

    def calculate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Calculate USD cost from token counts."""
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
        return (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000

    async def record(
        self,
        session: AsyncSession,
        project_id: str,
        run_id: str | None = None,
        phase_id: str | None = None,
        agent_id: str | None = None,
        source_system: str = "parallax",
        cost_type: str = "llm_call",
        model_name: str | None = None,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost_usd: float | None = None,
    ) -> CostEntry:
        """
        Record a cost entry. If cost_usd is not provided, calculates from tokens.
        Updates project and run budget counters. Emits budget events if thresholds crossed.
        """
        if cost_usd is None and model_name:
            cost_usd = self.calculate_cost(model_name, tokens_in, tokens_out)
        cost_usd = cost_usd or 0.0

        entry = CostEntry(
            project_id=project_id,
            run_id=run_id,
            phase_id=phase_id,
            agent_id=agent_id,
            source_system=source_system,
            cost_type=cost_type,
            model_name=model_name,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
        )
        session.add(entry)

        # Update project budget counter
        project = await session.get(Project, project_id)
        if project:
            project.budget_spent_usd = (project.budget_spent_usd or 0) + cost_usd

            # Budget warnings
            pct = project.budget_spent_usd / max(project.budget_cap_usd, 0.01)
            if pct >= 1.0:
                await event_bus.publish_event(
                    "budget.exhausted",
                    project_id=project_id,
                    run_id=run_id,
                    payload={"spent": project.budget_spent_usd, "cap": project.budget_cap_usd},
                )
            elif pct >= 0.8:
                await event_bus.publish_event(
                    "budget.warning",
                    project_id=project_id,
                    run_id=run_id,
                    payload={"spent": project.budget_spent_usd, "cap": project.budget_cap_usd, "pct": round(pct * 100, 1)},
                )

        # Update run budget counter
        if run_id:
            await session.execute(
                update(WorkflowRun)
                .where(WorkflowRun.run_id == run_id)
                .values(budget_spent_usd=WorkflowRun.budget_spent_usd + cost_usd)
            )

        return entry

    async def get_project_cost(self, session: AsyncSession, project_id: str) -> dict[str, Any]:
        """Get cost summary for a project."""
        result = await session.execute(
            select(
                func.sum(CostEntry.cost_usd).label("total"),
                func.sum(CostEntry.tokens_in).label("tokens_in"),
                func.sum(CostEntry.tokens_out).label("tokens_out"),
                func.count(CostEntry.entry_id).label("count"),
            ).where(CostEntry.project_id == project_id)
        )
        row = result.one()
        return {
            "project_id": project_id,
            "total_cost_usd": round(row.total or 0, 4),
            "total_tokens_in": row.tokens_in or 0,
            "total_tokens_out": row.tokens_out or 0,
            "entry_count": row.count or 0,
        }

    async def get_run_cost(self, session: AsyncSession, run_id: str) -> dict[str, Any]:
        """Get cost breakdown for a workflow run."""
        result = await session.execute(
            select(
                CostEntry.phase_id,
                CostEntry.model_name,
                func.sum(CostEntry.cost_usd).label("cost"),
                func.sum(CostEntry.tokens_in).label("tokens_in"),
                func.sum(CostEntry.tokens_out).label("tokens_out"),
                func.count(CostEntry.entry_id).label("calls"),
            )
            .where(CostEntry.run_id == run_id)
            .group_by(CostEntry.phase_id, CostEntry.model_name)
        )
        rows = result.all()

        by_phase: dict[str, dict] = {}
        total = 0.0
        for row in rows:
            pid = row.phase_id or "unattributed"
            if pid not in by_phase:
                by_phase[pid] = {"cost_usd": 0, "calls": 0, "models": {}}
            by_phase[pid]["cost_usd"] += row.cost or 0
            by_phase[pid]["calls"] += row.calls or 0
            model = row.model_name or "unknown"
            by_phase[pid]["models"][model] = round(row.cost or 0, 4)
            total += row.cost or 0

        return {
            "run_id": run_id,
            "total_cost_usd": round(total, 4),
            "by_phase": {k: {**v, "cost_usd": round(v["cost_usd"], 4)} for k, v in by_phase.items()},
        }

    async def check_budget(self, session: AsyncSession, project_id: str) -> dict[str, Any]:
        """Check if project has budget remaining. Used by middleware."""
        project = await session.get(Project, project_id)
        if not project:
            return {"allowed": False, "reason": "Project not found"}

        remaining = project.budget_cap_usd - (project.budget_spent_usd or 0)
        return {
            "allowed": remaining > 0,
            "remaining_usd": round(remaining, 4),
            "spent_usd": round(project.budget_spent_usd or 0, 4),
            "cap_usd": project.budget_cap_usd,
        }
