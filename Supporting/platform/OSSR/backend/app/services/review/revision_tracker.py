"""
Revision Tracker (P-3, Sprint 12)

Tracks changes across revision rounds. Supports 4 rewrite modes:
conservative, novelty-maximizing, clarity-first, journal-style.
Ensures no regression across rounds.
"""

import logging
from typing import Any, Dict, List, Optional

from ...models.review_models import RevisionHistoryDAO, RevisionRound

logger = logging.getLogger(__name__)

REWRITE_MODES = {
    "conservative": {
        "name": "Conservative",
        "description": "Minimal changes — address critical issues only, preserve original voice",
        "instruction": "Make only the changes necessary to address critical and major reviewer concerns. "
                       "Preserve the original writing style and structure as much as possible.",
    },
    "novelty": {
        "name": "Novelty-Maximizing",
        "description": "Emphasize novel contributions, strengthen differentiation from prior work",
        "instruction": "Rewrite to maximize the novelty narrative. Strengthen claims about what is new, "
                       "sharpen comparisons with prior work, and highlight unique contributions.",
    },
    "clarity": {
        "name": "Clarity-First",
        "description": "Prioritize readability and logical flow over other concerns",
        "instruction": "Rewrite for maximum clarity. Simplify complex sentences, improve transitions, "
                       "ensure each paragraph has a clear purpose, and eliminate all ambiguity.",
    },
    "journal": {
        "name": "Journal-Style",
        "description": "Formal academic tone, journal formatting conventions",
        "instruction": "Rewrite in formal academic style. Follow journal conventions for structure, "
                       "tone, and citation style. Ensure professional register throughout.",
    },
}


class RevisionTracker:
    """Tracks revision history and detects regressions across rounds."""

    def get_rewrite_modes(self) -> Dict[str, Dict[str, str]]:
        """Return available rewrite modes with descriptions."""
        return {
            key: {"name": v["name"], "description": v["description"]}
            for key, v in REWRITE_MODES.items()
        }

    def get_rewrite_instruction(self, mode: str) -> str:
        """Get the LLM instruction for a rewrite mode."""
        return REWRITE_MODES.get(mode, REWRITE_MODES["conservative"])["instruction"]

    def get_history(self, run_id: str) -> Dict[str, Any]:
        """
        Get full revision history with cross-round analytics.

        Returns:
            {
                "rounds": [RevisionRound.to_dict()],
                "score_trajectory": [{"round": int, "avg_score": float}],
                "regression_warnings": [{"metric": str, "round": int, "detail": str}],
                "total_rounds": int,
                "latest_score": float,
                "improving": bool
            }
        """
        rounds = RevisionHistoryDAO.list_by_run(run_id)

        score_trajectory = [
            {"round": r.round_number, "avg_score": r.avg_score}
            for r in rounds
        ]

        regressions = self._detect_regressions(rounds)

        latest_score = rounds[-1].avg_score if rounds else 0
        improving = len(rounds) >= 2 and rounds[-1].avg_score >= rounds[-2].avg_score

        return {
            "rounds": [r.to_dict() for r in rounds],
            "score_trajectory": score_trajectory,
            "regression_warnings": regressions,
            "total_rounds": len(rounds),
            "latest_score": latest_score,
            "improving": improving,
        }

    def _detect_regressions(self, rounds: List[RevisionRound]) -> List[Dict[str, str]]:
        """Detect score regressions between consecutive rounds."""
        warnings = []
        for i in range(1, len(rounds)):
            prev = rounds[i - 1]
            curr = rounds[i]

            if curr.avg_score < prev.avg_score - 0.5:
                warnings.append({
                    "metric": "avg_score",
                    "round": curr.round_number,
                    "detail": f"Score dropped from {prev.avg_score:.1f} to {curr.avg_score:.1f}",
                })

            # Check per-reviewer regressions
            prev_scores = {r.reviewer_type: r.overall_score for r in prev.results}
            for result in curr.results:
                prev_s = prev_scores.get(result.reviewer_type)
                if prev_s and result.overall_score < prev_s - 1.0:
                    warnings.append({
                        "metric": f"{result.reviewer_type}_score",
                        "round": curr.round_number,
                        "detail": f"{result.reviewer_name} score dropped from {prev_s:.1f} to {result.overall_score:.1f}",
                    })

        return warnings
