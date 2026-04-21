"""Cold filesystem-backed store for session workspaces."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from ...errors import ParallaxV3Error


class ColdStoreError(ParallaxV3Error):
    """Raised when a cold-store path escapes the session workspace."""


class ColdStore:
    def __init__(self, workspace_path: Path, session_id: str | None = None):
        base = Path(workspace_path)
        self.root = (base / session_id) if session_id else base
        self.root = self.root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        candidate = Path(path)
        if candidate.is_absolute():
            raise ColdStoreError(f"Absolute paths are not allowed: {path}")
        resolved = (self.root / candidate).resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise ColdStoreError(f"Path escapes workspace root: {path}") from exc
        return resolved

    def read(self, path: str) -> str:
        return self._resolve(path).read_text(encoding="utf-8")

    def write(self, path: str, content: str) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def list_files(self, subdir: str) -> list[str]:
        root = self._resolve(subdir) if subdir else self.root
        if not root.exists():
            return []
        if root.is_file():
            return [str(root.relative_to(self.root)).replace("\\", "/")]
        files = [str(path.relative_to(self.root)).replace("\\", "/") for path in root.rglob("*") if path.is_file()]
        return sorted(files)

    def hash(self, path: str) -> str:
        file_path = self._resolve(path)
        digest = hashlib.sha256()
        with file_path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


