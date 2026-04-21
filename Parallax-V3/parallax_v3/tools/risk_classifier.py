"""Shell command risk classifier."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern

from ..contracts import RiskLevel
from ..errors import ParallaxV3Error


class RiskClassifierError(ParallaxV3Error):
    """Raised when a command cannot be classified."""


def _rule(pattern: str, level: RiskLevel) -> tuple[Pattern[str], RiskLevel]:
    return re.compile(pattern, re.IGNORECASE), level


def _default_rules() -> list[tuple[Pattern[str], RiskLevel]]:
    return [
        _rule(r"\brm\s+-rf\b|\brm\s+-r\s+/\s*$", RiskLevel.DANGER_BLOCK),
        _rule(r"\bpip\s+(install|uninstall)\b", RiskLevel.ASK_USER),
        _rule(r"\b(curl|wget|nc|netcat)\b", RiskLevel.ASK_USER),
        _rule(r"\bgit\s+push\b|\bgit\s+reset\s+--hard\b|\bgit\s+clean\s+-f\b", RiskLevel.SAFE_CONFIRM),
        _rule(r"\bpytest\b|\bpython\s+-m\s+pytest\b|\bnpm\s+test\b|\bnpm\s+run\s+test\b", RiskLevel.SAFE_AUTO),
        _rule(r"\blatexmk\b|\bpdflatex\b|\bpython\s+-m\s+parallax_v3\b", RiskLevel.SAFE_AUTO),
    ]


@dataclass
class RiskClassifier:
    rules: list[tuple[Pattern[str], RiskLevel]] = field(default_factory=_default_rules)

    def classify(self, command: str) -> RiskLevel:
        for pattern, level in self.rules:
            if pattern.search(command):
                return level
        return RiskLevel.ASK_USER

