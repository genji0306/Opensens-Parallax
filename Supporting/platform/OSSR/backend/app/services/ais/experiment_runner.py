"""
Agent AiS — Experiment Runner
Orchestrates AI-Scientist experiment execution: writes seed ideas, invokes the
AI-Scientist pipeline (generate_ideas → perform_experiments → perform_writeup),
collects results, and persists ExperimentResult to the database.

Falls back to stub results when the AI-Scientist tooling is not installed.
"""

import json
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from opensens_common.task import TaskManager, TaskStatus

from ...db import get_connection
from ...models.ais_models import (
    ExperimentResult,
    ExperimentSpec,
    ExperimentStatus,
)

logger = logging.getLogger(__name__)


class ExperimentRunner:
    """Orchestrates AI-Scientist experiment execution."""

    AI_SCIENTIST_DIR = Path(__file__).resolve().parents[6] / "tools" / "ai-scientist"

    # Subprocess timeout per phase (seconds)
    PHASE_TIMEOUT = 600  # 10 minutes per phase

    def __init__(self):
        self.tm = TaskManager()
        self._ais_available = (self.AI_SCIENTIST_DIR / "launch_scientist.py").is_file()
        # Use AI-Scientist's own venv python if available (has torch, aider, etc.)
        ais_python = self.AI_SCIENTIST_DIR / ".venv" / "bin" / "python3"
        self._ais_python = str(ais_python) if ais_python.is_file() else "python"
        if not self._ais_available:
            logger.warning(
                "AI-Scientist not found at %s. "
                "Experiments will return stub results.",
                self.AI_SCIENTIST_DIR,
            )

    # ── Public API ────────────────────────────────────────────────────

    def run_experiment(self, spec: ExperimentSpec, task_id: str):
        """
        Execute an experiment end-to-end.

        Steps:
        1. Write seed_ideas.json to a temporary work directory.
        2. Invoke AI-Scientist phases (generate_ideas, perform_experiments, perform_writeup).
        3. Collect results (metrics, artifacts, paper path).
        4. Store ExperimentResult in DB and complete the task.

        Args:
            spec: The ExperimentSpec with template, seed ideas, and config.
            task_id: TaskManager task ID for progress tracking.
        """
        work_dir = None
        try:
            self._update_spec_status(spec.spec_id, ExperimentStatus.RUNNING)
            self.tm.update_task(
                task_id, status=TaskStatus.PROCESSING, progress=5,
                message=f"Experiment {spec.spec_id}: preparing work directory...",
            )

            # Create isolated work directory
            work_dir = Path(tempfile.mkdtemp(prefix=f"ais_exp_{spec.spec_id}_"))
            self._write_seed_ideas(spec, work_dir)

            self.tm.update_task(
                task_id, progress=10,
                message=f"Experiment {spec.spec_id}: seed ideas written. Starting execution...",
            )

            if self._ais_available:
                result = self._run_ai_scientist(spec, work_dir, task_id)
            else:
                result = self._run_stub(spec, work_dir)

            # Persist result
            self._save_result(result)
            self._update_spec_status(spec.spec_id, ExperimentStatus.COMPLETED)

            self.tm.complete_task(task_id, {
                "result_id": result.result_id,
                "spec_id": spec.spec_id,
                "status": result.status.value,
                "metrics": result.metrics,
                "artifact_count": len(result.artifacts),
                "paper_path": result.paper_path,
            })

            logger.info(
                "[ExperimentRunner] Experiment %s completed — result=%s, metrics=%s",
                spec.spec_id, result.result_id, result.metrics,
            )

        except Exception as e:
            logger.error(
                "[ExperimentRunner] Experiment %s failed: %s",
                spec.spec_id, e, exc_info=True,
            )
            self._update_spec_status(spec.spec_id, ExperimentStatus.FAILED)

            # Save a failed result record
            failed_result = ExperimentResult(
                result_id=f"ais_res_{uuid.uuid4().hex[:10]}",
                spec_id=spec.spec_id,
                run_id=spec.run_id,
                status=ExperimentStatus.FAILED,
                started_at=datetime.now().isoformat(),
                completed_at=datetime.now().isoformat(),
                error=str(e),
            )
            self._save_result(failed_result)
            self.tm.fail_task(task_id, str(e))

        finally:
            # Clean up work directory (keep on failure for debugging if env var set)
            if work_dir and work_dir.exists():
                keep = os.environ.get("AIS_KEEP_WORKDIR", "").lower() in ("1", "true")
                if not keep:
                    shutil.rmtree(work_dir, ignore_errors=True)
                else:
                    logger.info(
                        "[ExperimentRunner] Work dir preserved: %s", work_dir
                    )

    def get_result(self, spec_id: str) -> Optional[ExperimentResult]:
        """Load the most recent ExperimentResult for a given spec_id."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM experiment_results WHERE spec_id = ? ORDER BY completed_at DESC LIMIT 1",
            (spec_id,),
        ).fetchone()
        if not row:
            return None
        return self._row_to_result(row)

    def get_result_by_id(self, result_id: str) -> Optional[ExperimentResult]:
        """Load an ExperimentResult by its own ID."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM experiment_results WHERE result_id = ?", (result_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_result(row)

    def list_results(self, run_id: Optional[str] = None) -> List[ExperimentResult]:
        """List experiment results, optionally filtered by run_id."""
        conn = get_connection()
        if run_id:
            rows = conn.execute(
                "SELECT * FROM experiment_results WHERE run_id = ? ORDER BY completed_at DESC",
                (run_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM experiment_results ORDER BY completed_at DESC"
            ).fetchall()
        return [self._row_to_result(r) for r in rows]

    # ── AI-Scientist Execution ────────────────────────────────────────

    def _run_ai_scientist(
        self, spec: ExperimentSpec, work_dir: Path, task_id: str
    ) -> ExperimentResult:
        """
        Run the full AI-Scientist pipeline via subprocess.

        Invokes launch_scientist.py with the appropriate flags for the
        selected template and seed ideas file.
        """
        started_at = datetime.now().isoformat()
        seed_path = work_dir / "seed_ideas.json"
        template_dir = (
            self.AI_SCIENTIST_DIR / "templates" / spec.template
        )
        model = spec.config.get("model", "claude-sonnet-4-20250514")
        max_runs = spec.config.get("max_runs", 3)
        skip_writeup = spec.config.get("skip_writeup", False)

        cmd = [
            self._ais_python, str(self.AI_SCIENTIST_DIR / "launch_scientist.py"),
            "--experiment", str(template_dir),
            "--model", model,
            "--num-ideas", str(max_runs),
            "--skip-idea-generation",
            "--skip-novelty-check",
            "--writeup", "none" if skip_writeup else "latex",
        ]

        self.tm.update_task(
            task_id, progress=20,
            message=f"Experiment {spec.spec_id}: running AI-Scientist ({spec.template})...",
        )

        # Route AI-Scientist's OpenAI calls through our AIClient proxy (free)
        from opensens_common.config import Config
        env = {
            **os.environ,
            "PYTHONPATH": str(self.AI_SCIENTIST_DIR),
            "OPENAI_API_KEY": Config.AICLIENT_PROXY_KEY,
            "OPENAI_BASE_URL": Config.AICLIENT_PROXY_URL,
        }
        timeout = spec.config.get("timeout_minutes", 120) * 60

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )

            self.tm.update_task(
                task_id, progress=80,
                message=f"Experiment {spec.spec_id}: collecting results...",
            )

            if proc.returncode != 0:
                logger.warning(
                    "[ExperimentRunner] AI-Scientist exited with code %d: %s",
                    proc.returncode, proc.stderr[-500:] if proc.stderr else "(no stderr)",
                )

            # Collect results regardless of exit code (partial results possible)
            result = self._collect_results(work_dir, spec)
            result.started_at = started_at
            result.completed_at = datetime.now().isoformat()
            result.log_summary = self._truncate(proc.stdout, 5000)

            if proc.returncode != 0:
                result.error = self._truncate(proc.stderr or "Non-zero exit code", 2000)
                if not result.metrics:
                    result.status = ExperimentStatus.FAILED

            return result

        except subprocess.TimeoutExpired:
            logger.error(
                "[ExperimentRunner] AI-Scientist timed out after %d minutes",
                timeout // 60,
            )
            return ExperimentResult(
                result_id=f"ais_res_{uuid.uuid4().hex[:10]}",
                spec_id=spec.spec_id,
                run_id=spec.run_id,
                status=ExperimentStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now().isoformat(),
                error=f"Timed out after {timeout // 60} minutes",
            )

    def _run_stub(self, spec: ExperimentSpec, work_dir: Path) -> ExperimentResult:
        """
        Return stub results when AI-Scientist is not installed.
        Useful for development and testing without the full toolchain.
        """
        logger.info(
            "[ExperimentRunner] Running stub experiment for spec %s "
            "(AI-Scientist not available)",
            spec.spec_id,
        )
        now = datetime.now().isoformat()
        return ExperimentResult(
            result_id=f"ais_res_{uuid.uuid4().hex[:10]}",
            spec_id=spec.spec_id,
            run_id=spec.run_id,
            metrics={
                "stub": True,
                "note": "AI-Scientist tooling not installed — returning placeholder results",
                "template": spec.template,
                "seed_idea_count": len(spec.seed_ideas),
            },
            artifacts=[],
            log_summary="Stub execution — no actual experiment was run.",
            paper_path=None,
            status=ExperimentStatus.COMPLETED,
            started_at=now,
            completed_at=now,
        )

    # ── File I/O ──────────────────────────────────────────────────────

    def _write_seed_ideas(self, spec: ExperimentSpec, work_dir: Path):
        """Write seed ideas to work dir AND template's ideas.json (AI-Scientist expects it there)."""
        seed_path = work_dir / "seed_ideas.json"
        seed_path.write_text(json.dumps(spec.seed_ideas, indent=2), encoding="utf-8")

        # Also write to template directory as ideas.json (AI-Scientist loads from there
        # when --skip-idea-generation is used)
        template_dir = self.AI_SCIENTIST_DIR / "templates" / spec.template
        if template_dir.is_dir():
            ideas_path = template_dir / "ideas.json"
            ideas_path.write_text(json.dumps(spec.seed_ideas, indent=2), encoding="utf-8")
            logger.info(
                "[ExperimentRunner] Wrote %d seed ideas to %s + %s",
                len(spec.seed_ideas), seed_path, ideas_path,
            )
        else:
            logger.info(
                "[ExperimentRunner] Wrote %d seed ideas to %s",
                len(spec.seed_ideas), seed_path,
            )

    def _collect_results(self, work_dir: Path, spec: ExperimentSpec) -> ExperimentResult:
        """
        Parse AI-Scientist output directory for results.

        Expected structure under work_dir:
        - results/ or <template>/       — experiment outputs
        - *.pdf                          — generated paper
        - final_results.json or logs/    — metrics
        """
        metrics: Dict[str, Any] = {}
        artifacts: List[str] = []
        paper_path: Optional[str] = None

        # Scan for result JSON files
        for json_file in work_dir.rglob("*.json"):
            if json_file.name in ("seed_ideas.json",):
                continue
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    # Merge metrics from any result file
                    metrics[json_file.stem] = data
                artifacts.append(str(json_file.relative_to(work_dir)))
            except (json.JSONDecodeError, OSError):
                pass

        # Scan for PDF papers
        for pdf_file in work_dir.rglob("*.pdf"):
            paper_path = str(pdf_file)
            artifacts.append(str(pdf_file.relative_to(work_dir)))

        # Scan for plot images
        for img_ext in ("*.png", "*.svg", "*.jpg"):
            for img_file in work_dir.rglob(img_ext):
                artifacts.append(str(img_file.relative_to(work_dir)))

        status = ExperimentStatus.COMPLETED if metrics else ExperimentStatus.FAILED

        return ExperimentResult(
            result_id=f"ais_res_{uuid.uuid4().hex[:10]}",
            spec_id=spec.spec_id,
            run_id=spec.run_id,
            metrics=metrics,
            artifacts=artifacts,
            paper_path=paper_path,
            status=status,
        )

    # ── Persistence ───────────────────────────────────────────────────

    def _save_result(self, result: ExperimentResult):
        """Insert or replace an ExperimentResult in the database."""
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO experiment_results
               (result_id, spec_id, run_id, metrics, artifacts, log_summary,
                paper_path, status, started_at, completed_at, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                result.result_id,
                result.spec_id,
                result.run_id,
                json.dumps(result.metrics),
                json.dumps(result.artifacts),
                result.log_summary,
                result.paper_path,
                result.status.value if isinstance(result.status, ExperimentStatus) else result.status,
                result.started_at,
                result.completed_at,
                result.error,
            ),
        )
        conn.commit()

    def _update_spec_status(self, spec_id: str, status: ExperimentStatus):
        """Update the status of an experiment spec."""
        conn = get_connection()
        conn.execute(
            "UPDATE experiment_specs SET status = ? WHERE spec_id = ?",
            (status.value, spec_id),
        )
        conn.commit()

    def _row_to_result(self, row) -> ExperimentResult:
        """Convert a sqlite3.Row to an ExperimentResult dataclass (V1+V2 safe)."""
        keys = row.keys() if hasattr(row, "keys") else []
        return ExperimentResult(
            result_id=row["result_id"],
            spec_id=row["spec_id"],
            run_id=row["run_id"],
            metrics=json.loads(row["metrics"]) if row["metrics"] else {},
            artifacts=json.loads(row["artifacts"]) if row["artifacts"] else [],
            log_summary=row["log_summary"] or "",
            paper_path=row["paper_path"],
            status=ExperimentStatus(row["status"]),
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error=row["error"],
            tree_structure=json.loads(row["tree_structure"]) if "tree_structure" in keys and row["tree_structure"] else {},
            token_usage=json.loads(row["token_usage"]) if "token_usage" in keys and row["token_usage"] else {},
            self_review=row["self_review"] if "self_review" in keys else "",
        )

    # ── Utilities ─────────────────────────────────────────────────────

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        """Truncate text to max_len, adding ellipsis if trimmed."""
        if not text:
            return ""
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."
