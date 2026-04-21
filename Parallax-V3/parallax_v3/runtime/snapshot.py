"""Filesystem snapshot and restore utilities."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable

from ..errors import ParallaxV3Error


class SnapshotError(ParallaxV3Error):
    """Raised when snapshot creation, verification, or restore fails."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name == "provenance.json":
            continue
        if any(part.startswith("iter") and part[3:].isdigit() for part in path.relative_to(root).parts):
            continue
        yield path


def _next_iteration(root: Path) -> int:
    pattern = re.compile(r"^iter(\d+)$")
    highest = 0
    for child in root.iterdir():
        if not child.is_dir():
            continue
        match = pattern.match(child.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


@dataclass
class Snapshot:
    workspace_path: Path
    snapshot_path: Path
    iteration: int
    hashes: dict[str, str]
    provenance_path: Path

    @classmethod
    def create(cls, workspace_path: Path) -> "Snapshot":
        workspace = Path(workspace_path).resolve()
        if not workspace.exists():
            raise SnapshotError(f"Workspace does not exist: {workspace}")
        iteration = _next_iteration(workspace)
        snapshot_path = workspace / f"iter{iteration}"
        hashes = {str(path.relative_to(workspace)).replace("\\", "/"): _sha256(path) for path in _iter_files(workspace)}
        shutil.copytree(
            workspace,
            snapshot_path,
            ignore=shutil.ignore_patterns("iter*"),
        )
        provenance = {
            "workspace": str(workspace),
            "snapshot_path": str(snapshot_path),
            "iteration": iteration,
            "hashes": hashes,
        }
        provenance_path = workspace / "provenance.json"
        snapshot_provenance_path = snapshot_path / "provenance.json"
        provenance_json = json.dumps(provenance, indent=2, sort_keys=True)
        provenance_path.write_text(provenance_json, encoding="utf-8")
        snapshot_provenance_path.write_text(provenance_json, encoding="utf-8")
        return cls(
            workspace_path=workspace,
            snapshot_path=snapshot_path,
            iteration=iteration,
            hashes=hashes,
            provenance_path=provenance_path,
        )

    @classmethod
    def restore(cls, snapshot: "Snapshot") -> None:
        workspace = snapshot.workspace_path
        source = snapshot.snapshot_path
        if not source.exists():
            raise SnapshotError(f"Snapshot path does not exist: {source}")
        for child in workspace.iterdir():
            if child.name.startswith("iter") and child.is_dir():
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        for child in source.iterdir():
            destination = workspace / child.name
            if child.is_dir():
                shutil.copytree(child, destination, dirs_exist_ok=True)
            else:
                shutil.copy2(child, destination)

    @classmethod
    def verify(cls, snapshot: "Snapshot") -> bool:
        if not snapshot.snapshot_path.exists():
            return False
        current = {
            str(path.relative_to(snapshot.snapshot_path)).replace("\\", "/"): _sha256(path)
            for path in _iter_files(snapshot.snapshot_path)
        }
        return current == snapshot.hashes


