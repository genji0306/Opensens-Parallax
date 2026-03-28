"""
ParallaxClient -- the main SDK class.

Thin wrapper over WorkflowEngine + StageExecutor with event callbacks.
Designed for agent swarm integration: supports concurrent background runs,
custom event handlers, and programmatic idea selection.
"""

from __future__ import annotations

import logging
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .events import LoggingHandler, PipelineEvent

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for a single pipeline run."""

    research_idea: str
    sources: List[str] = field(
        default_factory=lambda: ["arxiv", "semantic_scholar", "openalex"]
    )
    max_papers: int = 100
    num_ideas: int = 10
    num_reflections: int = 3
    min_score: float = 6.0
    max_revisions: int = 3
    step_settings: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # Per-node model overrides: {"search": "claude-haiku-4-5-20251001", "draft": "claude-opus-4-20250514"}
    models: Dict[str, str] = field(default_factory=dict)

    def to_run_config(self) -> Dict[str, Any]:
        """Convert to the dict format expected by PipelineRun.config."""
        ss = dict(self.step_settings)
        for node_type, model in self.models.items():
            ss.setdefault(node_type, {})["model"] = model
        return {
            "sources": self.sources,
            "max_papers": self.max_papers,
            "num_ideas": self.num_ideas,
            "num_reflections": self.num_reflections,
            "step_settings": ss,
        }


class ParallaxClient:
    """
    Programmatic interface to the Parallax V2 research pipeline.

    Usage (synchronous):
        from parallax_sdk import ParallaxClient, PipelineConfig

        client = ParallaxClient()
        result = client.run(PipelineConfig(
            research_idea="Novel approaches to protein folding using GNNs",
            models={"draft": "claude-opus-4-20250514"},
        ))

    Usage (background / agent swarm):
        future = client.run_async(config)
        # ... agent does other work ...
        result = future.result(timeout=3600)

    Usage (concurrent swarm):
        futures = [
            client.run_async(PipelineConfig(research_idea=idea))
            for idea in ideas
        ]
        results = [f.result() for f in futures]
    """

    def __init__(
        self,
        handlers: Optional[List[Any]] = None,
        max_workers: int = 4,
        auto_select_idea: bool = True,
        env_path: Optional[str] = None,
    ):
        """
        Args:
            handlers: Event handler objects (any object with on_* methods).
                      If None, uses LoggingHandler.
            max_workers: Thread pool size for concurrent async runs.
            auto_select_idea: If True, auto-select the top-ranked idea.
            env_path: Optional path to .env file for backend configuration.
        """
        from ._bootstrap import get_app

        self._app = get_app(env_path=env_path)
        self._handlers = handlers if handlers is not None else [LoggingHandler()]
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="parallax"
        )
        self._auto_select = auto_select_idea

    # ── Synchronous API ──────────────────────────────────────────

    def run(
        self,
        config: PipelineConfig,
        idea_selector: Optional[Callable[[List[Dict]], Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Run a full pipeline synchronously. Blocks until completion or failure.

        Args:
            config: Pipeline configuration.
            idea_selector: Custom idea selection function.
                           Receives list of idea dicts, returns the chosen one.

        Returns:
            Graph state dict with nodes, edges, summary.
        """
        run_id = self._create_run(config)
        logger.info("Starting pipeline %s: %s", run_id, config.research_idea[:80])

        from ._executor_bridge import execute_pipeline

        return execute_pipeline(
            run_id=run_id,
            handlers=self._handlers,
            auto_select_idea=self._auto_select,
            idea_selector=idea_selector,
        )

    def run_async(
        self,
        config: PipelineConfig,
        idea_selector: Optional[Callable[[List[Dict]], Dict]] = None,
    ) -> Future:
        """
        Run a pipeline in the background. Returns a concurrent.futures.Future.

        The Future resolves to the same graph state dict as run().
        Events fire on the background thread.
        """
        run_id = self._create_run(config)
        logger.info("Starting async pipeline %s: %s", run_id, config.research_idea[:80])

        def _bg():
            # Each thread needs its own app context for DB connections
            with self._app.app_context():
                from ._executor_bridge import execute_pipeline

                return execute_pipeline(
                    run_id=run_id,
                    handlers=self._handlers,
                    auto_select_idea=self._auto_select,
                    idea_selector=idea_selector,
                )

        return self._pool.submit(_bg)

    # ── Query API ────────────────────────────────────────────────

    def get_status(self, run_id: str) -> Dict[str, Any]:
        """Get current graph state for a run."""
        from app.services.workflow.engine import WorkflowEngine

        return WorkflowEngine().get_graph_state(run_id)

    def get_ideas(self, run_id: str) -> List[Dict[str, Any]]:
        """Get ranked ideas for a run (available after Ideate completes)."""
        from app.services.ais.idea_generator import IdeaGenerator

        ideas = IdeaGenerator().get_ideas_by_run(run_id)
        return [i.to_dict() for i in ideas] if ideas else []

    def get_cost(self, run_id: str) -> Dict[str, Any]:
        """Get cost breakdown for a run."""
        from app.services.workflow.cost_tracker import CostTracker

        return CostTracker().get_run_cost(run_id)

    def list_runs(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List pipeline runs, optionally filtered by status."""
        from app.db import get_connection

        conn = get_connection()
        if status:
            rows = conn.execute(
                "SELECT * FROM ais_pipeline_runs WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM ais_pipeline_runs ORDER BY created_at DESC"
            ).fetchall()

        import json

        results = []
        for row in rows:
            results.append({
                "run_id": row["run_id"],
                "research_idea": row["research_idea"],
                "status": row["status"],
                "current_stage": row["current_stage"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "error": row["error"],
            })
        return results

    def restart_from(self, run_id: str, node_type: str) -> Dict[str, Any]:
        """
        Restart a pipeline from a specific node type (e.g., "debate", "draft").
        Invalidates all downstream nodes.
        """
        from app.services.workflow.engine import WorkflowEngine
        from app.models.workflow_models import NodeType

        engine = WorkflowEngine()
        node = engine.get_node_by_type(run_id, NodeType(node_type))
        if not node:
            raise ValueError(f"No node of type '{node_type}' in run {run_id}")
        return engine.restart_from_node(run_id, node.node_id)

    def export(self, run_id: str, fmt: str = "markdown") -> str:
        """
        Export a completed pipeline's paper draft.

        Args:
            run_id: Pipeline run ID.
            fmt: Export format ("markdown" or "json").

        Returns:
            Formatted string content.
        """
        import json
        from app.models.ais_models import PipelineRunDAO

        run = PipelineRunDAO.load(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        stage_5 = run.stage_results.get("stage_5", {})
        draft_id = stage_5.get("draft_id")

        if not draft_id:
            raise ValueError(f"No draft available for run {run_id}")

        if fmt == "json":
            return json.dumps(stage_5, indent=2, default=str)

        # Markdown export
        from app.services.ais.paper_draft_generator import PaperDraftGenerator

        gen = PaperDraftGenerator()
        draft = gen.get_draft_by_run(run_id)
        if not draft:
            raise ValueError(f"Draft not found for run {run_id}")

        sections = []
        for s in draft.sections:
            sections.append(f"## {s.title}\n\n{s.content}")
        return f"# {draft.title}\n\n" + "\n\n".join(sections)

    # ── Internal ─────────────────────────────────────────────────

    def _create_run(self, config: PipelineConfig) -> str:
        """Create a PipelineRun + workflow graph. Returns run_id."""
        from app.models.ais_models import PipelineRun, PipelineRunDAO
        from app.services.workflow.engine import WorkflowEngine

        run = PipelineRun(
            run_id="",
            research_idea=config.research_idea,
            config=config.to_run_config(),
        )
        PipelineRunDAO.save(run)

        engine = WorkflowEngine()
        engine.create_pipeline_graph(
            run.run_id,
            config=run.config,
            step_settings=config.to_run_config().get("step_settings", {}),
        )

        logger.info("Created pipeline run %s", run.run_id)
        return run.run_id

    def shutdown(self) -> None:
        """Shut down the thread pool. Call when done with the client."""
        self._pool.shutdown(wait=True)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.shutdown()
