"""
Revision Planner + Author Rebuttal Generator (P-3, Sprint 11)

Creates a prioritized revision plan from reviewer comments and generates
point-by-point response-to-reviewers.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

from ...models.review_models import RevisionHistoryDAO, RevisionTheme

logger = logging.getLogger(__name__)

REVISION_PLAN_PROMPT = """\
You are helping an author create a revision plan from reviewer feedback.

=== REVISION THEMES (prioritized) ===
{themes}

=== REVIEWER SUMMARIES ===
{summaries}

Create a prioritized revision plan. Return JSON:
{{
  "plan": [
    {{
      "priority": 1,
      "theme": "theme title",
      "action": "specific action to take",
      "sections_affected": ["Introduction", "Methods"],
      "estimated_effort": "minor|moderate|major",
      "rationale": "why this matters"
    }}
  ]
}}

Order by impact. Return ONLY valid JSON."""

REBUTTAL_PROMPT = """\
You are helping an author write a response to reviewers. For each reviewer
comment, draft a point-by-point response.

=== REVIEWER COMMENTS ===
{comments}

=== REVISION PLAN ===
{plan}

For each comment, write a response. Return JSON:
{{
  "responses": [
    {{
      "comment_id": "the original comment ID",
      "reviewer_type": "which reviewer",
      "response": "Dear Reviewer, we thank you for... We have addressed this by...",
      "action_taken": "what was changed",
      "status": "addressed|partially_addressed|respectfully_disagreed"
    }}
  ]
}}

Be professional and constructive. Return ONLY valid JSON."""


class RevisionPlanner:
    """Creates prioritized revision plans and response-to-reviewers."""

    def __init__(self):
        pass

    def _get_llm(self, model: str = "") -> LLMClient:
        return LLMClient(model=model) if model else LLMClient()

    def create_plan(self, run_id: str, model: str = "") -> Dict[str, Any]:
        """
        Generate a prioritized revision plan from the latest review round.

        Returns:
            {
                "plan": [{"priority", "theme", "action", "sections_affected", "estimated_effort", "rationale"}],
                "stats": {"total_actions": int, "major_actions": int}
            }
        """
        latest = RevisionHistoryDAO.latest(run_id)
        if not latest:
            return {"plan": [], "stats": {"total_actions": 0, "major_actions": 0}}

        themes_text = "\n".join(
            f"[P{t.priority}] {t.title}: {t.description} (impact: {t.impact})"
            for t in sorted(latest.themes, key=lambda t: t.priority)
        ) or "No themes identified."

        summaries_text = "\n".join(
            f"[{r.reviewer_type}] Score: {r.overall_score}/10 — {r.summary}"
            for r in latest.results
        )

        prompt = REVISION_PLAN_PROMPT.format(themes=themes_text, summaries=summaries_text)
        response = self._get_llm(model).chat(
            [{"role": "user", "content": prompt}],
        )

        plan = self._parse_plan(response)

        logger.info("[RevisionPlanner] Created plan for run %s: %d actions", run_id, len(plan))

        return {
            "plan": plan,
            "stats": {
                "total_actions": len(plan),
                "major_actions": sum(1 for p in plan if p.get("estimated_effort") == "major"),
            },
        }

    def generate_rebuttal(self, run_id: str, model: str = "") -> Dict[str, Any]:
        """
        Generate point-by-point response-to-reviewers.

        Returns:
            {
                "responses": [{"comment_id", "reviewer_type", "response", "action_taken", "status"}],
                "stats": {"total": int, "addressed": int, "disagreed": int}
            }
        """
        latest = RevisionHistoryDAO.latest(run_id)
        if not latest:
            return {"responses": [], "stats": {"total": 0, "addressed": 0, "disagreed": 0}}

        all_comments = []
        for result in latest.results:
            all_comments.extend(result.comments)

        if not all_comments:
            return {"responses": [], "stats": {"total": 0, "addressed": 0, "disagreed": 0}}

        comments_text = "\n".join(
            f"[{c.comment_id}] ({c.reviewer_type}, {c.severity}) {c.text}"
            for c in all_comments
        )

        plan_text = "\n".join(
            f"- {t.title}: {t.suggested_action}"
            for t in latest.themes
        ) or "No revision plan."

        prompt = REBUTTAL_PROMPT.format(comments=comments_text[:5000], plan=plan_text[:2000])
        response = self._get_llm(model).chat(
            [{"role": "user", "content": prompt}],
        )

        responses = self._parse_rebuttal(response)

        addressed = sum(1 for r in responses if r.get("status") == "addressed")
        disagreed = sum(1 for r in responses if r.get("status") == "respectfully_disagreed")

        logger.info("[RevisionPlanner] Rebuttal for run %s: %d responses", run_id, len(responses))

        return {
            "responses": responses,
            "stats": {
                "total": len(responses),
                "addressed": addressed,
                "disagreed": disagreed,
            },
        }

    def _parse_plan(self, response: str) -> List[Dict[str, Any]]:
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            data = json.loads(text)
            return data.get("plan", [])
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[RevisionPlanner] Plan parse error: %s", e)
            return []

    def _parse_rebuttal(self, response: str) -> List[Dict[str, Any]]:
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            data = json.loads(text)
            return data.get("responses", [])
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[RevisionPlanner] Rebuttal parse error: %s", e)
            return []
