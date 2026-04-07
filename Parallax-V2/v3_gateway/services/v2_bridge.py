"""
V2 Execution Bridge — delegates research phases to the Parallax V2 SDK.

For research phases (search, map, debate, validate, ideate, draft, revise, pass),
V3 delegates execution to the V2 backend using the parallax_sdk.

The bridge:
1. Translates V3 run config into V2 PipelineConfig
2. Runs V2 synchronously in a thread (V2 is sync)
3. Collects V2 events in a thread-safe queue
4. Pumps events into V3 DRVP event bus on the async side
5. Updates V3 phase statuses and cost entries from V2 results
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.workflow import WorkflowRun, Phase
from ..models.base import async_session
from . import event_bus
from .cost_recorder import CostRecorder

logger = logging.getLogger(__name__)

# Phase types that V2 can handle
V2_PHASE_TYPES = {
    "search", "map", "debate", "validate", "ideate", "draft",
    "experiment_plan", "revise", "pass",
}

# Map V2 node types to V3 phase types
V2_TO_V3_PHASE = {
    "search": "search",
    "map": "map",
    "debate": "debate",
    "validate": "validate",
    "ideate": "ideate",
    "draft": "draft",
    "experiment_design": "experiment_plan",
    "revise": "revise",
    "pass": "pass",
}


class V2Bridge:
    """
    Bridge between V3 Gateway and Parallax V2 SDK.
    Uses the V2 SDK in-process — no HTTP server needed.
    """

    def __init__(self):
        self._cost_recorder = CostRecorder()

    def can_handle(self, phase_type: str) -> bool:
        return phase_type in V2_PHASE_TYPES

    async def start_research_pipeline(
        self,
        run: WorkflowRun,
        project_id: str,
    ) -> str:
        """
        Start a V2 research pipeline in a background thread.
        Returns the V2 run_id.

        Events are collected in a thread-safe deque and pumped to the
        V3 DRVP event bus by a concurrent async task.
        """
        config = run.config or {}

        # Thread-safe event collection
        event_queue: deque[dict] = deque(maxlen=5000)
        done_event = threading.Event()

        # Start async event pump
        pump_task = asyncio.create_task(
            self._event_pump(event_queue, done_event, project_id, run.run_id)
        )

        # Run V2 in thread
        loop = asyncio.get_running_loop()
        v2_result = await loop.run_in_executor(
            None,
            self._run_v2_sync,
            config,
            project_id,
            run.run_id,
            event_queue,
            done_event,
        )

        # Wait for event pump to drain
        await pump_task

        # Update V3 run with results
        v2_run_id = v2_result.get("run_id", "")
        summary = v2_result.get("summary", {})
        progress_pct = summary.get("progress_pct", 0)
        failed_count = summary.get("failed", 0)
        if v2_result.get("error") or failed_count:
            status = "failed"
        elif progress_pct == 100:
            status = "completed"
        else:
            status = "paused"

        async with async_session() as session:
            async with session.begin():
                await session.execute(
                    update(WorkflowRun)
                    .where(WorkflowRun.run_id == run.run_id)
                    .values(
                        v2_run_id=v2_run_id,
                        status=status,
                    )
                )

                # Update V3 phases to match V2 node statuses
                if "nodes" in v2_result:
                    await self._sync_v3_phases(session, run.run_id, v2_result["nodes"], project_id)

        return v2_run_id

    async def run_pipeline_background(self, run_id: str, project_id: str) -> None:
        """Load a V3 run and execute it through the V2 bridge."""
        async with async_session() as session:
            async with session.begin():
                run = await session.get(WorkflowRun, run_id)
                if not run:
                    return

        try:
            await self.start_research_pipeline(run, project_id)
        except Exception as e:
            async with async_session() as session:
                async with session.begin():
                    await session.execute(
                        update(WorkflowRun)
                        .where(WorkflowRun.run_id == run_id)
                        .values(status="failed")
                    )

            await event_bus.publish_event(
                "pipeline.failed",
                source_system="v3_gateway",
                project_id=project_id,
                run_id=run_id,
                payload={"error": str(e)},
            )

    def _run_v2_sync(
        self,
        config: dict,
        project_id: str,
        v3_run_id: str,
        event_queue: deque,
        done_event: threading.Event,
    ) -> dict:
        """Synchronous V2 pipeline execution (runs in a thread)."""
        try:
            from parallax_sdk import ParallaxClient, PipelineConfig
            from parallax_sdk.events import PipelineEvent

            v2_config = PipelineConfig(
                research_idea=config.get("research_idea", ""),
                sources=config.get("sources", ["arxiv", "semantic_scholar", "openalex"]),
                max_papers=config.get("max_papers", 100),
                num_ideas=config.get("num_ideas", 10),
                num_reflections=config.get("num_reflections", 3),
                models=config.get("models", {}),
            )

            # Collect events into the thread-safe queue
            class EventCollector:
                def _push(self, event_type: str, event: PipelineEvent):
                    if len(event_queue) == event_queue.maxlen:
                        logger.warning("Event queue full — dropping oldest event for run %s", run.run_id)
                    event_queue.append({
                        "event_type": event_type,
                        "node_type": event.node_type,
                        "node_id": event.node_id,
                        "data": event.data,
                        "timestamp": event.timestamp,
                    })

                def on_node_started(self, event: PipelineEvent):
                    self._push("phase.started", event)

                def on_node_completed(self, event: PipelineEvent):
                    self._push("phase.completed", event)

                def on_node_failed(self, event: PipelineEvent):
                    self._push("phase.failed", event)

                def on_ideas_ready(self, event: PipelineEvent):
                    self._push("ideas.ready", event)

                def on_score_received(self, event: PipelineEvent):
                    self._push("score.received", event)

                def on_feedback_loop(self, event: PipelineEvent):
                    self._push("feedback.loop", event)

                def on_pipeline_completed(self, event: PipelineEvent):
                    self._push("pipeline.completed", event)

                def on_pipeline_failed(self, event: PipelineEvent):
                    self._push("pipeline.failed", event)

            client = ParallaxClient(handlers=[EventCollector()], auto_select_idea=True)
            result = client.run(v2_config)
            client.shutdown()
            return result

        except Exception as e:
            logger.error("V2 pipeline failed: %s", e, exc_info=True)
            event_queue.append({
                "event_type": "pipeline.failed",
                "node_type": "",
                "node_id": "",
                "data": {"error": str(e)},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            return {"error": str(e), "summary": {"progress_pct": 0, "failed": 1}}

        finally:
            done_event.set()

    async def _event_pump(
        self,
        event_queue: deque,
        done_event: threading.Event,
        project_id: str,
        run_id: str,
    ) -> None:
        """Async task that drains the event queue into the V3 DRVP event bus."""
        while not done_event.is_set() or len(event_queue) > 0:
            while len(event_queue) > 0:
                raw = event_queue.popleft()
                await event_bus.publish_event(
                    raw["event_type"],
                    source_system="parallax_v2",
                    project_id=project_id,
                    run_id=run_id,
                    payload={
                        "node_type": raw.get("node_type", ""),
                        "v2_node_id": raw.get("node_id", ""),
                        **raw.get("data", {}),
                    },
                )
            await asyncio.sleep(0.1)  # Check queue every 100ms

    async def _sync_v3_phases(
        self,
        session: AsyncSession,
        v3_run_id: str,
        v2_nodes: list[dict],
        project_id: str,
    ) -> None:
        """Update V3 phase statuses to reflect V2 node results."""
        from sqlalchemy import select

        v3_phases_result = await session.execute(
            select(Phase).where(Phase.run_id == v3_run_id)
        )
        v3_phases = {p.phase_type: p for p in v3_phases_result.scalars().all()}

        for v2_node in v2_nodes:
            v2_type = v2_node.get("node_type", "")
            v3_type = V2_TO_V3_PHASE.get(v2_type)
            if not v3_type or v3_type not in v3_phases:
                continue

            phase = v3_phases[v3_type]
            v2_status = v2_node.get("status", "pending")

            # Map V2 status to V3 status
            status_map = {
                "completed": "completed",
                "running": "running",
                "failed": "failed",
                "pending": "pending",
                "skipped": "skipped",
                "invalidated": "invalidated",
            }
            v3_status = status_map.get(v2_status, "pending")

            values: dict[str, Any] = {
                "status": v3_status,
                "outputs": v2_node.get("outputs", {}),
                "model_used": v2_node.get("model_used", ""),
            }
            if v2_node.get("score") is not None:
                values["score"] = v2_node["score"]
            if v2_status == "completed" and not phase.completed_at:
                values["completed_at"] = datetime.now(timezone.utc)

            await session.execute(
                update(Phase).where(Phase.phase_id == phase.phase_id).values(**values)
            )

            # Record cost if model was used
            model = v2_node.get("model_used", "")
            if model and v2_status == "completed":
                # Estimate cost from outputs if available
                node_costs = v2_node.get("outputs", {}).get("_cost", [])
                total_cost = sum(c.get("cost_usd", 0) for c in node_costs) if node_costs else 0
                if total_cost > 0:
                    await self._cost_recorder.record(
                        session,
                        project_id=project_id,
                        run_id=v3_run_id,
                        phase_id=phase.phase_id,
                        source_system="parallax_v2",
                        model_name=model,
                        cost_usd=total_cost,
                    )
