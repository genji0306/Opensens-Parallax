"""
AI Scientist V2 — Experiment Runner (BFTS)
Orchestrates AI-Scientist V2 tree-search experiment execution.

Falls back to stub results when V2 tooling is not installed.
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
from typing import Any, Dict, Optional

from opensens_common.task import TaskManager, TaskStatus

from ...db import get_connection
from ...models.ais_models import (
    ExperimentResult,
    ExperimentSpec,
    ExperimentStatus,
)
from .bfts_config import BFTSConfig, resolve_bfts_config
from .v2_result_parser import parse_v2_results

logger = logging.getLogger(__name__)


class ExperimentRunnerV2:
    """Orchestrates AI-Scientist V2 (BFTS) experiment execution."""

    AI_SCIENTIST_V2_DIR = Path(__file__).resolve().parents[6] / "tools" / "ai-scientist-v2"

    def __init__(self):
        self.tm = TaskManager()
        self._v2_available = (self.AI_SCIENTIST_V2_DIR / "launch_scientist_bfts.py").is_file()
        ais_python = self.AI_SCIENTIST_V2_DIR / ".venv" / "bin" / "python3"
        self._ais_python = str(ais_python) if ais_python.is_file() else "python"
        if not self._v2_available:
            logger.warning(
                "AI-Scientist V2 not found at %s. "
                "V2 experiments will return stub results.",
                self.AI_SCIENTIST_V2_DIR,
            )

    # ── Public API ────────────────────────────────────────────────────

    # Agent-Laboratory-style repair loop — up to 3 attempts with progressively
    # simpler BFTS configs when a run fails for a recoverable reason
    # (config parse error, resource exhaustion, timeout). Fatal errors are
    # surfaced immediately.
    MAX_REPAIR_ATTEMPTS = 3
    _RECOVERABLE_HINTS = (
        "timeout", "timed out", "out of memory", "cuda", "resource",
        "config", "yaml", "parse", "invalid", "max_children",
    )

    def _is_recoverable(self, error: str) -> bool:
        if not error:
            return False
        lowered = error.lower()
        return any(hint in lowered for hint in self._RECOVERABLE_HINTS)

    def _simplify_config(self, bfts_config: "BFTSConfig") -> None:
        """Shrink a BFTS config in place for a repair retry."""
        try:
            if getattr(bfts_config, "max_steps", 0) and bfts_config.max_steps > 4:
                bfts_config.max_steps = max(4, bfts_config.max_steps // 2)
            if getattr(bfts_config, "num_children", 0) and bfts_config.num_children > 1:
                bfts_config.num_children = max(1, bfts_config.num_children - 1)
            if getattr(bfts_config, "max_depth", 0) and bfts_config.max_depth > 2:
                bfts_config.max_depth = max(2, bfts_config.max_depth - 1)
        except Exception:  # defensive — config shape may vary
            pass

    def run_experiment(self, spec: ExperimentSpec, task_id: str):
        """
        Execute a V2 (BFTS) experiment end-to-end with an Agent-Laboratory-style
        repair loop. Up to ``MAX_REPAIR_ATTEMPTS`` attempts; each retry
        simplifies the BFTS config (fewer steps / children / depth) based on
        the error message from the previous attempt.
        """
        work_dir = None
        attempt = 0
        last_error: Optional[str] = None
        try:
            self._update_spec_status(spec.spec_id, ExperimentStatus.RUNNING)
            self.tm.update_task(
                task_id, status=TaskStatus.PROCESSING, progress=5,
                message=f"V2 Experiment {spec.spec_id}: preparing BFTS run...",
            )

            # Resolve BFTS config
            bfts_raw = spec.config.get("bfts_config", {})
            profile = spec.config.get("bfts_profile", "standard")
            bfts_config = resolve_bfts_config(profile, bfts_raw if isinstance(bfts_raw, dict) else {})

            # Apply per-field overrides from spec config
            if spec.config.get("include_writeup") is not None:
                bfts_config.include_writeup = bool(spec.config["include_writeup"])

            # Create isolated work directory
            work_dir = Path(tempfile.mkdtemp(prefix=f"ais_v2_{spec.spec_id}_"))
            self._write_v2_ideas(spec, work_dir)
            config_path = bfts_config.write_yaml(work_dir)

            self.tm.update_task(
                task_id, progress=10,
                message=f"V2 Experiment {spec.spec_id}: BFTS config written. Starting tree search...",
            )

            # ── Repair loop ──────────────────────────────────────────
            result = None
            for attempt in range(1, self.MAX_REPAIR_ATTEMPTS + 1):
                try:
                    if self._v2_available:
                        result = self._run_bfts(
                            spec, work_dir, config_path, bfts_config, task_id
                        )
                    else:
                        result = self._run_v2_stub(spec, work_dir, bfts_config)
                except Exception as attempt_err:  # noqa: BLE001
                    last_error = f"{type(attempt_err).__name__}: {attempt_err}"
                    logger.warning(
                        "[ExperimentRunnerV2] attempt %d/%d failed: %s",
                        attempt, self.MAX_REPAIR_ATTEMPTS, last_error,
                    )
                    if attempt < self.MAX_REPAIR_ATTEMPTS and self._is_recoverable(last_error):
                        self._simplify_config(bfts_config)
                        try:
                            config_path = bfts_config.write_yaml(work_dir)
                        except Exception:
                            pass
                        self.tm.update_task(
                            task_id, progress=10,
                            message=f"V2 Experiment {spec.spec_id}: retrying with simplified config (attempt {attempt + 1})...",
                        )
                        continue
                    raise

                # If the runner returned a failed result object (rather than
                # raising) treat it as a soft failure and retry once.
                if (
                    result
                    and getattr(result, "status", None) == ExperimentStatus.FAILED
                    and attempt < self.MAX_REPAIR_ATTEMPTS
                    and self._is_recoverable(getattr(result, "error", "") or "")
                ):
                    last_error = result.error
                    logger.info(
                        "[ExperimentRunnerV2] soft-failure on attempt %d — simplifying config",
                        attempt,
                    )
                    self._simplify_config(bfts_config)
                    try:
                        config_path = bfts_config.write_yaml(work_dir)
                    except Exception:
                        pass
                    continue
                break

            if result is None:
                raise RuntimeError(last_error or "experiment produced no result")

            # Persist
            if attempt > 1 and hasattr(result, "metrics"):
                result.metrics = dict(result.metrics or {})
                result.metrics["repair_attempts"] = attempt
            self._save_result(result)
            self._update_spec_status(spec.spec_id, ExperimentStatus.COMPLETED)

            self.tm.complete_task(task_id, {
                "result_id": result.result_id,
                "spec_id": spec.spec_id,
                "status": result.status.value,
                "metrics": result.metrics,
                "artifact_count": len(result.artifacts),
                "paper_path": result.paper_path,
                "version": "v2",
            })

            logger.info(
                "[ExperimentRunnerV2] Experiment %s completed — result=%s",
                spec.spec_id, result.result_id,
            )

        except Exception as e:
            logger.error(
                "[ExperimentRunnerV2] Experiment %s failed: %s",
                spec.spec_id, e, exc_info=True,
            )
            self._update_spec_status(spec.spec_id, ExperimentStatus.FAILED)

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
            if work_dir and work_dir.exists():
                keep = os.environ.get("AIS_KEEP_WORKDIR", "").lower() in ("1", "true")
                if not keep:
                    shutil.rmtree(work_dir, ignore_errors=True)

    # ── BFTS Execution ────────────────────────────────────────────────

    def _run_bfts(
        self,
        spec: ExperimentSpec,
        work_dir: Path,
        config_path: Path,
        bfts_config: BFTSConfig,
        task_id: str,
    ) -> ExperimentResult:
        """Run the V2 BFTS pipeline via subprocess."""
        started_at = datetime.now().isoformat()
        ideas_path = work_dir / "ideas.json"

        cmd = [
            self._ais_python,
            str(self.AI_SCIENTIST_V2_DIR / "launch_scientist_bfts.py"),
            "--config", str(config_path),
            "--load_ideas", str(ideas_path),
            "--num-workers", str(bfts_config.num_workers),
            "--steps", str(bfts_config.steps),
        ]

        if not bfts_config.include_writeup:
            cmd.append("--skip-writeup")

        self.tm.update_task(
            task_id, progress=20,
            message=f"V2 Experiment {spec.spec_id}: BFTS running ({bfts_config.num_workers} workers, {bfts_config.steps} steps)...",
        )

        from opensens_common.config import Config
        env = {
            **os.environ,
            "PYTHONPATH": str(self.AI_SCIENTIST_V2_DIR),
            "OPENAI_API_KEY": Config.AICLIENT_PROXY_KEY,
            "OPENAI_BASE_URL": Config.AICLIENT_PROXY_URL,
        }

        timeout = bfts_config.total_timeout

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
                message=f"V2 Experiment {spec.spec_id}: parsing tree results...",
            )

            if proc.returncode != 0:
                logger.warning(
                    "[ExperimentRunnerV2] V2 BFTS exited with code %d: %s",
                    proc.returncode, proc.stderr[-500:] if proc.stderr else "",
                )

            # Parse V2 results
            parsed = parse_v2_results(work_dir)

            result = ExperimentResult(
                result_id=f"ais_res_{uuid.uuid4().hex[:10]}",
                spec_id=spec.spec_id,
                run_id=spec.run_id,
                metrics=parsed["metrics"],
                artifacts=parsed["artifacts"],
                log_summary=self._truncate(proc.stdout, 5000),
                paper_path=parsed["paper_path"],
                status=ExperimentStatus.COMPLETED if parsed["metrics"] else ExperimentStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now().isoformat(),
                tree_structure=parsed["tree_structure"],
                token_usage=parsed["token_usage"],
                self_review=parsed["self_review"],
            )

            if proc.returncode != 0:
                result.error = self._truncate(proc.stderr or "Non-zero exit code", 2000)
                if not result.metrics:
                    result.status = ExperimentStatus.FAILED

            return result

        except subprocess.TimeoutExpired:
            logger.error(
                "[ExperimentRunnerV2] BFTS timed out after %d seconds", timeout
            )
            return ExperimentResult(
                result_id=f"ais_res_{uuid.uuid4().hex[:10]}",
                spec_id=spec.spec_id,
                run_id=spec.run_id,
                status=ExperimentStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.now().isoformat(),
                error=f"BFTS timed out after {timeout} seconds",
            )

    def _run_v2_stub(
        self, spec: ExperimentSpec, work_dir: Path, bfts_config: BFTSConfig
    ) -> ExperimentResult:
        """Return stub V2 results when AI-Scientist V2 is not installed."""
        logger.info(
            "[ExperimentRunnerV2] Running V2 stub for spec %s", spec.spec_id
        )
        now = datetime.now().isoformat()

        stub_tree = {
            "nodes": [
                {"node_id": "root", "parent_id": None, "depth": 0, "status": "success",
                 "metrics": {"loss": 0.45, "accuracy": 0.78}, "is_best": False},
                {"node_id": "node_1", "parent_id": "root", "depth": 1, "status": "success",
                 "metrics": {"loss": 0.32, "accuracy": 0.85}, "is_best": True},
                {"node_id": "node_2", "parent_id": "root", "depth": 1, "status": "failed",
                 "metrics": {}, "is_best": False},
                {"node_id": "node_3", "parent_id": "node_1", "depth": 2, "status": "success",
                 "metrics": {"loss": 0.28, "accuracy": 0.87}, "is_best": False},
            ],
            "max_depth": 2,
            "total_explored": 4,
            "successful": 3,
            "failed": 1,
            "best_node_id": "node_1",
            "best_metrics": {"loss": 0.32, "accuracy": 0.85},
        }

        stub_tokens = {
            "total_input_tokens": 125000,
            "total_output_tokens": 45000,
            "total_cost_usd": 8.50,
            "by_model": {
                "claude-sonnet": {"input_tokens": 80000, "output_tokens": 30000, "cost_usd": 5.50},
                "gpt-4o": {"input_tokens": 45000, "output_tokens": 15000, "cost_usd": 3.00},
            },
        }

        return ExperimentResult(
            result_id=f"ais_res_{uuid.uuid4().hex[:10]}",
            spec_id=spec.spec_id,
            run_id=spec.run_id,
            metrics={
                "stub": True,
                "version": "v2",
                "note": "AI-Scientist V2 not installed — returning placeholder BFTS results",
                "profile": bfts_config.to_dict(),
                "best_loss": 0.32,
                "best_accuracy": 0.85,
            },
            artifacts=[],
            log_summary="V2 stub execution — no actual BFTS experiment was run.",
            paper_path=None,
            status=ExperimentStatus.COMPLETED,
            started_at=now,
            completed_at=now,
            tree_structure=stub_tree,
            token_usage=stub_tokens,
            self_review="Stub review: This is a placeholder. No actual experiment was conducted.",
        )

    # ── File I/O ──────────────────────────────────────────────────────

    def _write_v2_ideas(self, spec: ExperimentSpec, work_dir: Path):
        """Write V2-format ideas to work directory."""
        ideas_path = work_dir / "ideas.json"
        ideas_path.write_text(json.dumps(spec.seed_ideas, indent=2), encoding="utf-8")
        logger.info(
            "[ExperimentRunnerV2] Wrote %d ideas to %s",
            len(spec.seed_ideas), ideas_path,
        )

    # ── Persistence ───────────────────────────────────────────────────

    def _save_result(self, result: ExperimentResult):
        """Insert or replace an ExperimentResult (V2 extended) in the database."""
        conn = get_connection()
        conn.execute(
            """INSERT OR REPLACE INTO experiment_results
               (result_id, spec_id, run_id, metrics, artifacts, log_summary,
                paper_path, status, started_at, completed_at, error,
                tree_structure, token_usage, self_review)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                json.dumps(getattr(result, "tree_structure", {})),
                json.dumps(getattr(result, "token_usage", {})),
                getattr(result, "self_review", ""),
            ),
        )
        conn.commit()

    def _update_spec_status(self, spec_id: str, status: ExperimentStatus):
        conn = get_connection()
        conn.execute(
            "UPDATE experiment_specs SET status = ? WHERE spec_id = ?",
            (status.value, spec_id),
        )
        conn.commit()

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if not text:
            return ""
        return text[:max_len - 3] + "..." if len(text) > max_len else text
