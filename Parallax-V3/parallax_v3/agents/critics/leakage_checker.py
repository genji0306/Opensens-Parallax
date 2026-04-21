"""Anti-leakage checks."""

from __future__ import annotations

from dataclasses import dataclass

from ...tools.primitives.anti_leakage import scan_text


@dataclass
class LeakageChecker:
    def check(self, text: str) -> list[str]:
        return scan_text(text)

