"""Anti-leakage text scanner."""

from __future__ import annotations

import re
from pathlib import Path

PATTERNS = (
    re.compile(r"hidden reasoning", re.IGNORECASE),
    re.compile(r"chain of thought", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"developer message", re.IGNORECASE),
)


def scan_text(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def scan_file(path: str | Path) -> list[str]:
    return scan_text(Path(path).read_text(encoding="utf-8"))

