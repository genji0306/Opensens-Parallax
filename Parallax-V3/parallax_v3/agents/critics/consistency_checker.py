"""Consistency checks across section drafts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ConsistencyChecker:
    def check(self, sections: dict[str, str]) -> list[str]:
        issues: list[str] = []
        if "methods" in sections and "results" in sections:
            if "control" not in sections["methods"].lower() and "control" in sections["results"].lower():
                issues.append("Results mention control conditions missing from methods.")
        return issues

