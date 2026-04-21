"""Typed IO tools for the cold store."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ...contracts import Phase, RiskLevel, TypedTool
from ...memory.stores.cold import ColdStore


def _store_from_value(value: ColdStore | Path) -> ColdStore:
    return value if isinstance(value, ColdStore) else ColdStore(Path(value))


class ReadTool(TypedTool):
    def __init__(self, store: ColdStore | Path):
        super().__init__(
            name="read",
            input_schema=dict,
            output_schema=str,
            risk_level=RiskLevel.SAFE_AUTO,
            phase_unlock=Phase.EXPLORE,
        )
        object.__setattr__(self, "store", _store_from_value(store))

    def run(self, path: str) -> str:
        return self.store.read(path)


class EditTool(TypedTool):
    def __init__(self, store: ColdStore | Path):
        super().__init__(
            name="edit",
            input_schema=dict,
            output_schema=bool,
            risk_level=RiskLevel.SAFE_AUTO,
            phase_unlock=Phase.ACT,
        )
        object.__setattr__(self, "store", _store_from_value(store))

    def run(self, path: str, old: str, new: str) -> bool:
        content = self.store.read(path)
        if old not in content:
            raise ValueError(f"Text not found in {path}")
        self.store.write(path, content.replace(old, new, 1))
        return True


class GrepTool(TypedTool):
    def __init__(self, store: ColdStore | Path):
        super().__init__(
            name="grep",
            input_schema=dict,
            output_schema=list,
            risk_level=RiskLevel.SAFE_AUTO,
            phase_unlock=Phase.EXPLORE,
        )
        object.__setattr__(self, "store", _store_from_value(store))

    def run(self, pattern: str, path: str) -> list[dict[str, Any]]:
        target = self.store._resolve(path)
        if target.is_dir():
            raise ValueError(f"Grep target must be a file: {path}")
        regex = re.compile(pattern)
        matches: list[dict[str, Any]] = []
        for line_no, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
            if regex.search(line):
                matches.append({"line": line_no, "content": line})
        return matches


class GlobTool(TypedTool):
    def __init__(self, store: ColdStore | Path):
        super().__init__(
            name="glob",
            input_schema=dict,
            output_schema=list,
            risk_level=RiskLevel.SAFE_AUTO,
            phase_unlock=Phase.EXPLORE,
        )
        object.__setattr__(self, "store", _store_from_value(store))

    def run(self, pattern: str, root: str) -> list[str]:
        base = self.store._resolve(root) if root else self.store.root
        if base.is_file():
            base = base.parent
        matches = []
        for path in base.glob(pattern):
            if path.is_file():
                matches.append(str(path.relative_to(self.store.root)).replace("\\", "/"))
        return sorted(matches)


class WriteTool(TypedTool):
    def __init__(self, store: ColdStore | Path):
        super().__init__(
            name="write",
            input_schema=dict,
            output_schema=bool,
            risk_level=RiskLevel.SAFE_AUTO,
            phase_unlock=Phase.ACT,
        )
        object.__setattr__(self, "store", _store_from_value(store))

    def run(self, path: str, content: str) -> bool:
        self.store.write(path, content)
        return True

