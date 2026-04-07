"""
Stage Executor
Bridges the WorkflowEngine DAG with actual pipeline stage execution.

Responsibilities:
- Resolve the model for a node (model_config > project default > system default)
- Execute a single node by dispatching to the appropriate service
- Auto-advance: after completing a node, find and execute the next ready nodes
- Track cost per node via CostTracker

Usage from routes:
    executor = StageExecutor()
    executor.execute_node(run_id, node_id, task_id)     # single node
    executor.auto_advance(run_id, task_id)               # run all ready nodes
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from opensens_common.config import Config
from opensens_common.task import TaskManager, TaskStatus

from ...db import get_connection
from ...models.ais_models import PipelineRunDAO, PipelineStatus
from ...models.workflow_models import NodeStatus, NodeType, WorkflowNode, WorkflowNodeDAO
from .engine import WorkflowEngine
from .cost_tracker import CostTracker

logger = logging.getLogger(__name__)

# Default model when nothing is configured
SYSTEM_DEFAULT_MODEL = "claude-sonnet-4-20250514"


class StageExecutor:
    """Executes individual DAG nodes by dispatching to pipeline services."""

    def __init__(self):
        self.wf = WorkflowEngine()
        self.tm = TaskManager()
        self.costs = CostTracker()

    # ── Model Resolution ────────────────────────────────────────────

    def resolve_model(self, node: WorkflowNode, run_id: str) -> str:
        """
        Resolve the model to use for a node.
        Priority: node.model_config > project step_settings > system default.
        """
        # 1. Per-node model_config (set via UI StageCard dropdown)
        if node.model_config and node.model_config.get("model"):
            return node.model_config["model"]

        # 2. Project-level step_settings (set at pipeline start)
        run = PipelineRunDAO.load(run_id)
        if run and run.config:
            step_settings = run.config.get("step_settings", {})
            node_settings = step_settings.get(node.node_type.value, {})
            if isinstance(node_settings, dict) and node_settings.get("model"):
                return node_settings["model"]

        # 3. System default
        try:
            cfg = Config()
            return getattr(cfg, "default_model", SYSTEM_DEFAULT_MODEL)
        except Exception:
            return SYSTEM_DEFAULT_MODEL

    # ── Single Node Execution ───────────────────────────────────────

    def execute_node(self, run_id: str, node_id: str, task_id: str):
        """
        Execute a single workflow node.
        Resolves the model, dispatches to the correct service, updates status.
        """
        node = WorkflowNodeDAO.load(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")
        if node.run_id != run_id:
            raise ValueError(f"Node {node_id} does not belong to run {run_id}")

        model = self.resolve_model(node, run_id)
        logger.info("[Executor] Running node %s (%s) with model=%s",
                     node_id, node.node_type.value, model)

        self.wf.mark_node_running(node_id, model_used=model)

        # Set cost tracking context so LLMClient._cost_hook knows which node is active
        try:
            from flask import current_app
            cost_ctx = getattr(current_app, "_cost_context", None)
            if cost_ctx is not None:
                cost_ctx.node_id = node_id
        except Exception:
            pass

        try:
            handler = self._get_handler(node.node_type)
            if handler is None:
                raise ValueError(f"No handler for node type: {node.node_type.value}")

            outputs = handler(run_id, node, model, task_id)
            score = outputs.pop("_score", None) if isinstance(outputs, dict) else None

            self.wf.complete_node(node_id, outputs or {}, score=score, model_used=model)
            logger.info("[Executor] Node %s completed (score=%s)", node_id, score)

            # Handle revision feedback loop
            if node.node_type == NodeType.REVISE and score is not None:
                self.wf.handle_revise_completion(run_id, node_id, score)

        except Exception as e:
            logger.error("[Executor] Node %s failed: %s", node_id, e, exc_info=True)
            self.wf.fail_node(node_id, str(e))
            raise
        finally:
            # Clear cost context
            try:
                from flask import current_app
                cost_ctx = getattr(current_app, "_cost_context", None)
                if cost_ctx is not None:
                    cost_ctx.node_id = None
            except Exception:
                pass

    # ── Auto-Advance ────────────────────────────────────────────────

    def auto_advance(self, run_id: str, task_id: str):
        """
        After a node completes, find all newly-ready nodes and execute them.
        Stops when no more nodes are executable or pipeline reaches a
        human-gated stage (idea selection, human review).
        """
        max_iterations = 20  # safety cap
        for _ in range(max_iterations):
            ready = self.wf.get_next_executable(run_id)
            if not ready:
                break

            # Filter out human-gated stages
            auto_executable = [
                n for n in ready
                if n.node_type not in (NodeType.HUMAN_REVIEW,)
            ]
            if not auto_executable:
                break

            for node in auto_executable:
                try:
                    self.execute_node(run_id, node.node_id, task_id)
                except Exception as e:
                    logger.error("[Executor] Auto-advance stopped: node %s failed: %s",
                                 node.node_id, e)
                    return

        # Check if pipeline is complete
        if self.wf.is_pipeline_complete(run_id):
            PipelineRunDAO.update_status(run_id, PipelineStatus.COMPLETED)
            logger.info("[Executor] Pipeline %s completed", run_id)

    # ── Handlers ────────────────────────────────────────────────────

    def _get_handler(self, node_type: NodeType):
        """Map node types to execution handlers."""
        handlers = {
            NodeType.SEARCH: self._handle_search,
            NodeType.MAP: self._handle_map,
            NodeType.IDEATE: self._handle_ideate,
            NodeType.DEBATE: self._handle_debate,
            NodeType.VALIDATE: self._handle_validate,
            NodeType.DRAFT: self._handle_draft,
            NodeType.EXPERIMENT_DESIGN: self._handle_experiment_design,
            NodeType.REVISE: self._handle_revise,
            NodeType.PASS: self._handle_pass,
        }
        return handlers.get(node_type)

    def _handle_search(self, run_id: str, node: WorkflowNode, model: str, task_id: str) -> Dict:
        """Execute literature search (crawl)."""
        from ..academic_ingestion import IngestionPipeline

        run = PipelineRunDAO.load(run_id)
        sources = node.config.get("sources", run.config.get("sources", ["arxiv", "semantic_scholar"]))
        max_papers = node.config.get("max_papers", run.config.get("max_papers", 100))

        self.tm.update_task(task_id, progress=5, message="Searching academic databases...")

        pipeline = IngestionPipeline()
        result = pipeline.ingest(
            query=run.research_idea,
            sources=sources,
            max_results=max_papers,
        )

        paper_count = result.get("total_ingested", 0) if isinstance(result, dict) else 0
        PipelineRunDAO.update_stage_result(run_id, "stage_1", {"paper_count": paper_count})

        return {"paper_count": paper_count, "sources": sources}

    def _handle_map(self, run_id: str, node: WorkflowNode, model: str, task_id: str) -> Dict:
        """Execute topic mapping."""
        from ..research_mapper import ResearchMapper

        self.tm.update_task(task_id, progress=15, message="Mapping research landscape...")

        mapper = ResearchMapper()
        result = mapper.map_topics(run_id=run_id, model=model)

        topic_count = result.get("topic_count", 0) if isinstance(result, dict) else 0
        PipelineRunDAO.update_stage_result(run_id, "map", result or {})

        return {"topic_count": topic_count}

    def _handle_ideate(self, run_id: str, node: WorkflowNode, model: str, task_id: str) -> Dict:
        """Execute idea generation."""
        from .._compat import get_idea_generator

        run = PipelineRunDAO.load(run_id)
        num_ideas = node.config.get("num_ideas", 10)
        num_reflections = node.config.get("num_reflections", 3)

        self.tm.update_task(task_id, progress=20, message="Generating research ideas...")

        generator = get_idea_generator()
        ideas = generator.generate(
            run_id=run_id,
            num_ideas=num_ideas,
            num_reflections=num_reflections,
            model=model,
        )

        idea_count = len(ideas) if ideas else 0
        PipelineRunDAO.update_stage_result(run_id, "stage_2", {"idea_count": idea_count})

        # Pipeline pauses here for human idea selection
        PipelineRunDAO.update_status(run_id, PipelineStatus.AWAITING_SELECTION, stage=2)

        return {"idea_count": idea_count}

    def _handle_debate(self, run_id: str, node: WorkflowNode, model: str, task_id: str) -> Dict:
        """Execute agent debate. Delegates to AisPipeline.run_stage_3."""
        from ..ais.pipeline import AisPipeline
        pipeline = AisPipeline()
        pipeline.run_stage_3(run_id, task_id)

        # Read back results
        run = PipelineRunDAO.load(run_id)
        stage_3 = run.stage_results.get("stage_3", {}) if run else {}
        return {
            "simulation_id": stage_3.get("simulation_id", ""),
            "total_turns": stage_3.get("total_turns", 0),
        }

    def _handle_validate(self, run_id: str, node: WorkflowNode, model: str, task_id: str) -> Dict:
        """Execute specialist review (validation)."""
        from ..ais.specialist_review import SpecialistReview

        self.tm.update_task(task_id, progress=50, message="Running specialist validation...")

        run = PipelineRunDAO.load(run_id)
        # Get draft content for review
        draft_content = ""
        stage_5 = run.stage_results.get("stage_5", {}) if run else {}
        draft_id = stage_5.get("draft_id")
        if draft_id:
            from ..ais.paper_draft_generator import PaperDraftGenerator
            gen = PaperDraftGenerator()
            draft = gen.get_draft_by_run(run_id)
            if draft:
                draft_content = "\n\n".join(s.content for s in draft.sections)

        if not draft_content:
            # Fallback: use research idea as review target
            draft_content = run.research_idea if run else ""

        reviewer = SpecialistReview()
        domains = node.config.get("specialist_domains", [])
        if not domains:
            domains = reviewer.detect_relevant_domains(draft_content)

        results = reviewer.review(
            content=draft_content,
            domains=domains,
            model=model,
        )

        avg_score = sum(r.overall_score for r in results) / max(len(results), 1) if results else 0
        PipelineRunDAO.update_stage_result(run_id, "validation", {
            "domain_count": len(results),
            "avg_score": round(avg_score, 1),
            "reviews": [r.to_dict() for r in results] if results else [],
        })

        return {
            "domain_count": len(results),
            "avg_score": round(avg_score, 1),
            "_score": round(avg_score, 1),
        }

    def _handle_draft(self, run_id: str, node: WorkflowNode, model: str, task_id: str) -> Dict:
        """Execute paper draft generation. Delegates to AisPipeline.run_stage_5."""
        from ..ais.pipeline import AisPipeline
        pipeline = AisPipeline()
        pipeline.run_stage_5(run_id, task_id)

        run = PipelineRunDAO.load(run_id)
        stage_5 = run.stage_results.get("stage_5", {}) if run else {}
        return {
            "draft_id": stage_5.get("draft_id", ""),
            "word_count": stage_5.get("total_word_count", 0),
            "_score": stage_5.get("review_overall", 0),
        }

    def _handle_experiment_design(self, run_id: str, node: WorkflowNode, model: str, task_id: str) -> Dict:
        """Execute experiment design + run. Routes to V1 or V2 based on node config."""
        from ..ais.pipeline import AisPipeline

        # Read ais_version from node config (set via stage settings UI)
        node_config = node.config if isinstance(node.config, dict) else {}
        version = node_config.get("ais_version", "v1")

        # Build config overrides from node settings
        config_overrides = {}
        if version == "v2":
            config_overrides["bfts_profile"] = node_config.get("bfts_profile", "standard")
            config_overrides["include_writeup"] = node_config.get("include_writeup", False)
            bfts_config = node_config.get("bfts_config", {})
            if bfts_config:
                config_overrides["bfts_config"] = bfts_config

        pipeline = AisPipeline()
        pipeline.run_stage_6(run_id, task_id, config_overrides=config_overrides or None, version=version)

        # After completion, feed V2 costs into CostTracker
        run = PipelineRunDAO.load(run_id)
        stage_6 = run.stage_results.get("stage_6", {}) if run else {}

        if version == "v2":
            self._record_v2_costs(node.node_id, run_id)

        return {
            "spec_id": stage_6.get("spec_id", ""),
            "template": stage_6.get("template", ""),
            "version": version,
            "_score": 7.0 if stage_6.get("status") == "completed" else 3.0,
        }

    def _record_v2_costs(self, node_id: str, run_id: str):
        """Feed V2 experiment token costs into CostTracker from experiment results."""
        try:
            from .cost_tracker import CostTracker
            conn = get_connection()
            # Find the latest V2 result for this run
            row = conn.execute(
                "SELECT token_usage FROM experiment_results WHERE run_id = ? ORDER BY completed_at DESC LIMIT 1",
                (run_id,),
            ).fetchone()
            if not row or not row["token_usage"]:
                return

            import json
            token_usage = json.loads(row["token_usage"])
            by_model = token_usage.get("by_model", {})
            tracker = CostTracker()
            for model_name, usage in by_model.items():
                if isinstance(usage, dict) and usage.get("input_tokens", 0) > 0:
                    tracker.record(
                        node_id=node_id,
                        model=model_name,
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                    )
        except Exception as e:
            logger.warning("[Executor] Failed to record V2 costs: %s", e)

    def _handle_revise(self, run_id: str, node: WorkflowNode, model: str, task_id: str) -> Dict:
        """Execute revision scoring. Reads validation + draft scores, determines pass/loop/fail."""
        self.tm.update_task(task_id, progress=80, message="Scoring for revision...")

        run = PipelineRunDAO.load(run_id)
        validation = run.stage_results.get("validation", {}) if run else {}
        stage_5 = run.stage_results.get("stage_5", {}) if run else {}

        # Composite score from validation + draft review
        val_score = validation.get("avg_score", 0)
        draft_score = stage_5.get("review_overall", 0)
        composite = (val_score + draft_score) / 2 if val_score and draft_score else max(val_score, draft_score)

        revision_count = node.outputs.get("revision_count", 0)

        return {
            "composite_score": round(composite, 1),
            "validation_score": val_score,
            "draft_score": draft_score,
            "revision_count": revision_count,
            "_score": round(composite, 1),
        }

    def _handle_pass(self, run_id: str, node: WorkflowNode, model: str, task_id: str) -> Dict:
        """Terminal node — marks pipeline as complete."""
        self.tm.update_task(task_id, progress=100, message="Pipeline complete")

        run = PipelineRunDAO.load(run_id)
        revise_node = self.wf.get_node_by_type(run_id, NodeType.REVISE)
        final_score = revise_node.score if revise_node and revise_node.score else 0

        PipelineRunDAO.update_status(run_id, PipelineStatus.COMPLETED)

        return {
            "final_score": final_score,
            "revision_count": revise_node.outputs.get("revision_count", 0) if revise_node else 0,
            "_score": final_score,
        }
