"""Sandboxed Python statistics runner."""

from __future__ import annotations

import ast
import subprocess
import sys
from typing import Any

from ...contracts import Phase, RiskLevel, TypedTool
from ...errors import ParallaxV3Error


class StatRunnerError(ParallaxV3Error):
    """Raised when the script violates allowlist rules or execution fails."""


def _allowed_root(module: str, allowed: set[str]) -> bool:
    return module.split(".", 1)[0] in allowed


def _validate_imports(script: str, allowed_imports: list[str]) -> None:
    allowed = set(allowed_imports)
    tree = ast.parse(script)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _allowed_root(alias.name, allowed):
                    raise StatRunnerError(f"Disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module is None:
                raise StatRunnerError("Relative imports are not allowed")
            if node.module == "__future__":
                continue
            if not _allowed_root(node.module, allowed):
                raise StatRunnerError(f"Disallowed import: {node.module}")


class StatRunner(TypedTool):
    def __init__(self):
        TypedTool.__init__(
            self,
            name="stat_runner",
            input_schema=dict,
            output_schema=dict,
            risk_level=RiskLevel.SAFE_AUTO,
            phase_unlock=Phase.ACT,
        )
        object.__setattr__(self, "allowed_imports", [
            "numpy",
            "pandas",
            "scipy",
            "sklearn",
            "matplotlib",
            "json",
            "math",
            "statistics",
        ])

    def run(self, script: str, allowed_imports: list[str] | None = None) -> dict[str, Any]:
        imports = allowed_imports or self.allowed_imports
        _validate_imports(script, imports)
        try:
            completed = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("StatRunner script timed out after 30 seconds") from exc
        return {
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
        }
