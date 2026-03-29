"""
Contribution Hypothesis Builder (P-2, Sprint 7.1)

Builds a structured hypothesis from the research idea + gaps + novelty map.
Output: problem statement, contribution, differentiators, predicted impact.
"""

import json
import logging
from typing import Any, Dict

from opensens_common.llm_client import LLMClient

from ...models.knowledge_models import (
    Hypothesis,
    KnowledgeArtifact,
    KnowledgeArtifactDAO,
)

logger = logging.getLogger(__name__)

HYPOTHESIS_PROMPT = """\
You are a research contribution strategist. Given the research context below,
formulate a structured contribution hypothesis.

Research Idea: {idea}

=== KEY CLAIMS ===
{claims}

=== IDENTIFIED GAPS ===
{gaps}

=== NOVELTY ASSESSMENT ===
{novelty}

Formulate a contribution hypothesis. Return JSON:
{{
  "problem_statement": "clear statement of the problem being addressed",
  "contribution": "what this research specifically contributes",
  "differentiators": ["what makes this different from existing work — list 3-5"],
  "predicted_impact": "expected impact on the field"
}}

Be specific and grounded in the evidence. Return ONLY valid JSON."""


class HypothesisBuilder:
    """Builds structured contribution hypotheses from knowledge artifacts."""

    def __init__(self):
        self.llm = LLMClient()

    def build(self, run_id: str, model: str = "") -> Dict[str, Any]:
        """
        Build a contribution hypothesis from the artifact's claims, gaps, and novelty.

        Returns:
            {
                "hypothesis": Hypothesis.to_dict(),
                "supporting_context": {"claims": int, "gaps": int, "novel_claims": int}
            }
        """
        artifact = KnowledgeArtifactDAO.load(run_id)
        from ...models.ais_models import PipelineRunDAO
        run = PipelineRunDAO.load(run_id)

        idea = run.research_idea if run else ""

        claims_text = ""
        gaps_text = ""
        novelty_text = ""

        if artifact:
            claims_text = "\n".join(f"- [{c.category}] {c.text}" for c in artifact.claims[:8])
            gaps_text = "\n".join(f"- [{g.severity}] {g.description}" for g in artifact.gaps[:5])
            novelty_text = "\n".join(
                f"- {a.explanation} (score: {a.novelty_score:.1f})"
                for a in artifact.novelty_assessments[:5]
            )

        model = model or "claude-sonnet-4-20250514"
        response = self.llm.chat(
            HYPOTHESIS_PROMPT.format(
                idea=idea,
                claims=claims_text or "No claims yet.",
                gaps=gaps_text or "No gaps identified.",
                novelty=novelty_text or "No novelty assessment yet.",
            ),
            model=model,
        )

        hypothesis = self._parse_response(response, artifact)

        # Save to artifact
        if artifact:
            artifact.hypothesis = hypothesis
            KnowledgeArtifactDAO.save(artifact)

        context = {
            "claims": len(artifact.claims) if artifact else 0,
            "gaps": len(artifact.gaps) if artifact else 0,
            "novel_claims": sum(
                1 for a in (artifact.novelty_assessments if artifact else [])
                if a.novelty_score >= 0.7
            ),
        }

        logger.info("[HypothesisBuilder] Built hypothesis for run %s", run_id)

        return {
            "hypothesis": hypothesis.to_dict(),
            "supporting_context": context,
        }

    def _parse_response(self, response: str, artifact) -> Hypothesis:
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)
            return Hypothesis(
                problem_statement=data.get("problem_statement", ""),
                contribution=data.get("contribution", ""),
                differentiators=data.get("differentiators", []),
                predicted_impact=data.get("predicted_impact", ""),
                supporting_gaps=[g.gap_id for g in (artifact.gaps if artifact else [])],
                novelty_basis=[
                    a.claim_id for a in (artifact.novelty_assessments if artifact else [])
                    if a.novelty_score >= 0.7
                ],
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[HypothesisBuilder] Parse error: %s", e)
            return Hypothesis(problem_statement="Failed to generate hypothesis")
