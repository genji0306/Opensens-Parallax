"""
Conflict Detector + Theme Clusterer (P-3, Sprint 10)

Detects where reviewers contradict each other and clusters
comments into 3-7 revision themes.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

from ...models.review_models import (
    ReviewComment,
    ReviewConflict,
    ReviewerResult,
    RevisionRound,
    RevisionTheme,
    RevisionHistoryDAO,
)

logger = logging.getLogger(__name__)

CONFLICT_PROMPT = """\
You are analyzing reviewer comments for contradictions. Two reviewers may
disagree about the same aspect of a paper.

=== REVIEWER COMMENTS ===
{comments}

Identify any conflicting opinions between reviewers. Return JSON:
{{
  "conflicts": [
    {{
      "reviewer_a": "reviewer type A",
      "reviewer_b": "reviewer type B",
      "comment_a_index": 0,
      "comment_b_index": 1,
      "description": "what they disagree about",
      "resolution_suggestion": "how the author should handle this"
    }}
  ],
  "themes": [
    {{
      "title": "theme title",
      "description": "what this revision theme covers",
      "priority": 1,
      "impact": "high|medium|low",
      "comment_indices": [0, 2, 5],
      "suggested_action": "what the author should do"
    }}
  ]
}}

Identify 0-3 conflicts and cluster ALL comments into 3-7 themes.
Return ONLY valid JSON."""


class ConflictDetector:
    """Detects conflicts between reviewers and clusters comments into themes."""

    def __init__(self):
        pass

    def _get_llm(self, model: str = "") -> LLMClient:
        return LLMClient(model=model) if model else LLMClient()

    def analyze(self, run_id: str, model: str = "") -> Dict[str, Any]:
        """
        Analyze the latest revision round for conflicts and themes.

        Returns:
            {
                "conflicts": [ReviewConflict.to_dict()],
                "themes": [RevisionTheme.to_dict()],
                "stats": {"conflict_count": int, "theme_count": int, "critical_themes": int}
            }
        """
        latest = RevisionHistoryDAO.latest(run_id)
        if not latest or not latest.results:
            return {"conflicts": [], "themes": [], "stats": {"conflict_count": 0, "theme_count": 0, "critical_themes": 0}}

        # Flatten all comments
        all_comments: List[ReviewComment] = []
        for result in latest.results:
            all_comments.extend(result.comments)

        if not all_comments:
            return {"conflicts": [], "themes": [], "stats": {"conflict_count": 0, "theme_count": 0, "critical_themes": 0}}

        comments_text = "\n".join(
            f"[{i}] ({c.reviewer_type}, {c.severity}) {c.section}: {c.text}"
            for i, c in enumerate(all_comments)
        )

        prompt = CONFLICT_PROMPT.format(comments=comments_text[:5000])
        response = self._get_llm(model).chat(
            [{"role": "user", "content": prompt}],
        )

        conflicts, themes = self._parse_response(response, all_comments)

        # Update the revision round
        latest.conflicts = conflicts
        latest.themes = themes
        RevisionHistoryDAO.save(latest)

        critical_themes = sum(1 for t in themes if t.priority <= 2 and t.impact == "high")

        logger.info("[ConflictDetector] Run %s: %d conflicts, %d themes",
                     run_id, len(conflicts), len(themes))

        return {
            "conflicts": [c.to_dict() for c in conflicts],
            "themes": [t.to_dict() for t in themes],
            "stats": {
                "conflict_count": len(conflicts),
                "theme_count": len(themes),
                "critical_themes": critical_themes,
            },
        }

    def detect_conflicts(
        self,
        revision_round: RevisionRound,
        *,
        model: str = "",
    ) -> Dict[str, Any]:
        """
        In-memory variant of :meth:`analyze` that takes a ``RevisionRound``
        directly (without round-tripping through the DAO). Used by the
        AgentReview 5-phase pipeline in ``BoardManager``.

        Returns the same dict shape as ``analyze`` plus two AgentReview-
        inspired bias flags:

        * ``bias.groupthink`` — True when scores cluster within a tight
          window despite reviewers having very different personas
          (27.2% convergence effect reported in AgentReview).
        * ``bias.authority`` — True when an expert reviewer's score
          dominates the cluster by more than 1.5 points.
        """
        all_comments: List[ReviewComment] = []
        for result in revision_round.results:
            all_comments.extend(result.comments)

        conflicts: List[ReviewConflict] = []
        themes: List[RevisionTheme] = []

        if all_comments:
            comments_text = "\n".join(
                f"[{i}] ({c.reviewer_type}, {c.severity}) {c.section}: {c.text}"
                for i, c in enumerate(all_comments)
            )
            prompt = CONFLICT_PROMPT.format(comments=comments_text[:5000])
            try:
                response = self._get_llm(model).chat(
                    [{"role": "user", "content": prompt}],
                )
                conflicts, themes = self._parse_response(response, all_comments)
            except Exception as exc:  # noqa: BLE001
                logger.warning("[ConflictDetector] detect_conflicts LLM call failed: %s", exc)

        # Bias heuristics — AgentReview findings
        scores = [r.overall_score for r in revision_round.results if r.overall_score > 0]
        bias: Dict[str, Any] = {"groupthink": False, "authority": False}
        if len(scores) >= 3:
            spread = max(scores) - min(scores)
            if spread <= 1.0:
                bias["groupthink"] = True
            # Authority: one reviewer more than 1.5 from the mean
            mean = sum(scores) / len(scores)
            if any(abs(s - mean) >= 1.5 for s in scores):
                bias["authority"] = True

        return {
            "conflicts": [c.to_dict() for c in conflicts],
            "themes": [t.to_dict() for t in themes],
            "bias": bias,
            "stats": {
                "conflict_count": len(conflicts),
                "theme_count": len(themes),
                "critical_themes": sum(
                    1 for t in themes if t.priority <= 2 and t.impact == "high"
                ),
            },
        }

    def _parse_response(self, response: str, comments: List[ReviewComment]):
        conflicts = []
        themes = []

        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)

            for cf in data.get("conflicts", []):
                a_idx = cf.get("comment_a_index", 0)
                b_idx = cf.get("comment_b_index", 0)
                conflicts.append(ReviewConflict(
                    reviewer_a=cf.get("reviewer_a", ""),
                    reviewer_b=cf.get("reviewer_b", ""),
                    comment_a_id=comments[a_idx].comment_id if a_idx < len(comments) else "",
                    comment_b_id=comments[b_idx].comment_id if b_idx < len(comments) else "",
                    description=cf.get("description", ""),
                    resolution_suggestion=cf.get("resolution_suggestion", ""),
                ))

            for th in data.get("themes", []):
                indices = th.get("comment_indices", [])
                themes.append(RevisionTheme(
                    title=th.get("title", ""),
                    description=th.get("description", ""),
                    priority=int(th.get("priority", 5)),
                    impact=th.get("impact", "medium"),
                    comment_ids=[
                        comments[i].comment_id
                        for i in indices
                        if i < len(comments)
                    ],
                    suggested_action=th.get("suggested_action", ""),
                ))

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[ConflictDetector] Parse error: %s", e)

        return conflicts, themes
