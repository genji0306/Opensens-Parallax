"""Figure rendering for matplotlib and simple diagram code."""

from __future__ import annotations

import ast
import builtins
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg", force=True)
import matplotlib.pyplot as plt
import numpy as np

from ...contracts import Phase, RiskLevel, TypedTool
from ...errors import ParallaxV3Error


class FigureRenderError(ParallaxV3Error):
    """Raised when a figure specification cannot be rendered."""


_ASPECT_RATIOS = {
    "1:1": (1, 1),
    "4:3": (4, 3),
    "16:9": (16, 9),
    "3:2": (3, 2),
    "2:1": (2, 1),
    "1:2": (1, 2),
    "3:4": (3, 4),
    "9:16": (9, 16),
    "2:3": (2, 3),
    "1:3": (1, 3),
    "3:1": (3, 1),
    "golden": (1.61803398875, 1),
}


def _safe_import(name: str, globals=None, locals=None, fromlist=(), level=0):
    root = name.split(".", 1)[0]
    if root not in {"numpy", "matplotlib"}:
        raise ImportError(f"Import not allowed: {name}")
    return builtins.__import__(name, globals, locals, fromlist, level)


def _validate_code(code: str) -> None:
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".", 1)[0] not in {"numpy", "matplotlib"}:
                    raise FigureRenderError(f"Disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                raise FigureRenderError("Relative imports are not allowed")
            if node.module.split(".", 1)[0] not in {"numpy", "matplotlib"}:
                raise FigureRenderError(f"Disallowed import: {node.module}")


class FigureRenderer(TypedTool):
    def __init__(self, workspace_path: Path | None = None):
        TypedTool.__init__(
            self,
            name="figure_render",
            input_schema=dict,
            output_schema=Path,
            risk_level=RiskLevel.SAFE_AUTO,
            phase_unlock=Phase.PLAN,
        )
        root = Path(workspace_path or Path.cwd())
        root = root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        object.__setattr__(self, "workspace_path", root)

    def render(self, spec: dict[str, Any]) -> Path:
        render_type = spec.get("type")
        code = spec.get("code", "")
        output_path = self.workspace_path / spec.get("output_path", "figure.png")
        aspect_ratio = spec.get("aspect_ratio", "4:3")
        if aspect_ratio not in _ASPECT_RATIOS:
            raise FigureRenderError(f"Unsupported aspect ratio: {aspect_ratio}")
        if render_type not in {"matplotlib", "diagram"}:
            raise FigureRenderError(f"Unsupported figure type: {render_type}")
        _validate_code(code)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ratio_w, ratio_h = _ASPECT_RATIOS[aspect_ratio]
        base_width = 8.0
        width = base_width
        height = base_width * (ratio_h / ratio_w)
        fig = plt.figure(figsize=(width, height), dpi=300)
        namespace = {
            "__builtins__": {"__import__": _safe_import, "range": range, "len": len, "min": min, "max": max, "sum": sum, "abs": abs},
            "np": np,
            "plt": plt,
            "fig": fig,
        }
        try:
            exec(code, namespace, namespace)
            fig.savefig(output_path, dpi=300)
        finally:
            plt.close(fig)
        return output_path
