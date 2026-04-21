"""
parallax_v3/runtime/conductor.py
=================================
Stateful Orchestrator — the single god-object per run.

Manages:
  - Session lifecycle (create, get, phase transitions)
  - Pipeline dispatch (run, audit, memory stats)
  - Phase transitions (EXPLORE → PLAN → ACT)
  - Revision loop (halt-rule state machine)
  - SSE event streaming
"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from ..contracts import Phase, RefinementState, SessionManifest
from ..memory.stores.cold import ColdStore


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ROOT = REPO_ROOT / "workspace"


@dataclass
class SessionRecord:
    session_id: str
    status: str
    manifest: dict[str, Any]
    created_at: datetime
    current_phase: Phase = Phase.EXPLORE


@dataclass
class RunRecord:
    run_id: str
    session_id: str
    status: str
    pipeline: str
    started_at: datetime
    current_phase: Phase = Phase.EXPLORE
    refinement_state: RefinementState | None = None
    audit: list[dict[str, Any]] = field(default_factory=list)
    memory: dict[str, int] = field(
        default_factory=lambda: {
            "hot_keys": 0,
            "warm_entries": 0,
            "cold_files": 0,
            "token_estimate": 0,
        }
    )
    events: list[dict[str, Any]] = field(default_factory=list)


class Conductor:
    """
    The per-process orchestrator. One instance shared across API routes.

    In production, this would back onto a durable store. For Sprint 7
    it uses in-memory dicts which are sufficient for single-process runs.
    """

    def __init__(self) -> None:
        self.sessions: dict[str, SessionRecord] = {}
        self.runs: dict[str, RunRecord] = {}

    # ------------------------------------------------------------------
    # Session lifecycle
    # ------------------------------------------------------------------

    async def create_session(self, request: Any) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        manifest = SessionManifest(
            session_id=session_id,
            research_question=request.research_question,
            target_venue=request.target_venue,
            citation_style=request.citation_style,
            max_refinement_iters=request.max_refinement_iters,
            budget_usd=request.budget_usd,
        )
        record = SessionRecord(
            session_id=session_id,
            status="active",
            manifest=asdict(manifest),
            created_at=datetime.now(timezone.utc),
        )
        self.sessions[session_id] = record
        return {
            "session_id": session_id,
            "status": record.status,
            "manifest": record.manifest,
            "created_at": record.created_at,
        }

    async def get_session(self, session_id: str) -> dict[str, Any]:
        record = self.sessions.get(session_id)
        if not record:
            raise KeyError(f"Session not found: {session_id}")
        return {
            "session_id": record.session_id,
            "status": record.status,
            "manifest": record.manifest,
            "created_at": record.created_at,
        }

    # ------------------------------------------------------------------
    # Phase transitions
    # ------------------------------------------------------------------

    def transition_phase(self, run_id: str, target: Phase) -> Phase:
        """
        Advance the run to a new phase. Returns the new phase.
        Phase order: EXPLORE → PLAN → ACT. Cannot go backwards.
        """
        record = self.runs.get(run_id)
        if not record:
            raise KeyError(f"Run not found: {run_id}")
        previous_phase = record.current_phase
        if target.value <= record.current_phase.value:
            return record.current_phase
        next_value = min(target.value, record.current_phase.value + 1)
        record.current_phase = Phase(next_value)
        record.events.append({
            "type": "phase_transition",
            "from": previous_phase.value,
            "to": record.current_phase.value,
            "session_id": record.session_id,
        })
        return record.current_phase

    # ------------------------------------------------------------------
    # Pipeline execution
    # ------------------------------------------------------------------

    async def run_pipeline(self, request: Any) -> dict[str, Any]:
        if request.session_id not in self.sessions:
            raise KeyError(f"Session not found: {request.session_id}")
        run_id = str(uuid.uuid4())
        record = RunRecord(
            run_id=run_id,
            session_id=request.session_id,
            status="queued",
            pipeline=request.pipeline,
            started_at=datetime.now(timezone.utc),
        )
        self.runs[run_id] = record
        response_status = record.status
        await self._execute_pipeline(record, request)
        return {
            "run_id": run_id,
            "session_id": request.session_id,
            "status": response_status,
            "started_at": record.started_at,
        }

    # ------------------------------------------------------------------
    # Refinement loop
    # ------------------------------------------------------------------

    def init_refinement(self, run_id: str) -> RefinementState:
        """Initialise refinement state for a revision loop."""
        record = self.runs.get(run_id)
        if not record:
            raise KeyError(f"Run not found: {run_id}")
        state = RefinementState(
            iteration=0,
            scores=[5.0] * 6,
            prev_scores=[5.0] * 6,
            plateau_count=0,
            verdict="halt_empty",
        )
        record.refinement_state = state
        return state

    def advance_refinement(
        self,
        run_id: str,
        new_scores: list[float],
    ) -> RefinementState:
        """Update refinement state with new scores and evaluate halt rule."""
        from ..llm.rubrics.halt_rules import evaluate_halt

        record = self.runs.get(run_id)
        if not record or not record.refinement_state:
            raise KeyError(f"No refinement state for run: {run_id}")

        state = record.refinement_state
        state.prev_scores = list(state.scores)
        state.scores = list(new_scores)
        state.iteration += 1

        overall_new = sum(
            w * s for w, s in zip(
                [0.20, 0.20, 0.15, 0.15, 0.20, 0.10], new_scores
            )
        )
        overall_prev = sum(
            w * s for w, s in zip(
                [0.20, 0.20, 0.15, 0.15, 0.20, 0.10], state.prev_scores
            )
        )
        net_delta = sum(n - p for n, p in zip(new_scores, state.prev_scores))

        manifest = self.sessions.get(record.session_id)
        iter_cap = None
        if manifest:
            iter_cap = manifest.manifest.get("max_refinement_iters")

        evaluate_halt(
            state,
            overall_new=overall_new,
            overall_prev=overall_prev,
            net_subaxis_delta=net_delta,
            iter_cap=iter_cap,
        )
        record.refinement_state = state
        return state

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    async def get_run_audit(self, run_id: str) -> list[dict[str, Any]]:
        record = self.runs.get(run_id)
        if not record:
            raise KeyError(f"Run not found: {run_id}")
        return list(record.audit)

    async def get_memory_stats(self, run_id: str) -> dict[str, Any]:
        record = self.runs.get(run_id)
        if not record:
            raise KeyError(f"Run not found: {run_id}")
        return dict(record.memory)

    async def stream_events(self, run_id: str) -> AsyncIterator[dict[str, Any]]:
        """Yield pending events then heartbeat. Matches V2 SSE contract."""
        record = self.runs.get(run_id)
        if not record:
            raise KeyError(f"Run not found: {run_id}")
        for event in record.events:
            yield event
            await asyncio.sleep(0)
        yield {"type": "heartbeat", "status": "awaiting_selection"}

    async def _execute_pipeline(self, record: RunRecord, request: Any) -> None:
        workspace = WORKSPACE_ROOT / record.session_id
        store = ColdStore(WORKSPACE_ROOT, record.session_id)
        started_at = datetime.now(timezone.utc)

        try:
            idea_text = self._read_pipeline_input(getattr(request, "idea_path", None), "idea.md")
            log_text = self._read_pipeline_input(
                getattr(request, "log_path", None),
                "experimental_log.md",
            )
            store.write("inputs/idea.md", idea_text)
            store.write("inputs/experimental_log.md", log_text)

            relative_workspace = str(workspace.relative_to(REPO_ROOT)).replace("\\", "/")
            record.events.append(
                {
                    "type": "progress",
                    "status": "running",
                    "stage": 1,
                    "progress": 50,
                    "message": "Workspace inputs materialized",
                }
            )
            record.events.append(
                {
                    "type": "complete",
                    "status": "completed",
                    "stage": 2,
                    "stage_results": {
                        "pipeline": record.pipeline,
                        "workspace": relative_workspace,
                        "inputs": {
                            "idea": "inputs/idea.md",
                            "experimental_log": "inputs/experimental_log.md",
                        },
                    },
                }
            )
            record.audit.extend(
                [
                    {
                        "timestamp": started_at,
                        "hook_point": "session_start",
                        "tool_name": None,
                        "risk_level": None,
                        "cost_usd": 0.0,
                        "detail": {"workspace": relative_workspace},
                    },
                    {
                        "timestamp": datetime.now(timezone.utc),
                        "hook_point": "stage_end",
                        "tool_name": None,
                        "risk_level": None,
                        "cost_usd": 0.0,
                        "detail": {"pipeline": record.pipeline, "status": "completed"},
                    },
                ]
            )
            record.memory.update(
                {
                    "cold_files": len(store.list_files("")),
                    "token_estimate": len(idea_text.split()) + len(log_text.split()),
                }
            )
            record.status = "completed"
        except Exception as exc:
            record.status = "failed"
            record.events.append({"type": "error", "status": "failed", "error": str(exc)})
            record.audit.append(
                {
                    "timestamp": datetime.now(timezone.utc),
                    "hook_point": "session_stop",
                    "tool_name": None,
                    "risk_level": None,
                    "cost_usd": 0.0,
                    "detail": {"pipeline": record.pipeline, "status": "failed", "error": str(exc)},
                }
            )
            raise

    def _read_pipeline_input(self, raw_path: str | None, default_name: str) -> str:
        if not raw_path:
            return f"Placeholder {default_name} content for smoke-safe runs.\n"
        path = Path(raw_path)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path.read_text(encoding="utf-8")
