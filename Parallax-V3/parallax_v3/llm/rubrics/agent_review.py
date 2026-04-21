"""6-axis AgentReview rubric."""

from __future__ import annotations

from statistics import mean
from typing import Any

from ...contracts import ReviewFinding


class AgentReviewRubric:
    axes = ("depth", "exec", "flow", "clarity", "evidence", "style")

    def score(self, findings: list[ReviewFinding]) -> dict[str, float]:
        scores: dict[str, float] = {}
        for axis in self.axes:
            axis_scores = [finding.score for finding in findings if finding.axis == axis]
            scores[axis] = float(mean(axis_scores)) if axis_scores else 5.0
        scores["overall"] = (
            0.20 * scores["depth"]
            + 0.20 * scores["exec"]
            + 0.15 * scores["flow"]
            + 0.15 * scores["clarity"]
            + 0.20 * scores["evidence"]
            + 0.10 * scores["style"]
        )
        return scores


