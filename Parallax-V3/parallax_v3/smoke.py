"""Basic no-op smoke test for the package."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from .contracts import Phase, SessionManifest
from .manifest.schema import SessionManifestValidator
from .memory.stores.cold import ColdStore
from .memory.stores.hot import HotStore
from .observability.audit import AuditLog
from .runtime.phase_guard import PhaseGuard
from .tools.registry import ToolRegistry
from .tools.risk_classifier import RiskClassifier


def main() -> int:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        manifest = SessionManifest(
            session_id="smoke-session",
            research_question="Smoke test",
            target_venue="neurips",
            citation_style="ieee",
        )
        manifest_path = root / "manifest.json"
        manifest_path.write_text(json.dumps(
            {
                "session_id": manifest.session_id,
                "research_question": manifest.research_question,
                "target_venue": manifest.target_venue,
                "citation_style": manifest.citation_style,
            },
            indent=2,
            sort_keys=True,
        ), encoding="utf-8")
        SessionManifestValidator.validate(manifest_path)
        store = ColdStore(root, "workspace")
        store.write("note.txt", "hello")
        HotStore().set("x", 1)
        AuditLog(manifest.session_id, root).close()
        PhaseGuard(Phase.EXPLORE)
        ToolRegistry()
        RiskClassifier().classify("pytest")
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
