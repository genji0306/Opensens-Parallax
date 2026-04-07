"""
V3 Workflow Engine — DAG-based phase orchestration.

Extends V2's graph engine with:
- More phase types (experiment, compute, simulation, governance)
- More edge types (approval, branch, merge)
- Protocol templates that define default DAGs per domain
- Delegation to V2 SDK for research phases
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.workflow import WorkflowRun, Phase, PhaseEdge

logger = logging.getLogger(__name__)

# Templates whose phases are delegated to the V2 research backend
RESEARCH_TEMPLATES = {"academic_research", "full_research_experiment"}

# ── Protocol Templates ───────────────────────────────────────────

TEMPLATES: dict[str, dict[str, Any]] = {
    "academic_research": {
        "label": "Academic Research",
        "domain": "academic",
        "description": "Full research pipeline: literature → debate → ideas → draft → revision",
        "phases": [
            ("search", "Literature Search", {"sources": ["arxiv", "semantic_scholar", "openalex"], "max_papers": 100}),
            ("map", "Topic Mapping", {"clustering": "llm_assisted"}),
            ("debate", "Agent Debate", {"format": "adversarial", "max_rounds": 5}),
            ("validate", "Validation & Review", {"novelty_check": True, "specialist_domains": []}),
            ("ideate", "Idea Generation", {"num_ideas": 10, "num_reflections": 3}),
            ("draft", "Paper Draft", {"paper_format": "ieee", "sections": "auto"}),
            ("experiment_plan", "Experiment Design", {"auto_detect_gaps": True, "required": False}),
            ("revise", "Revision & Scoring", {"min_score": 6.0, "max_revisions": 3}),
            ("pass", "Pass / Publish", {}),
        ],
        "edges": [
            (0, 1, "dependency"),    # Search → Map
            (1, 2, "dependency"),    # Map → Debate
            (4, 2, "dependency"),    # Ideas → Debate
            (2, 3, "dependency"),    # Debate → Validate
            (1, 4, "dependency"),    # Map → Ideas
            (4, 5, "dependency"),    # Ideas → Draft
            (5, 6, "conditional"),   # Draft → Experiment (optional)
            (6, 7, "dependency"),    # Experiment → Revise
            (5, 7, "conditional"),   # Draft → Revise (skip experiment)
            (7, 8, "dependency"),    # Revise → Pass
            (7, 3, "feedback"),      # Revise → Validate (feedback loop)
            (3, 6, "optional"),      # Validate → Experiment (informational)
        ],
    },
    "experiment": {
        "label": "Experiment Workflow",
        "domain": "experiment",
        "description": "Plan, validate, execute, and analyze an experiment",
        "phases": [
            ("experiment_plan", "Experiment Plan", {"auto_detect_gaps": True}),
            ("safety_check", "Safety Check", {"required": True}),
            ("approval_gate", "Approval Gate", {"risk_threshold": "medium"}),
            ("experiment_execute", "Experiment Execute", {"sandbox": True, "timeout_s": 300}),
            ("experiment_analyze", "Analyze Results", {}),
            ("report", "Generate Report", {}),
            ("pass", "Complete", {}),
        ],
        "edges": [
            (0, 1, "dependency"),    # Plan → Safety
            (1, 2, "dependency"),    # Safety → Approval
            (2, 3, "approval"),      # Approval → Execute
            (3, 4, "dependency"),    # Execute → Analyze
            (4, 5, "dependency"),    # Analyze → Report
            (5, 6, "dependency"),    # Report → Complete
            (4, 0, "feedback"),      # Analyze → Plan (loop if QC fails)
        ],
    },
    "simulation": {
        "label": "Simulation Workflow",
        "domain": "simulation",
        "description": "Design, estimate, dispatch, and analyze a simulation",
        "phases": [
            ("simulate_design", "Design Simulation", {}),
            ("compute_estimate", "Estimate Cost", {}),
            ("approval_gate", "Approval Gate", {"cost_threshold_usd": 10.0}),
            ("compute_dispatch", "Dispatch Job", {"target": "auto"}),
            ("compute_monitor", "Monitor Progress", {}),
            ("compute_collect", "Collect Results", {}),
            ("simulate_analyze", "Analyze Results", {}),
            ("report", "Generate Report", {}),
            ("pass", "Complete", {}),
        ],
        "edges": [
            (0, 1, "dependency"),
            (1, 2, "dependency"),
            (2, 3, "approval"),
            (3, 4, "dependency"),
            (4, 5, "dependency"),
            (5, 6, "dependency"),
            (6, 7, "dependency"),
            (7, 8, "dependency"),
            (5, 0, "feedback"),      # Collect → Design (retry on failure)
        ],
    },
    "full_research_experiment": {
        "label": "Research → Experiment",
        "domain": "hybrid",
        "description": "Full pipeline from literature research through experiment execution",
        "phases": [
            ("search", "Literature Search", {"sources": ["arxiv", "semantic_scholar", "openalex"]}),
            ("map", "Topic Mapping", {}),
            ("debate", "Agent Debate", {"max_rounds": 5}),
            ("validate", "Validation", {}),
            ("ideate", "Idea Generation", {"num_ideas": 10}),
            ("draft", "Paper Draft", {}),
            ("experiment_plan", "Experiment Plan", {}),
            ("safety_check", "Safety Check", {}),
            ("approval_gate", "Experiment Approval", {}),
            ("experiment_execute", "Experiment Execute", {"sandbox": True}),
            ("experiment_analyze", "Analyze Results", {}),
            ("synthesize", "Synthesize", {}),
            ("revise", "Revision", {"min_score": 6.0}),
            ("pass", "Complete", {}),
        ],
        "edges": [
            (0, 1, "dependency"),    # Search → Map
            (1, 2, "dependency"),    # Map → Debate
            (4, 2, "dependency"),    # Ideas → Debate
            (2, 3, "dependency"),    # Debate → Validate
            (1, 4, "dependency"),    # Map → Ideas
            (4, 5, "dependency"),    # Ideas → Draft
            (5, 6, "dependency"),    # Draft → Experiment Plan
            (6, 7, "dependency"),    # Plan → Safety
            (7, 8, "dependency"),    # Safety → Approval
            (8, 9, "approval"),      # Approval → Execute
            (9, 10, "dependency"),   # Execute → Analyze
            (10, 11, "dependency"),  # Analyze → Synthesize
            (3, 11, "optional"),     # Validate → Synthesize (informational)
            (11, 12, "dependency"),  # Synthesize → Revise
            (12, 13, "dependency"),  # Revise → Pass
            (12, 3, "feedback"),     # Revise → Validate (feedback loop)
        ],
    },
}


# ── Engine ───────────────────────────────────────────────────────


class V3WorkflowEngine:
    """
    Async workflow engine for V3.
    Creates phase DAGs from templates, resolves dependencies, and manages phase lifecycle.
    """

    async def create_from_template(
        self,
        session: AsyncSession,
        run_id: str,
        template_id: str,
        config_overrides: dict | None = None,
    ) -> tuple[list[Phase], list[PhaseEdge]]:
        """Create a phase DAG from a protocol template."""
        template = TEMPLATES.get(template_id)
        if not template:
            raise ValueError(f"Unknown template: {template_id}. Available: {list(TEMPLATES.keys())}")

        config_overrides = config_overrides or {}

        phases: list[Phase] = []
        for i, (phase_type, label, default_cfg) in enumerate(template["phases"]):
            cfg = {**default_cfg, **config_overrides.get(phase_type, {})}
            phase = Phase(
                run_id=run_id,
                phase_type=phase_type,
                label=label,
                config=cfg,
                sort_order=i,
            )
            session.add(phase)
            phases.append(phase)

        await session.flush()  # Assign phase_ids

        edges: list[PhaseEdge] = []
        for src_idx, tgt_idx, edge_type in template["edges"]:
            edge = PhaseEdge(
                run_id=run_id,
                source_phase_id=phases[src_idx].phase_id,
                target_phase_id=phases[tgt_idx].phase_id,
                edge_type=edge_type,
            )
            session.add(edge)
            edges.append(edge)

        await session.flush()

        logger.info("Created %d phases + %d edges for run %s (template=%s)",
                     len(phases), len(edges), run_id, template_id)
        return phases, edges

    async def get_graph_state(self, session: AsyncSession, run_id: str) -> dict:
        """Get full graph state for a workflow run."""
        phases_result = await session.execute(
            select(Phase).where(Phase.run_id == run_id).order_by(Phase.sort_order)
        )
        phases = list(phases_result.scalars().all())

        edges_result = await session.execute(
            select(PhaseEdge).where(PhaseEdge.run_id == run_id)
        )
        edges = list(edges_result.scalars().all())

        completed = sum(1 for p in phases if p.status == "completed")
        running = sum(1 for p in phases if p.status == "running")
        failed = sum(1 for p in phases if p.status == "failed")

        return {
            "run_id": run_id,
            "phases": [p.to_dict() for p in phases],
            "edges": [e.to_dict() for e in edges],
            "summary": {
                "total_phases": len(phases),
                "completed": completed,
                "running": running,
                "failed": failed,
                "pending": len(phases) - completed - running - failed,
                "progress_pct": round(100 * completed / max(len(phases), 1), 1),
            },
        }

    async def get_next_executable(self, session: AsyncSession, run_id: str) -> list[Phase]:
        """
        Find phases that are PENDING and have all required dependencies satisfied.

        Edge type behavior (same as V2 + new types):
        - dependency: MUST be completed
        - optional: does NOT block
        - conditional: at least ONE conditional parent must be completed
        - feedback: NEVER blocks
        - approval: MUST be completed (approval was granted)
        - branch/merge: treated as dependency
        """
        phases_result = await session.execute(
            select(Phase).where(Phase.run_id == run_id)
        )
        phases = list(phases_result.scalars().all())

        edges_result = await session.execute(
            select(PhaseEdge).where(PhaseEdge.run_id == run_id)
        )
        edges = list(edges_result.scalars().all())

        phase_map = {p.phase_id: p for p in phases}

        # Group incoming edges by target
        incoming: dict[str, list[tuple[str, str]]] = {}
        for e in edges:
            incoming.setdefault(e.target_phase_id, []).append(
                (e.source_phase_id, e.edge_type)
            )

        executable = []
        for phase in phases:
            if phase.status not in ("pending", "invalidated"):
                continue

            parents = incoming.get(phase.phase_id, [])
            if not parents:
                executable.append(phase)
                continue

            required_ok = True
            conditional_parents = []
            has_conditional = False

            for pid, etype in parents:
                parent = phase_map.get(pid)
                if not parent:
                    continue

                if etype in ("feedback", "optional"):
                    continue
                elif etype == "conditional":
                    has_conditional = True
                    conditional_parents.append(parent.status == "completed")
                else:
                    # dependency, approval, branch, merge — must be completed
                    if parent.status != "completed":
                        required_ok = False
                        break

            if required_ok and has_conditional and not any(conditional_parents):
                required_ok = False

            if required_ok:
                executable.append(phase)

        return executable

    async def mark_phase_running(self, session: AsyncSession, phase_id: str) -> None:
        """Mark a phase as running."""
        await session.execute(
            update(Phase)
            .where(Phase.phase_id == phase_id)
            .values(status="running", started_at=datetime.now(timezone.utc))
        )

    async def complete_phase(
        self,
        session: AsyncSession,
        phase_id: str,
        outputs: dict,
        score: float | None = None,
        model_used: str = "",
        cost_usd: float = 0.0,
    ) -> None:
        """Mark a phase as completed with outputs."""
        values: dict[str, Any] = {
            "status": "completed",
            "outputs": outputs,
            "model_used": model_used,
            "cost_usd": cost_usd,
            "completed_at": datetime.now(timezone.utc),
        }
        if score is not None:
            values["score"] = score
        await session.execute(
            update(Phase).where(Phase.phase_id == phase_id).values(**values)
        )

    async def fail_phase(self, session: AsyncSession, phase_id: str, error: str) -> None:
        """Mark a phase as failed."""
        await session.execute(
            update(Phase)
            .where(Phase.phase_id == phase_id)
            .values(
                status="failed",
                error=error,
                completed_at=datetime.now(timezone.utc),
            )
        )

    async def restart_from_phase(
        self, session: AsyncSession, run_id: str, phase_id: str
    ) -> dict:
        """Restart from a phase — reset it and invalidate all downstream."""
        # Reset the target phase
        await session.execute(
            update(Phase)
            .where(Phase.phase_id == phase_id)
            .values(
                status="pending",
                outputs={},
                score=None,
                error=None,
                cost_usd=0.0,
                model_used="",
                started_at=None,
                completed_at=None,
            )
        )

        # BFS to find and invalidate downstream phases
        edges_result = await session.execute(
            select(PhaseEdge).where(PhaseEdge.run_id == run_id)
        )
        edges = list(edges_result.scalars().all())

        # Build adjacency: source → [targets]
        adj: dict[str, list[str]] = {}
        for e in edges:
            if e.edge_type != "feedback":  # Don't follow feedback edges
                adj.setdefault(e.source_phase_id, []).append(e.target_phase_id)

        # BFS from phase_id
        visited = set()
        queue = list(adj.get(phase_id, []))
        while queue:
            pid = queue.pop(0)
            if pid in visited:
                continue
            visited.add(pid)
            queue.extend(adj.get(pid, []))

        # Invalidate all downstream
        for pid in visited:
            await session.execute(
                update(Phase)
                .where(Phase.phase_id == pid)
                .values(
                    status="invalidated",
                    outputs={},
                    score=None,
                    error=None,
                    model_used="",
                    started_at=None,
                    completed_at=None,
                )
            )

        return {
            "restarted_phase": phase_id,
            "invalidated": list(visited),
            "invalidated_count": len(visited),
        }

    def list_templates(self) -> list[dict]:
        """List available protocol templates."""
        return [
            {
                "template_id": tid,
                "label": t["label"],
                "domain": t["domain"],
                "description": t["description"],
                "phase_count": len(t["phases"]),
                "edge_count": len(t["edges"]),
            }
            for tid, t in TEMPLATES.items()
        ]
