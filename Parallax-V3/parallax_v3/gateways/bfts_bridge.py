"""Bridge to the V2 BFTS experiment runner."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def _ensure_v2_backend_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[2].parent
    backend_path = repo_root / "Parallax-V2" / "backend"
    if backend_path.exists() and str(backend_path) not in sys.path:
        sys.path.insert(0, str(backend_path))


_ensure_v2_backend_on_path()

try:  # pragma: no cover - optional external dependency
    from app.services.ais.experiment_runner_v2 import ExperimentRunnerV2
except Exception:  # pragma: no cover - fallback when V2 backend is unavailable
    ExperimentRunnerV2 = None  # type: ignore[assignment]


class BFTSBridge:
    def __init__(self, runner: Any | None = None):
        if runner is not None:
            self.runner = runner
        elif ExperimentRunnerV2 is not None:
            self.runner = ExperimentRunnerV2()
        else:
            self.runner = None

    def run_experiment(self, spec: Any, task_id: str) -> Any:
        if self.runner is None:
            return {"status": "unavailable"}
        return self.runner.run_experiment(spec, task_id)

