"""Progressive compaction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass
class CompactionResult:
    retained: list[str]
    compacted: list[str]
    summary: str


@dataclass
class ProgressiveCompactor:
    retain_fraction: float = 0.7

    def compact(self, items: Iterable[str]) -> CompactionResult:
        values = list(items)
        if not values:
            return CompactionResult(retained=[], compacted=[], summary="")
        cutoff = max(1, int(len(values) * (1.0 - self.retain_fraction)))
        compacted = values[:cutoff]
        retained = values[cutoff:]
        summary = " ".join(compacted)
        return CompactionResult(retained=retained, compacted=compacted, summary=summary)

