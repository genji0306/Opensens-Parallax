"""CLI integration tests."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
TOPIC = "Hydrolysis of Tetra-butyl Titanate (TBT) in Water-Friendly Solvent System as Binder for Zinc Flake Coating Process"


def _run_cli(*args: str, workspace_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args, "--workspace-root", str(workspace_root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_package_cli_explore_runs_topic(tmp_path):
    completed = _run_cli("-m", "parallax_v3", "explore", "--topic", TOPIC, workspace_root=tmp_path / "workspace")

    assert completed.returncode == 0, completed.stderr
    assert "RuntimeWarning" not in completed.stderr

    payload = json.loads(completed.stdout)
    assert payload["pipeline"] == "full_research"
    assert payload["topic"] == TOPIC

    results_path = Path(payload["results_path"])
    assert results_path.exists()
    results = json.loads(results_path.read_text(encoding="utf-8"))
    assert results["agent_count"] == 9
    assert results["topic"] == TOPIC


def test_pipeline_module_cli_runs_without_runpy_warning(tmp_path):
    completed = _run_cli(
        "-m",
        "parallax_v3.pipelines.full_research",
        "--topic",
        TOPIC,
        workspace_root=tmp_path / "workspace",
    )

    assert completed.returncode == 0, completed.stderr
    assert "RuntimeWarning" not in completed.stderr

    payload = json.loads(completed.stdout)
    assert payload["pipeline"] == "full_research"
    assert Path(payload["results_path"]).exists()
