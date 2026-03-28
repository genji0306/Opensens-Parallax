"""
Bridge between StageExecutor and the SDK event system.

Wraps the DAG execution loop to emit PipelineEvents at each node transition.
This is the core execution driver — the client.py delegates here.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, List, Optional

from .events import EventType, PipelineEvent

logger = logging.getLogger(__name__)


def _emit(handlers: List[Any], event: PipelineEvent) -> None:
    """Dispatch event to all handlers. Swallows handler errors to avoid breaking the pipeline."""
    method_name = f"on_{event.event_type.value}"
    for h in handlers:
        fn = getattr(h, method_name, None)
        if fn is not None:
            try:
                fn(event)
            except Exception as exc:
                logger.warning("Event handler %s.%s raised: %s",
                               type(h).__name__, method_name, exc)


def execute_pipeline(
    run_id: str,
    handlers: List[Any],
    auto_select_idea: bool = True,
    idea_selector: Optional[Callable[[List[Dict]], Dict]] = None,
    task_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Drive a pipeline run to completion, firing events along the way.

    This is the main execution loop. It iterates over the DAG using
    WorkflowEngine.get_next_executable(), executes each ready node via
    StageExecutor, and emits events before/after each transition.

    Args:
        run_id: Pipeline run ID (must already exist with graph created).
        handlers: List of objects with on_* event methods.
        auto_select_idea: If True, auto-select the top-ranked idea.
        idea_selector: Custom callable(ideas_list) -> selected_idea_dict.
                       Overrides auto_select_idea when provided.
        task_id: Optional TaskManager task ID for progress tracking.

    Returns:
        Final graph state dict with nodes, edges, and summary.
    """
    from app.services.workflow.engine import WorkflowEngine
    from app.services.workflow.executor import StageExecutor
    from app.models.workflow_models import NodeType, NodeStatus, WorkflowNodeDAO
    from app.models.ais_models import PipelineRunDAO, PipelineStatus
    from opensens_common.task import TaskManager

    engine = WorkflowEngine()
    executor = StageExecutor()
    tm = TaskManager()

    if not task_id:
        task_id = tm.create_task("sdk_pipeline", metadata={"run_id": run_id})

    # Safety cap: 9 nodes + up to 3 revision loops * 2 nodes each = ~15 max
    max_iterations = 30

    for _iteration in range(max_iterations):
        ready = engine.get_next_executable(run_id)
        if not ready:
            break

        for node in ready:
            # -- NODE_STARTED --
            _emit(handlers, PipelineEvent(
                event_type=EventType.NODE_STARTED,
                run_id=run_id,
                node_type=node.node_type.value,
                node_id=node.node_id,
            ))

            try:
                executor.execute_node(run_id, node.node_id, task_id)
            except Exception as e:
                _emit(handlers, PipelineEvent(
                    event_type=EventType.NODE_FAILED,
                    run_id=run_id,
                    node_type=node.node_type.value,
                    node_id=node.node_id,
                    data={"error": str(e)},
                ))
                _emit(handlers, PipelineEvent(
                    event_type=EventType.PIPELINE_FAILED,
                    run_id=run_id,
                    data={"error": str(e), "failed_node": node.node_type.value},
                ))
                return engine.get_graph_state(run_id)

            # Reload node to get outputs and score
            updated = WorkflowNodeDAO.load(node.node_id)
            outputs = updated.outputs if updated else {}
            score = updated.score if updated else None

            # -- NODE_COMPLETED --
            _emit(handlers, PipelineEvent(
                event_type=EventType.NODE_COMPLETED,
                run_id=run_id,
                node_type=node.node_type.value,
                node_id=node.node_id,
                data=outputs,
            ))

            # -- IDEAS_READY (after Ideate node) --
            if node.node_type == NodeType.IDEATE:
                _emit(handlers, PipelineEvent(
                    event_type=EventType.IDEAS_READY,
                    run_id=run_id,
                    node_type="ideate",
                    node_id=node.node_id,
                    data={"idea_count": outputs.get("idea_count", 0)},
                ))
                # Pipeline pauses here for idea selection
                _handle_idea_selection(run_id, auto_select_idea, idea_selector)

            # -- SCORE_RECEIVED (after Validate or Revise) --
            if score is not None and node.node_type in (NodeType.VALIDATE, NodeType.REVISE):
                _emit(handlers, PipelineEvent(
                    event_type=EventType.SCORE_RECEIVED,
                    run_id=run_id,
                    node_type=node.node_type.value,
                    node_id=node.node_id,
                    data={"score": score},
                ))

            # -- FEEDBACK_LOOP (Revise triggers loop back) --
            # Note: handle_revise_completion is already called inside executor.execute_node
            # for the REVISE node type, so we just check the resulting state
            if node.node_type == NodeType.REVISE and score is not None:
                # Re-read to check if the engine looped back
                revise_node = WorkflowNodeDAO.load(node.node_id)
                if revise_node and revise_node.status == NodeStatus.PENDING:
                    # The engine reset this node — feedback loop triggered
                    revision_count = revise_node.outputs.get("revision_count", 0)
                    _emit(handlers, PipelineEvent(
                        event_type=EventType.FEEDBACK_LOOP,
                        run_id=run_id,
                        node_type="revise",
                        node_id=node.node_id,
                        data={
                            "score": score,
                            "revision": revision_count,
                            "reason": revise_node.outputs.get("loop_reason", ""),
                        },
                    ))
                    # Continue the outer loop — get_next_executable will find
                    # Validate reset to PENDING

        # Check if pipeline is complete
        if engine.is_pipeline_complete(run_id):
            PipelineRunDAO.update_status(run_id, PipelineStatus.COMPLETED)

            revise = engine.get_node_by_type(run_id, NodeType.REVISE)
            final_score = revise.score if revise and revise.score else 0

            _emit(handlers, PipelineEvent(
                event_type=EventType.PIPELINE_COMPLETED,
                run_id=run_id,
                data={"score": final_score},
            ))
            break

    return engine.get_graph_state(run_id)


def _handle_idea_selection(
    run_id: str,
    auto_select: bool,
    idea_selector: Optional[Callable[[List[Dict]], Dict]],
) -> None:
    """Select an idea to continue the pipeline past the Ideate gate."""
    from app.services.ais.idea_generator import IdeaGenerator
    from app.models.ais_models import PipelineRunDAO, PipelineStatus

    generator = IdeaGenerator()
    ideas = generator.get_ideas_by_run(run_id)
    if not ideas:
        logger.warning("No ideas generated for run %s", run_id)
        return

    idea_dicts = [i.to_dict() for i in ideas]

    if idea_selector:
        selected = idea_selector(idea_dicts)
    elif auto_select:
        selected = max(idea_dicts, key=lambda x: x.get("composite_score", 0))
    else:
        raise RuntimeError(
            "Pipeline paused at idea selection. "
            "Provide idea_selector callback or set auto_select_idea=True."
        )

    idea_id = selected.get("idea_id") or selected.get("id")
    if not idea_id:
        raise RuntimeError(f"Selected idea has no idea_id: {selected}")

    # Store selection in stage_results (mirrors the route logic in ais_routes.py)
    run = PipelineRunDAO.load(run_id)
    if run:
        run.stage_results["selected_idea_id"] = idea_id
        run.status = PipelineStatus.DEBATING
        run.current_stage = 3
        PipelineRunDAO.save(run)

    logger.info("Auto-selected idea %s for run %s: %s",
                idea_id, run_id, selected.get("title", "")[:60])
