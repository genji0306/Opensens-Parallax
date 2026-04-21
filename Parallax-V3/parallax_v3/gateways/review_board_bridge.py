"""Bridge to the V2 review board manager."""

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
    from app.services.review.board_manager import BoardManager
except Exception:  # pragma: no cover - fallback when V2 backend is unavailable
    BoardManager = None  # type: ignore[assignment]


class ReviewBoardBridge:
    def __init__(self, manager: Any | None = None):
        if manager is not None:
            self.manager = manager
        elif BoardManager is not None:
            self.manager = BoardManager()
        else:
            self.manager = None

    def get_reviewer_archetypes(self) -> dict[str, Any]:
        if self.manager is None:
            return {}
        return self.manager.get_available_archetypes()

    def run_review_round(self, *args: Any, **kwargs: Any) -> Any:
        if self.manager is None:
            return {"status": "unavailable"}
        return self.manager.run_review_round(*args, **kwargs)

    def run_5phase_review_round(self, *args: Any, **kwargs: Any) -> Any:
        if self.manager is None:
            return {"status": "unavailable"}
        return self.manager.run_5phase_review_round(*args, **kwargs)

