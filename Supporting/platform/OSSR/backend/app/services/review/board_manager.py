"""
Reviewer Board Manager (P-3, Sprint 9)

Configurable reviewer panel with 5 archetypes. Runs all selected reviewers
against the draft and produces structured ReviewerResults.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

from ...models.review_models import (
    REVIEWER_ARCHETYPES,
    ReviewComment,
    ReviewerResult,
    RevisionRound,
    RevisionHistoryDAO,
)

logger = logging.getLogger(__name__)

REVIEW_PROMPT = """\
{persona}

You are reviewing a research paper draft. Apply strictness level: {strictness_label}.
Focus on: {focus}

=== DRAFT CONTENT ===
{content}

Provide a structured review. Return JSON:
{{
  "overall_score": 0-10,
  "summary": "1-2 sentence overall assessment",
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "comments": [
    {{
      "section": "which section (Introduction, Methods, etc.)",
      "text": "the comment",
      "severity": "critical|major|minor|suggestion",
      "confidence": 0.0-1.0,
      "impact": "high|medium|low",
      "category": "{rubric_example}",
      "quote": "specific text from the draft if applicable"
    }}
  ]
}}

Provide 3-8 specific comments. Be constructive. Return ONLY valid JSON."""


class BoardManager:
    """Manages a configurable panel of reviewer archetypes."""

    def __init__(self):
        self.llm = LLMClient()

    def get_available_archetypes(self) -> Dict[str, Dict[str, Any]]:
        """Return all available reviewer archetypes."""
        return {
            key: {"name": v["name"], "focus": v["focus"], "rubric": v["rubric"]}
            for key, v in REVIEWER_ARCHETYPES.items()
        }

    def run_review_round(
        self,
        run_id: str,
        content: str,
        reviewer_types: List[str] = None,
        strictness: float = 0.7,
        rewrite_mode: str = "conservative",
        model: str = "",
    ) -> RevisionRound:
        """
        Run a full review round with the selected reviewer panel.

        Args:
            run_id: Pipeline run ID
            content: Draft text to review
            reviewer_types: List of archetype keys (default: all 5)
            strictness: 0-1 scale
            rewrite_mode: conservative | novelty | clarity | journal
            model: LLM model override

        Returns:
            RevisionRound with all reviewer results
        """
        if not reviewer_types:
            reviewer_types = list(REVIEWER_ARCHETYPES.keys())

        # Determine round number
        existing = RevisionHistoryDAO.list_by_run(run_id)
        round_number = len(existing) + 1

        model = model or "claude-sonnet-4-20250514"
        strictness_label = (
            "very strict" if strictness > 0.8
            else "moderate" if strictness > 0.4
            else "lenient"
        )

        results = []
        for rtype in reviewer_types:
            archetype = REVIEWER_ARCHETYPES.get(rtype)
            if not archetype:
                logger.warning("[BoardManager] Unknown reviewer type: %s", rtype)
                continue

            result = self._run_single_reviewer(
                rtype, archetype, content, strictness_label, model
            )
            results.append(result)

        # Calculate average score
        scores = [r.overall_score for r in results if r.overall_score > 0]
        avg_score = round(sum(scores) / max(len(scores), 1), 1)

        revision_round = RevisionRound(
            run_id=run_id,
            round_number=round_number,
            rewrite_mode=rewrite_mode,
            reviewer_types=reviewer_types,
            results=results,
            avg_score=avg_score,
        )

        RevisionHistoryDAO.save(revision_round)
        logger.info("[BoardManager] Review round %d for run %s: %d reviewers, avg=%.1f",
                     round_number, run_id, len(results), avg_score)

        return revision_round

    def _run_single_reviewer(
        self,
        rtype: str,
        archetype: Dict,
        content: str,
        strictness_label: str,
        model: str,
    ) -> ReviewerResult:
        """Run a single reviewer archetype against the content."""
        rubric_example = archetype["rubric"][0] if archetype["rubric"] else "general"

        prompt = REVIEW_PROMPT.format(
            persona=archetype["persona"],
            strictness_label=strictness_label,
            focus=archetype["focus"],
            content=content[:6000],
            rubric_example=rubric_example,
        )

        try:
            response = self.llm.chat(prompt, model=model)
            return self._parse_reviewer_response(rtype, archetype["name"], response)
        except Exception as e:
            logger.error("[BoardManager] Reviewer %s failed: %s", rtype, e)
            return ReviewerResult(
                reviewer_type=rtype,
                reviewer_name=archetype["name"],
                overall_score=0,
                summary=f"Review failed: {e}",
            )

    def _parse_reviewer_response(self, rtype: str, name: str, response: str) -> ReviewerResult:
        """Parse LLM JSON response into ReviewerResult."""
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)

            comments = []
            for c in data.get("comments", []):
                comments.append(ReviewComment(
                    reviewer_type=rtype,
                    section=c.get("section", ""),
                    text=c.get("text", ""),
                    severity=c.get("severity", "minor"),
                    confidence=float(c.get("confidence", 0.8)),
                    impact=c.get("impact", "medium"),
                    category=c.get("category", ""),
                    quote=c.get("quote", ""),
                ))

            return ReviewerResult(
                reviewer_type=rtype,
                reviewer_name=name,
                overall_score=float(data.get("overall_score", 0)),
                summary=data.get("summary", ""),
                comments=comments,
                strengths=data.get("strengths", []),
                weaknesses=data.get("weaknesses", []),
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[BoardManager] Parse error for %s: %s", rtype, e)
            return ReviewerResult(
                reviewer_type=rtype,
                reviewer_name=name,
                summary="Failed to parse review response",
            )
