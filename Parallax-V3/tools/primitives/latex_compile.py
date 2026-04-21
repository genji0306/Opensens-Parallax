"""LaTeX package probing and compilation helpers."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...contracts import Phase, RiskLevel, TypedTool
from ...errors import ParallaxV3Error


class LatexCompilerError(ParallaxV3Error):
    """Raised when TeX probing or compilation fails unexpectedly."""


def _probe_package(name: str) -> bool:
    try:
        completed = subprocess.run(["kpsewhich", f"{name}.sty"], capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return False
    return completed.returncode == 0 and bool((completed.stdout or "").strip())


@dataclass
class LatexCompiler(TypedTool):
    def __init__(self):
        TypedTool.__init__(
            self,
            name="latex_compile",
            input_schema=dict,
            output_schema=dict,
            risk_level=RiskLevel.SAFE_AUTO,
            phase_unlock=Phase.ACT,
        )

    def probe(self, workspace_path: Path) -> dict[str, Any]:
        workspace = Path(workspace_path)
        profile = {
            "has_cleveref": _probe_package("cleveref"),
            "has_microtype": _probe_package("microtype"),
            "has_biblatex": _probe_package("biblatex"),
            "has_hyperref": _probe_package("hyperref"),
        }
        profile["cite_cmd"] = "\\cref" if profile["has_cleveref"] else "\\ref"
        (workspace / "tex_profile.json").write_text(json.dumps(profile, indent=2, sort_keys=True), encoding="utf-8")
        return profile

    def compile(self, tex_path: Path) -> dict[str, Any]:
        tex_path = Path(tex_path)
        try:
            completed = subprocess.run(
                ["latexmk", "-pdf", "-interaction=nonstopmode", tex_path.name],
                cwd=tex_path.parent,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            return {"success": False, "log": f"latexmk not found: {exc}", "pdf_path": None}

        pdf_path = tex_path.with_suffix(".pdf")
        success = completed.returncode == 0 and pdf_path.exists()
        log = (completed.stdout or "") + ("\n" if completed.stdout and completed.stderr else "") + (completed.stderr or "")
        return {
            "success": success,
            "log": log,
            "pdf_path": pdf_path if success else None,
        }


