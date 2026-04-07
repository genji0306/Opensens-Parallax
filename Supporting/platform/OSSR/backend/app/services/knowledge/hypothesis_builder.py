"""
Contribution Hypothesis Builder (P-2, Sprint 7.1)

Builds a structured hypothesis from the research idea + gaps + novelty map.
Output: problem statement, contribution, differentiators, predicted impact.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

from ...models.knowledge_models import (
    Hypothesis,
    KnowledgeArtifact,
    KnowledgeArtifactDAO,
)
from .._agents.base import AgentResult, llm_call_with_retry
from .._agents.rollout import rollout_and_aggregate

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
        pass

    def _get_llm(self, model: str = "") -> LLMClient:
        return LLMClient(model=model) if model else LLMClient()

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
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        idea = run.research_idea

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

        prompt = HYPOTHESIS_PROMPT.format(
            idea=idea,
            claims=claims_text or "No claims yet.",
            gaps=gaps_text or "No gaps identified.",
            novelty=novelty_text or "No novelty assessment yet.",
        )

        # UniScientist multi-rollout with grounding requirement.
        # Rubric: reject rollouts that fail to cite at least two claims, and
        # prefer higher self-assessed confidence when multiple rollouts
        # pass. ``rollout_and_aggregate`` falls back cleanly when N=1.
        min_supporting = 2 if artifact and len(artifact.claims) >= 2 else 0

        def _rollout() -> AgentResult:
            return llm_call_with_retry(
                prompt,
                model=model,
                temperature=0.55,
                expect_json=True,
                max_retries=1,
            )

        def _rubric(result: AgentResult) -> float:
            if not result.ok or not isinstance(result.data, dict):
                return 0.0
            data = result.data
            differentiators = data.get("differentiators") or []
            supporting = data.get("supporting_claim_ids") or []
            # Grounding requirement
            if min_supporting and len(supporting) < min_supporting:
                return 0.0
            score = 0.4
            if len(differentiators) >= 3:
                score += 0.2
            if data.get("problem_statement"):
                score += 0.2
            if data.get("contribution"):
                score += 0.2
            return min(1.0, score)

        aggregated = rollout_and_aggregate(_rollout, n=3, rubric=_rubric)

        if aggregated.ok and isinstance(aggregated.data, dict):
            hypothesis = self._from_dict(aggregated.data, artifact)
            hypothesis_rollouts = aggregated.rollouts
        else:
            logger.info(
                "[HypothesisBuilder] rollouts failed (%s) — falling back to single-shot",
                aggregated.error,
            )
            response = self._get_llm(model).chat(
                [{"role": "user", "content": prompt}],
            )
            hypothesis = self._parse_response(response, artifact)
            hypothesis_rollouts = []

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

        logger.info(
            "[HypothesisBuilder] Built hypothesis for run %s (rollouts=%d)",
            run_id, len(hypothesis_rollouts),
        )

        return {
            "hypothesis": hypothesis.to_dict(),
            "supporting_context": context,
            "rollouts": hypothesis_rollouts,
        }

    def _from_dict(self, data: Dict[str, Any], artifact) -> Hypothesis:
        """Build a ``Hypothesis`` from a successful rollout dict."""
        # Accept both the new skill-card schema (`hypothesis`, `supporting_claim_ids`)
        # and the legacy schema (`problem_statement`, `contribution`).
        problem = data.get("problem_statement") or data.get("hypothesis", "")
        contribution = data.get("contribution") or data.get("hypothesis", "")
        differentiators = data.get("differentiators") or []
        if not differentiators and data.get("counter_evidence_acknowledged"):
            differentiators = [data["counter_evidence_acknowledged"]]
        return Hypothesis(
            problem_statement=problem,
            contribution=contribution,
            differentiators=differentiators,
            predicted_impact=data.get("predicted_impact", ""),
            supporting_gaps=data.get("addressed_gap_ids")
                or [g.gap_id for g in (artifact.gaps if artifact else [])],
            novelty_basis=data.get("supporting_claim_ids")
                or [
                    a.claim_id for a in (artifact.novelty_assessments if artifact else [])
                    if a.novelty_score >= 0.7
                ],
        )

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
