"""
Workflow Graph Engine
Manages DAG-based research pipelines with checkpointing, restart, and dependency tracking.

The default pipeline graph:

  Search ──→ Map ──┬──→ Debate ──→ Validate
                   │               (specialist review)
                   └──→ Ideate ──→ Draft ──→ Experiment Design ──→ Revise ──→ (pass if score high)
                                   ↑                               ↑
                                   └── (experiment data) ──────────┘

Each node stores its own config, inputs, outputs, status, score, and model provenance.
Restart from any node invalidates all downstream nodes and re-executes.
"""

import logging
import threading
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from ...models.workflow_models import (
    NodeStatus,
    NodeType,
    StepSettings,
    WorkflowEdge,
    WorkflowEdgeDAO,
    WorkflowNode,
    WorkflowNodeDAO,
)
from ...models.ais_models import PipelineRun, PipelineRunDAO, PipelineStatus

logger = logging.getLogger(__name__)

# Per-run locks prevent concurrent restart + auto-advance races.
# Key: run_id → Lock.  Cleaned up lazily (small memory footprint).
_run_locks: Dict[str, threading.Lock] = {}
_run_locks_guard = threading.Lock()


def _get_run_lock(run_id: str) -> threading.Lock:
    """Get or create a per-run mutex for serialising graph mutations."""
    with _run_locks_guard:
        if run_id not in _run_locks:
            _run_locks[run_id] = threading.Lock()
        return _run_locks[run_id]


# ── Default Graph Template ───────────────────────────────────────────
#
# Two parallel tracks branching from Map:
#
#   TOP:    Search → Map → Debate → Validate ←──── (feedback loop from Revise)
#                     |  /                |                    |
#                     | /                 |                    |
#   BOTTOM:        Ideas → Draft → Experiment Design → Revise → Pass (end)
#                                  (if needed/possible)
#
# Revise checks the score:
#   - score < threshold → resets Validate to PENDING (loops back)
#   - score >= threshold → Pass completes (pipeline done)
# Pass is a terminal end-stage — it completes when Revise passes.

# Each tuple: (node_type, label, default_config)
DEFAULT_PIPELINE_NODES = [
    (NodeType.SEARCH, "Literature Search", {"sources": ["arxiv", "semantic_scholar", "openalex"], "max_papers": 100}),          # 0
    (NodeType.MAP, "Topic Mapping", {"clustering": "llm_assisted", "citation_graph": True}),                                     # 1
    (NodeType.DEBATE, "Agent Debate", {"format": "adversarial", "max_rounds": 5, "agents": 6}),                                 # 2
    (NodeType.VALIDATE, "Validation & Review", {"novelty_check": True, "citation_verify": True, "specialist_domains": []}),      # 3
    (NodeType.IDEATE, "Idea Generation", {"num_ideas": 10, "num_reflections": 3}),                                               # 4
    (NodeType.DRAFT, "Paper Draft", {"paper_format": "ieee", "sections": "auto"}),                                               # 5
    (NodeType.EXPERIMENT_DESIGN, "Experiment Design", {"auto_detect_gaps": True, "required": False}),                            # 6
    (NodeType.REVISE, "Revision & Scoring", {"min_score": 6.0, "max_revisions": 3}),                                            # 7
    (NodeType.PASS, "Pass / Publish", {}),                                                                                       # 8
]

# Edges: (source_index, target_index, edge_type)
DEFAULT_PIPELINE_EDGES = [
    # Top row: Search → Map → Debate → Validate
    (0, 1, "dependency"),       # Search → Map
    (1, 2, "dependency"),       # Map → Debate
    (4, 2, "dependency"),       # Ideas → Debate (selected idea required)
    (2, 3, "dependency"),       # Debate → Validate

    # Bottom row: Map → Ideas → Draft → Experiment → Revise → Pass
    (1, 4, "dependency"),       # Map → Ideas (branch down)
    (4, 5, "dependency"),       # Ideas → Draft
    (5, 6, "conditional"),      # Draft → Experiment Design (if needed/possible)
    (6, 7, "dependency"),       # Experiment Design → Revise
    (5, 7, "conditional"),      # Draft → Revise (skip experiment if not needed)
    (7, 8, "dependency"),       # Revise → Pass (end stage)

    # Feedback loop: Revise → Validate (score too low → loop back)
    (7, 3, "feedback"),         # Revise ──feedback──→ Validate

    # Cross-track: Validate findings inform experiment design
    (3, 6, "optional"),         # Validate → Experiment Design
]


class WorkflowEngine:
    """
    Graph-based workflow engine for research pipelines.

    Responsibilities:
    - Create pipeline graphs from templates
    - Track node status and outputs
    - Handle restart from any node (with downstream invalidation)
    - Determine next executable nodes
    - Per-node model selection and advanced settings
    """

    def create_pipeline_graph(
        self,
        run_id: str,
        config: Dict[str, Any] = None,
        step_settings: Dict[str, Dict[str, Any]] = None,
    ) -> Tuple[List[WorkflowNode], List[WorkflowEdge]]:
        """
        Create the default pipeline DAG for a run.

        Args:
            run_id: Pipeline run ID
            config: Global pipeline config (merged into per-node config)
            step_settings: Per-node-type settings override {node_type_str: StepSettings.to_dict()}

        Returns:
            (nodes, edges) created
        """
        config = config or {}
        step_settings = step_settings or {}

        nodes = []
        for node_type, label, default_cfg in DEFAULT_PIPELINE_NODES:
            node_cfg = {**default_cfg}

            # Merge global config
            if node_type == NodeType.SEARCH:
                node_cfg["sources"] = config.get("sources", node_cfg["sources"])
                node_cfg["max_papers"] = config.get("max_papers", node_cfg["max_papers"])
            elif node_type == NodeType.IDEATE:
                node_cfg["num_ideas"] = config.get("num_ideas", node_cfg["num_ideas"])
                node_cfg["num_reflections"] = config.get("num_reflections", node_cfg["num_reflections"])
            elif node_type == NodeType.DRAFT:
                node_cfg["paper_format"] = config.get("paper_format", node_cfg["paper_format"])

            # Apply per-step settings
            ss = step_settings.get(node_type.value, {})
            model_config = {}
            if ss:
                settings = StepSettings.from_dict(ss) if isinstance(ss, dict) else ss
                model_config = {"model": settings.model if isinstance(settings, StepSettings) else ss.get("model", "")}
                node_cfg["step_settings"] = ss

            node = WorkflowNode(
                node_id="",
                run_id=run_id,
                node_type=node_type,
                label=label,
                config=node_cfg,
                model_config=model_config,
            )
            nodes.append(node)

        # Save nodes
        WorkflowNodeDAO.save_batch(nodes)

        # Create edges
        edges = []
        for src_idx, tgt_idx, edge_type in DEFAULT_PIPELINE_EDGES:
            edge = WorkflowEdge(
                edge_id="",
                run_id=run_id,
                source_node_id=nodes[src_idx].node_id,
                target_node_id=nodes[tgt_idx].node_id,
                edge_type=edge_type,
            )
            edges.append(edge)

        WorkflowEdgeDAO.save_batch(edges)

        logger.info("[Workflow] Created pipeline graph for run %s: %d nodes, %d edges",
                     run_id, len(nodes), len(edges))
        return nodes, edges

    def get_graph_state(self, run_id: str) -> Dict[str, Any]:
        """
        Get the full graph state for a run.
        Returns serializable dict with nodes, edges, and summary stats.
        """
        nodes = WorkflowNodeDAO.list_by_run(run_id)
        edges = WorkflowEdgeDAO.list_by_run(run_id)

        completed = sum(1 for n in nodes if n.status == NodeStatus.COMPLETED)
        running = sum(1 for n in nodes if n.status == NodeStatus.RUNNING)
        failed = sum(1 for n in nodes if n.status == NodeStatus.FAILED)

        return {
            "run_id": run_id,
            "nodes": [n.to_dict() for n in nodes],
            "edges": [e.to_dict() for e in edges],
            "summary": {
                "total_nodes": len(nodes),
                "completed": completed,
                "running": running,
                "failed": failed,
                "pending": len(nodes) - completed - running - failed,
                "progress_pct": round(100 * completed / max(len(nodes), 1), 1),
            },
        }

    def get_next_executable(self, run_id: str) -> List[WorkflowNode]:
        """
        Find nodes that are PENDING and have all required dependencies satisfied.

        Edge type behavior:
        - dependency: MUST be completed before target can run
        - optional: does NOT block target (nice-to-have input)
        - conditional: at least ONE conditional parent must be completed
        - feedback: NEVER blocks (this is a loop-back edge from Revise → Validate)

        Thread-safe: acquires per-run lock to avoid reading stale state
        during a concurrent restart or revision loop.
        """
        lock = _get_run_lock(run_id)
        with lock:
            return self._get_next_executable_locked(run_id)

    def _get_next_executable_locked(self, run_id: str) -> List[WorkflowNode]:
        nodes = WorkflowNodeDAO.list_by_run(run_id)
        edges = WorkflowEdgeDAO.list_by_run(run_id)

        node_map = {n.node_id: n for n in nodes}

        # Group incoming edges by target → [(source_id, edge_type)]
        incoming: Dict[str, List[tuple]] = {}
        for e in edges:
            incoming.setdefault(e.target_node_id, []).append((e.source_node_id, e.edge_type))

        executable = []
        for node in nodes:
            if node.status != NodeStatus.PENDING:
                continue

            parents = incoming.get(node.node_id, [])
            if not parents:
                executable.append(node)
                continue

            # Check dependencies by type
            required_ok = True
            conditional_parents = []
            has_conditional = False

            for pid, etype in parents:
                parent = node_map.get(pid)
                if not parent:
                    continue

                if etype == "feedback":
                    # Feedback edges never block — they represent loop-backs
                    continue
                elif etype == "optional":
                    # Optional edges don't block
                    continue
                elif etype == "conditional":
                    # Track conditional parents — at least one must be completed
                    has_conditional = True
                    conditional_parents.append(parent.status == NodeStatus.COMPLETED)
                else:
                    # dependency — must be completed
                    if parent.status != NodeStatus.COMPLETED:
                        required_ok = False
                        break

            # Conditional check: at least one conditional parent must be done
            if required_ok and has_conditional and not any(conditional_parents):
                required_ok = False

            if required_ok:
                executable.append(node)

        return executable

    def restart_from_node(self, run_id: str, node_id: str) -> Dict[str, Any]:
        """
        Restart pipeline from a specific node.
        1. Reset the target node to PENDING
        2. Invalidate all downstream nodes
        3. Return info about what was invalidated

        Thread-safe: acquires a per-run lock to prevent races with
        concurrent auto-advance or other restart calls.

        Returns:
            {"restarted_node": node_id, "invalidated": [node_ids], "warning": str}
        """
        lock = _get_run_lock(run_id)
        with lock:
            node = WorkflowNodeDAO.load(node_id)
            if not node:
                raise ValueError(f"Node not found: {node_id}")
            if node.run_id != run_id:
                raise ValueError(f"Node {node_id} does not belong to run {run_id}")

            # Reset target node and clear its previous execution artifacts while
            # preserving user-edited config/model settings for the rerun.
            WorkflowNodeDAO.reset_node(node_id, NodeStatus.PENDING)

            # Invalidate downstream
            invalidated = WorkflowNodeDAO.invalidate_downstream(run_id, node_id)

            # Update pipeline run status to allow re-execution
            run = PipelineRunDAO.load(run_id)
            if run and run.status in (PipelineStatus.COMPLETED, PipelineStatus.FAILED):
                PipelineRunDAO.update_status(run_id, PipelineStatus.HUMAN_REVIEW)

            logger.info("[Workflow] Restart from node %s: invalidated %d downstream nodes",
                         node_id, len(invalidated))

            return {
                "restarted_node": node_id,
                "restarted_type": node.node_type.value,
                "invalidated": invalidated,
                "invalidated_count": len(invalidated),
            }

    def update_node_model(self, node_id: str, model: str, model_config: Dict[str, Any] = None):
        """Update the model selection for a specific node."""
        from ...db import get_connection
        import json
        conn = get_connection()
        mc = json.dumps(model_config or {"model": model})
        conn.execute(
            "UPDATE workflow_nodes SET model_config = ? WHERE node_id = ?",
            (mc, node_id),
        )
        conn.commit()

    def update_node_settings(self, node_id: str, settings: Dict[str, Any]):
        """Update advanced settings for a specific node."""
        from ...db import get_connection
        import json
        conn = get_connection()
        # Merge into existing config
        row = conn.execute("SELECT config FROM workflow_nodes WHERE node_id = ?", (node_id,)).fetchone()
        if row:
            existing = json.loads(row["config"]) if row["config"] else {}
            existing["step_settings"] = settings
            conn.execute(
                "UPDATE workflow_nodes SET config = ? WHERE node_id = ?",
                (json.dumps(existing), node_id),
            )
            conn.commit()

    def mark_node_running(self, node_id: str, model_used: str = ""):
        """Mark a node as running."""
        from ...db import get_connection
        conn = get_connection()
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE workflow_nodes SET status = ?, started_at = ?, model_used = ?, error = NULL WHERE node_id = ?",
            (NodeStatus.RUNNING.value, now, model_used, node_id),
        )
        conn.commit()

    def complete_node(self, node_id: str, outputs: Dict[str, Any], score: float = None, model_used: str = ""):
        """Mark a node as completed with outputs."""
        WorkflowNodeDAO.update_outputs(node_id, outputs, score=score, model_used=model_used)

    def handle_revise_completion(self, run_id: str, node_id: str, score: float) -> Dict[str, Any]:
        """
        Handle the Revise node completion with feedback loop to Validate.

        If score >= min_score → Revise is done, Pass (end stage) completes naturally
        If score < min_score and revisions left → loop back: reset Validate + Revise to PENDING
        If score < min_score and no revisions left → fail the pipeline

        Thread-safe: acquires per-run lock to prevent races with restart.

        Returns: {"action": "pass"|"loop"|"fail", "score": float, "revision": int}
        """
        lock = _get_run_lock(run_id)
        with lock:
            return self._handle_revise_completion_locked(run_id, node_id, score)

    def _handle_revise_completion_locked(self, run_id: str, node_id: str, score: float) -> Dict[str, Any]:
        node = WorkflowNodeDAO.load(node_id)
        if not node:
            raise ValueError(f"Node not found: {node_id}")

        min_score = node.config.get("min_score", 6.0)
        max_revisions = node.config.get("max_revisions", 3)
        revision_count = node.outputs.get("revision_count", 0)

        validate_node = self.get_node_by_type(run_id, NodeType.VALIDATE)

        if score >= min_score:
            # Score high enough → Revise completes, Pass will auto-run as dependency is met
            logger.info("[Workflow] Run %s PASSED with score %.1f after %d revisions",
                        run_id, score, revision_count)
            return {"action": "pass", "score": score, "revision": revision_count}

        elif revision_count < max_revisions:
            # Score too low → feedback loop: reset Validate and Revise to PENDING
            new_revision = revision_count + 1
            WorkflowNodeDAO.update_outputs(node_id, {
                **node.outputs,
                "revision_count": new_revision,
                "last_score": score,
                "loop_reason": f"Score {score:.1f} < {min_score}, revision {new_revision}/{max_revisions}",
            }, score=score)

            # Reset Validate to PENDING (feedback loop target)
            if validate_node:
                WorkflowNodeDAO.update_status(validate_node.node_id, NodeStatus.PENDING)
            # Reset Revise itself to PENDING for next iteration
            WorkflowNodeDAO.update_status(node_id, NodeStatus.PENDING)

            logger.info("[Workflow] Run %s revision %d: score %.1f < %.1f → loop back to Validate",
                        run_id, new_revision, score, min_score)
            return {"action": "loop", "score": score, "revision": new_revision}

        else:
            # Max revisions exhausted → fail
            pass_node = self.get_node_by_type(run_id, NodeType.PASS)
            if pass_node:
                self.fail_node(pass_node.node_id,
                               f"Score {score:.1f} < {min_score} after {max_revisions} revisions")
            logger.info("[Workflow] Run %s FAILED: score %.1f after max %d revisions",
                        run_id, score, max_revisions)
            return {"action": "fail", "score": score, "revision": revision_count}

    def fail_node(self, node_id: str, error: str):
        """Mark a node as failed."""
        WorkflowNodeDAO.update_status(node_id, NodeStatus.FAILED, error=error)

    def get_node_by_type(self, run_id: str, node_type: NodeType) -> Optional[WorkflowNode]:
        """Find a node by type within a run."""
        nodes = WorkflowNodeDAO.list_by_run(run_id)
        for n in nodes:
            if n.node_type == node_type:
                return n
        return None

    def is_pipeline_complete(self, run_id: str) -> bool:
        """Check if all required nodes are completed or skipped."""
        nodes = WorkflowNodeDAO.list_by_run(run_id)
        edges = WorkflowEdgeDAO.list_by_run(run_id)

        # Find nodes that have no outgoing edges (terminal nodes)
        sources = {e.source_node_id for e in edges}
        terminal = [n for n in nodes if n.node_id not in sources]

        return all(
            n.status in (NodeStatus.COMPLETED, NodeStatus.SKIPPED)
            for n in terminal
        )

    def migrate_legacy_run(self, run_id: str) -> bool:
        """
        Migrate an old linear pipeline run to the graph engine.
        Reads ais_pipeline_runs stage_results and creates workflow nodes
        with appropriate statuses based on existing data.

        Returns True if migration succeeded.
        """
        run = PipelineRunDAO.load(run_id)
        if not run:
            return False

        # Check if already migrated
        existing_nodes = WorkflowNodeDAO.list_by_run(run_id)
        if existing_nodes:
            return True  # Already has graph

        # Create the graph
        nodes, edges = self.create_pipeline_graph(
            run_id, config=run.config,
        )

        # Map old stage results to node statuses
        sr = run.stage_results or {}
        stage_num = run.current_stage

        # Node type → index in DEFAULT_PIPELINE_NODES
        type_to_idx = {nt.value: i for i, (nt, _, _) in enumerate(DEFAULT_PIPELINE_NODES)}

        # Determine which nodes should be marked completed based on stage progress
        completed_types = set()
        if stage_num >= 2 or sr.get("stage_2"):
            completed_types.update(["search", "map", "ideate"])
        if stage_num >= 3 or sr.get("stage_3"):
            completed_types.add("debate")
        if sr.get("stage_3") and sr.get("stage_3", {}).get("simulation_id"):
            completed_types.add("validate")
        if stage_num >= 5 or sr.get("stage_5"):
            completed_types.add("draft")
        if sr.get("stage_6"):
            completed_types.update(["experiment_design", "revise"])

        for node in nodes:
            nt = node.node_type.value
            if nt in completed_types:
                # Port outputs from stage_results
                outputs = {}
                if nt == "search":
                    outputs = {"paper_count": sr.get("stage_2", {}).get("paper_count", 0)}
                elif nt == "ideate":
                    outputs = {"idea_count": sr.get("stage_2", {}).get("idea_count", 0)}
                elif nt == "debate":
                    outputs = sr.get("stage_3", {})
                elif nt == "draft":
                    outputs = sr.get("stage_5", {})
                elif nt in ("experiment_design", "revise"):
                    outputs = sr.get("stage_6", {})

                WorkflowNodeDAO.update_outputs(node.node_id, outputs)
            elif run.status == PipelineStatus.FAILED and nt not in completed_types:
                # Leave as pending
                pass

        logger.info("[Workflow] Migrated legacy run %s to graph engine (%d nodes)",
                     run_id, len(nodes))
        return True
