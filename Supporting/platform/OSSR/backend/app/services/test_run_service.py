"""
Test Run Service — discovers and normalizes CLI test results from the filesystem.

Scans backend/data/test_runs/ for:
  - Timestamped debate folders (20260321_1454_test_run_984ac055b0/)
  - Tool test JSON files (ais_superconductor.json, sc_superconductor.json, auto_superconductor.json)

Returns unified HistoricalRun dicts that can be merged with DB-backed pipeline runs.
"""

import json
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Directory where CLI test results are stored
TEST_RUNS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "test_runs"

# Folder pattern: 20260321_1454_test_run_984ac055b0
_FOLDER_RE = re.compile(r"^(\d{8}_\d{4})_(.+)$")

# Cache TTL in seconds
_CACHE_TTL = 60
_cache: dict = {"ts": 0, "runs": []}


def _parse_folder_timestamp(ts_str: str) -> str:
    """Convert folder timestamp '20260321_1454' to ISO 8601."""
    try:
        dt = datetime.strptime(ts_str, "%Y%m%d_%H%M")
        return dt.isoformat()
    except ValueError:
        return datetime.now().isoformat()


def _classify_tool_json(data: dict) -> str:
    """Determine run type from a tool test JSON's test_suite field."""
    suite = data.get("test_suite", "")
    mapping = {
        "ai-scientist": "ais",
        "scienceclaw": "scienceclaw",
        "autoresearch-mlx": "autoresearch",
    }
    return mapping.get(suite, "unknown")


def _summarize_tool_steps(data: dict) -> dict:
    """Extract summary stats from a tool test JSON (steps array)."""
    steps = data.get("steps", [])
    summary = data.get("summary", {})
    return {
        "steps_total": len(steps),
        "steps_passed": summary.get("pass", 0),
        "steps_failed": summary.get("fail", 0),
        "steps_warned": summary.get("warn", 0),
        "steps_skipped": summary.get("skip", 0),
        "total_elapsed_s": data.get("total_elapsed_s"),
    }


def _summarize_debate(data: dict) -> dict:
    """Extract summary stats from a full debate results JSON."""
    debate = data.get("debate", {})
    return {
        "agent_count": debate.get("agent_count", 0),
        "rounds": debate.get("rounds", 0),
        "total_turns": debate.get("total_turns", 0),
    }


def _read_json_safe(path: Path) -> Optional[dict]:
    """Read and parse a JSON file, returning None on failure."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read %s: %s", path, e)
        return None


def _scan_debate_folders() -> list[dict]:
    """Scan timestamped debate folders in test_runs/."""
    runs = []
    if not TEST_RUNS_DIR.is_dir():
        return runs

    for entry in TEST_RUNS_DIR.iterdir():
        if not entry.is_dir():
            continue
        m = _FOLDER_RE.match(entry.name)
        if not m:
            continue

        ts_str, run_id = m.group(1), m.group(2)
        created_at = _parse_folder_timestamp(ts_str)

        # Look for the results JSON
        result_json = entry / f"results_{run_id}.json"
        html_artifact = entry / f"research_test_{run_id}.html"
        draft_md = entry / f"paper_draft_{run_id}.md"

        # Check if already imported to DB
        imported = (entry / ".imported").exists()

        data = _read_json_safe(result_json) if result_json.exists() else None
        query = ""
        summary = {}
        status = "completed"

        if data:
            query = data.get("query", data.get("debate", {}).get("query", ""))
            summary = _summarize_debate(data)
        else:
            status = "parse_error"

        runs.append({
            "run_id": run_id,
            "source": "platform" if imported else "cli",
            "type": "debate",
            "query": query,
            "created_at": created_at,
            "status": status,
            "summary": summary,
            "artifacts": {
                "html": str(html_artifact.relative_to(TEST_RUNS_DIR)) if html_artifact.exists() else None,
                "draft_md": str(draft_md.relative_to(TEST_RUNS_DIR)) if draft_md.exists() else None,
                "result_json": str(result_json.relative_to(TEST_RUNS_DIR)) if result_json.exists() else None,
            },
            "folder": entry.name,
        })

    return runs


def _scan_tool_jsons() -> list[dict]:
    """Scan standalone tool test JSON files (not in timestamped folders)."""
    runs = []
    if not TEST_RUNS_DIR.is_dir():
        return runs

    for entry in TEST_RUNS_DIR.iterdir():
        if not entry.is_file() or not entry.suffix == ".json":
            continue
        # Skip results files that belong to debate folders
        if entry.name.startswith("results_"):
            continue

        data = _read_json_safe(entry)
        if not data:
            continue

        run_type = _classify_tool_json(data)
        if run_type == "unknown":
            continue

        # Use filename (without .json) as run_id
        run_id = entry.stem
        timestamp = data.get("timestamp", "")
        if not timestamp:
            # Fall back to file mtime
            mtime = entry.stat().st_mtime
            timestamp = datetime.fromtimestamp(mtime).isoformat()

        runs.append({
            "run_id": run_id,
            "source": "cli",
            "type": run_type,
            "query": data.get("query", run_id),
            "created_at": timestamp,
            "status": "completed",
            "summary": _summarize_tool_steps(data),
            "artifacts": {
                "html": None,
                "draft_md": None,
                "result_json": entry.name,
            },
            "folder": None,
        })

    return runs


def list_cli_runs(force_refresh: bool = False) -> list[dict]:
    """
    Return all CLI test runs from the filesystem.
    Results are cached for _CACHE_TTL seconds.
    """
    global _cache
    now = time.time()
    if not force_refresh and (now - _cache["ts"]) < _CACHE_TTL and _cache["runs"]:
        return _cache["runs"]

    runs = _scan_debate_folders() + _scan_tool_jsons()
    # Sort newest first
    runs.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    _cache = {"ts": now, "runs": runs}
    return runs


def get_cli_run(run_id: str) -> Optional[dict]:
    """Get a single CLI run by run_id. Returns full data including transcript."""
    runs = list_cli_runs()
    meta = next((r for r in runs if r["run_id"] == run_id), None)
    if not meta:
        return None

    result = dict(meta)

    # Load full JSON data
    json_path = meta["artifacts"].get("result_json")
    if json_path:
        full_path = TEST_RUNS_DIR / (meta["folder"] or "") / json_path if meta["folder"] else TEST_RUNS_DIR / json_path
        # For tool JSONs without a folder, the path is just the filename
        if not full_path.exists() and meta["folder"]:
            full_path = TEST_RUNS_DIR / json_path
        data = _read_json_safe(full_path)
        if data:
            result["data"] = data

    return result


def get_artifact_path(run_id: str, artifact_type: str = "html") -> Optional[Path]:
    """Get the absolute filesystem path for a run's artifact."""
    runs = list_cli_runs()
    meta = next((r for r in runs if r["run_id"] == run_id), None)
    if not meta or not meta.get("folder"):
        return None

    key = artifact_type if artifact_type in ("html", "draft_md") else "html"
    rel = meta["artifacts"].get(key)
    if not rel:
        return None

    full_path = TEST_RUNS_DIR / meta["folder"] / rel
    return full_path if full_path.exists() else None


def mark_as_imported(run_id: str) -> bool:
    """Create a .imported sentinel file in the run's folder."""
    runs = list_cli_runs()
    meta = next((r for r in runs if r["run_id"] == run_id), None)
    if not meta or not meta.get("folder"):
        return False

    sentinel = TEST_RUNS_DIR / meta["folder"] / ".imported"
    try:
        sentinel.touch()
        # Invalidate cache
        _cache["ts"] = 0
        return True
    except OSError:
        return False
