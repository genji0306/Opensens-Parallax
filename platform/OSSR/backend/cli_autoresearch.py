#!/usr/bin/env python3
"""
Autoresearch Daemon — Continuous background research loop.

Polls OSSR for approved ideas, claims DAMD cluster GPU slots,
runs 5-min fixed-budget experiments via autoresearch-mlx protocol,
and pushes results back to OSSR.

Usage:
    python cli_autoresearch.py                # Run daemon (default: local node)
    python cli_autoresearch.py --node gpu0    # Target a specific DAMD node
    python cli_autoresearch.py --once         # Run one experiment then exit
    python cli_autoresearch.py --dry-run      # Plan experiments without executing
"""

import argparse
import json
import logging
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent))
from app.db import get_connection, init_db
from app.models.ais_models import AutoresearchStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [autoresearch] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("autoresearch")

AUTORESEARCH_DIR = Path(__file__).resolve().parents[1] / ".." / "tools" / "autoresearch-mlx"
POLL_INTERVAL = 30  # seconds between queue checks
EXPERIMENT_TIMEOUT = 900  # 15 min max per experiment (5 min train + overhead)
MAX_ITERATIONS_DEFAULT = 50

_shutdown = False


def _signal_handler(signum, frame):
    global _shutdown
    logger.info("Shutdown signal received — finishing current experiment...")
    _shutdown = True


def _claim_next_run():
    """Find the next queued autoresearch run and claim it."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM autoresearch_runs WHERE status = 'queued' ORDER BY created_at ASC LIMIT 1"
    ).fetchone()
    if not row:
        return None

    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE autoresearch_runs SET status = 'running', updated_at = ? WHERE auto_run_id = ?",
        (now, row["auto_run_id"]),
    )
    conn.commit()
    return dict(row)


def _update_run(auto_run_id: str, **kwargs):
    """Update an autoresearch run record."""
    conn = get_connection()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    vals = list(kwargs.values()) + [auto_run_id]
    conn.execute(
        f"UPDATE autoresearch_runs SET {sets}, updated_at = ? WHERE auto_run_id = ?",
        [*kwargs.values(), datetime.now().isoformat(), auto_run_id],
    )
    conn.commit()


def _load_idea(idea_id: str):
    """Load idea from DB."""
    conn = get_connection()
    row = conn.execute("SELECT data FROM research_ideas WHERE idea_id = ?", (idea_id,)).fetchone()
    if row:
        return json.loads(row["data"])
    return None


def _check_gpu_available(node: str) -> bool:
    """
    Check if GPU resources are available on the target DAMD node.
    For local node, check if no other autoresearch is running.
    For remote nodes, query the DAMD resource manager (future).
    """
    if node == "local":
        conn = get_connection()
        active = conn.execute(
            "SELECT COUNT(*) as c FROM autoresearch_runs WHERE status = 'running' AND node = 'local'"
        ).fetchone()
        return active["c"] <= 1  # Allow the current run (which we just claimed)
    # Future: DAMD cluster API
    logger.warning("Remote node GPU check not yet implemented for node: %s", node)
    return True


def _run_single_experiment(auto_run: dict, work_dir: Path, dry_run: bool = False) -> dict:
    """
    Run one 5-min autoresearch-mlx experiment.
    Returns: {"val_bpb": float, "status": "keep"|"discard"|"crash"}
    """
    if dry_run:
        logger.info("[DRY RUN] Would run: uv run train.py in %s", work_dir)
        return {"val_bpb": 0.0, "status": "dry_run", "peak_vram_mb": 0}

    try:
        result = subprocess.run(
            ["uv", "run", "train.py"],
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=EXPERIMENT_TIMEOUT,
        )

        # Parse val_bpb from output
        metrics = {}
        for line in result.stdout.splitlines():
            if line.startswith("val_bpb:"):
                metrics["val_bpb"] = float(line.split(":")[1].strip())
            elif line.startswith("peak_vram_mb:"):
                metrics["peak_vram_mb"] = float(line.split(":")[1].strip())
            elif line.startswith("total_seconds:"):
                metrics["total_seconds"] = float(line.split(":")[1].strip())

        if "val_bpb" not in metrics:
            # Check stderr for crash
            logger.error("Experiment produced no val_bpb. stderr: %s", result.stderr[-500:])
            return {"val_bpb": 0.0, "status": "crash", "error": result.stderr[-200:]}

        return {**metrics, "status": "keep"}

    except subprocess.TimeoutExpired:
        logger.warning("Experiment timed out after %ds", EXPERIMENT_TIMEOUT)
        return {"val_bpb": 0.0, "status": "crash", "error": "timeout"}
    except FileNotFoundError:
        logger.error("uv not found — install with: curl -LsSf https://astral.sh/uv/install.sh | sh")
        return {"val_bpb": 0.0, "status": "crash", "error": "uv not found"}


def _run_autoresearch_loop(auto_run: dict, node: str, dry_run: bool = False):
    """Run the full autoresearch loop for one idea."""
    auto_run_id = auto_run["auto_run_id"]
    idea_id = auto_run["idea_id"]
    config = json.loads(auto_run["config"]) if auto_run["config"] else {}
    max_iterations = config.get("max_iterations", MAX_ITERATIONS_DEFAULT)

    idea = _load_idea(idea_id)
    idea_title = idea.get("title", idea_id) if idea else idea_id

    logger.info("Starting autoresearch for idea: %s (%d max iterations)", idea_title, max_iterations)

    # Check autoresearch-mlx is available
    if not AUTORESEARCH_DIR.exists():
        logger.error("autoresearch-mlx not found at %s", AUTORESEARCH_DIR)
        _update_run(auto_run_id, status="failed", error="autoresearch-mlx directory not found")
        return

    work_dir = AUTORESEARCH_DIR
    best_metric = None
    results_lines = []

    for iteration in range(1, max_iterations + 1):
        if _shutdown:
            logger.info("Shutdown requested — stopping after iteration %d", iteration - 1)
            _update_run(auto_run_id, status="stopped", iterations=iteration - 1)
            return

        # Check GPU availability
        if not _check_gpu_available(node):
            logger.info("No GPU available — waiting...")
            _update_run(auto_run_id, status="waiting_gpu")
            time.sleep(60)
            _update_run(auto_run_id, status="running")
            continue

        logger.info("Iteration %d/%d", iteration, max_iterations)
        result = _run_single_experiment(auto_run, work_dir, dry_run=dry_run)

        val_bpb = result.get("val_bpb", 0.0)
        status = result.get("status", "crash")

        # Track best
        if status == "keep" and (best_metric is None or val_bpb < best_metric):
            best_metric = val_bpb

        results_lines.append(f"{iteration}\t{val_bpb:.6f}\t{status}\t{datetime.now().isoformat()}")

        _update_run(
            auto_run_id,
            iterations=iteration,
            best_metric=best_metric,
            results_tsv="\n".join(results_lines),
        )

        if dry_run:
            break

    # Mark completed
    _update_run(
        auto_run_id,
        status="completed",
        iterations=max_iterations,
        best_metric=best_metric,
        results_tsv="\n".join(results_lines),
    )
    logger.info(
        "Autoresearch complete. %d iterations, best %s: %s",
        max_iterations, auto_run.get("metric_name", "val_bpb"), best_metric,
    )


def main():
    parser = argparse.ArgumentParser(description="Autoresearch daemon")
    parser.add_argument("--node", default="local", help="DAMD node target (default: local)")
    parser.add_argument("--once", action="store_true", help="Run one experiment then exit")
    parser.add_argument("--dry-run", action="store_true", help="Plan without executing")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    init_db()
    logger.info("Autoresearch daemon started (node: %s)", args.node)

    while not _shutdown:
        run = _claim_next_run()
        if run:
            logger.info("Claimed run: %s (idea: %s)", run["auto_run_id"], run["idea_id"])
            _run_autoresearch_loop(run, node=args.node, dry_run=args.dry_run)
            if args.once:
                break
        else:
            if args.once:
                logger.info("No queued runs. Exiting (--once mode).")
                break
            logger.debug("No queued runs. Sleeping %ds...", POLL_INTERVAL)
            time.sleep(POLL_INTERVAL)

    logger.info("Autoresearch daemon stopped.")


if __name__ == "__main__":
    main()
