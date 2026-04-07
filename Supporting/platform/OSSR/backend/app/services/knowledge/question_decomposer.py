"""
Research Question Decomposer (P-2, Sprint 6.2)

Decomposes a research idea into 3-7 sub-questions with evidence coverage indicators.
Produces a tree structure for visualization.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

from ...models.knowledge_models import (
    KnowledgeArtifact,
    KnowledgeArtifactDAO,
    SubQuestion,
)

logger = logging.getLogger(__name__)

DECOMPOSE_PROMPT = """\
You are a research question decomposition expert. Break down the following
research idea into a tree of sub-questions.

Research Idea: {idea}

=== EXISTING CLAIMS ===
{claims}

=== EVIDENCE COVERAGE ===
{evidence_summary}

Decompose into 3-7 primary sub-questions. For each, optionally add 1-3
sub-sub-questions. For each question, estimate evidence coverage (0.0-1.0)
based on how well the existing claims and evidence address it.

Return JSON:
{{
  "questions": [
    {{
      "text": "the sub-question",
      "evidence_coverage": 0.0-1.0,
      "children": [
        {{
          "text": "a sub-sub-question",
          "evidence_coverage": 0.0-1.0
        }}
      ]
    }}
  ]
}}

Return ONLY valid JSON."""


class QuestionDecomposer:
    """Decomposes research ideas into sub-question trees."""

    def __init__(self):
        pass

    def _get_llm(self, model: str = "") -> LLMClient:
        return LLMClient(model=model) if model else LLMClient()

    def decompose(self, run_id: str, model: str = "") -> Dict[str, Any]:
        """
        Decompose the research idea into sub-questions with evidence coverage.

        Returns:
            {
                "questions": [SubQuestion.to_dict()],
                "tree": nested structure for visualization,
                "stats": {"total_questions": int, "avg_coverage": float, "uncovered_count": int}
            }
        """
        artifact = KnowledgeArtifactDAO.load(run_id)
        from ...models.ais_models import PipelineRunDAO
        run = PipelineRunDAO.load(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        idea = run.research_idea
        claims_text = ""
        evidence_summary = ""

        if artifact:
            claims_text = "\n".join(f"- {c.text}" for c in artifact.claims[:10])
            evidence_summary = f"{len(artifact.evidence)} pieces of evidence, {len(artifact.claims)} claims"

        prompt = DECOMPOSE_PROMPT.format(
            idea=idea,
            claims=claims_text or "No claims extracted yet.",
            evidence_summary=evidence_summary or "No evidence yet.",
        )
        response = self._get_llm(model).chat(
            [{"role": "user", "content": prompt}],
        )

        questions, tree = self._parse_response(response)

        # Save to artifact
        if artifact:
            artifact.sub_questions = questions
            KnowledgeArtifactDAO.save(artifact)

        coverages = [q.evidence_coverage for q in questions]
        stats = {
            "total_questions": len(questions),
            "avg_coverage": round(sum(coverages) / max(len(coverages), 1), 2),
            "uncovered_count": sum(1 for c in coverages if c < 0.3),
        }

        logger.info("[QuestionDecomposer] Decomposed into %d questions for run %s",
                     len(questions), run_id)

        return {
            "questions": [q.to_dict() for q in questions],
            "tree": tree,
            "stats": stats,
        }

    def _parse_response(self, response: str):
        questions = []
        tree = []

        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)

            for item in data.get("questions", []):
                parent = SubQuestion(
                    text=item.get("text", ""),
                    evidence_coverage=float(item.get("evidence_coverage", 0.0)),
                )
                questions.append(parent)

                tree_node = {
                    "id": parent.question_id,
                    "text": parent.text,
                    "evidence_coverage": parent.evidence_coverage,
                    "children": [],
                }

                for child_item in item.get("children", []):
                    child = SubQuestion(
                        text=child_item.get("text", ""),
                        parent_id=parent.question_id,
                        evidence_coverage=float(child_item.get("evidence_coverage", 0.0)),
                    )
                    questions.append(child)
                    tree_node["children"].append({
                        "id": child.question_id,
                        "text": child.text,
                        "evidence_coverage": child.evidence_coverage,
                        "children": [],
                    })

                tree.append(tree_node)

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[QuestionDecomposer] Parse error: %s", e)

        return questions, tree
