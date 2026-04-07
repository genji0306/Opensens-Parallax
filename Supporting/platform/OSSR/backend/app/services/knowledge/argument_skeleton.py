"""
Citation-Backed Argument Skeleton (P-2, Sprint 7.2)

Generates a section-by-section outline with pre-assigned citations.
Fed into the draft generator instead of free-form outline.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

from ...models.knowledge_models import (
    ArgumentSection,
    KnowledgeArtifact,
    KnowledgeArtifactDAO,
)

logger = logging.getLogger(__name__)

SKELETON_PROMPT = """\
You are an academic paper structure architect. Given the research hypothesis
and available evidence, create a citation-backed argument skeleton.

=== HYPOTHESIS ===
Problem: {problem}
Contribution: {contribution}
Differentiators: {differentiators}

=== KEY CLAIMS ===
{claims}

=== AVAILABLE PAPERS (for citation assignment) ===
{papers}

Create a section-by-section paper outline. For each section, assign specific
papers as citations based on relevance. Return JSON:
{{
  "sections": [
    {{
      "heading": "section title",
      "purpose": "what this section argues/establishes",
      "key_points": ["point 1", "point 2"],
      "assigned_citations": ["paper title 1", "paper title 2"]
    }}
  ]
}}

Include: Introduction, Related Work, Methodology, Results, Discussion, Conclusion.
Return ONLY valid JSON."""


class ArgumentSkeleton:
    """Generates citation-backed argument skeletons from knowledge artifacts."""

    def __init__(self):
        pass

    def _get_llm(self, model: str = "") -> LLMClient:
        return LLMClient(model=model) if model else LLMClient()

    def build(self, run_id: str, model: str = "") -> Dict[str, Any]:
        """
        Build an argument skeleton from the artifact's hypothesis and evidence.

        Returns:
            {
                "sections": [ArgumentSection.to_dict()],
                "stats": {"total_sections": int, "total_citations": int, "uncited_sections": int}
            }
        """
        artifact = KnowledgeArtifactDAO.load(run_id)
        if not artifact:
            raise ValueError(f"No knowledge artifact found for run: {run_id}")

        hypothesis = artifact.hypothesis
        problem = hypothesis.problem_statement if hypothesis else "Not defined"
        contribution = hypothesis.contribution if hypothesis else "Not defined"
        differentiators = ", ".join(hypothesis.differentiators) if hypothesis else "None"

        claims_text = "\n".join(f"- {c.text}" for c in artifact.claims[:10])

        papers = self._get_paper_titles(run_id)

        prompt = SKELETON_PROMPT.format(
            problem=problem,
            contribution=contribution,
            differentiators=differentiators,
            claims=claims_text or "No claims.",
            papers=papers or "No papers available.",
        )
        response = self._get_llm(model).chat(
            [{"role": "user", "content": prompt}],
        )

        sections = self._parse_response(response)

        # Save to artifact
        if artifact:
            artifact.argument_skeleton = sections
            KnowledgeArtifactDAO.save(artifact)

        total_citations = sum(len(s.assigned_citations) for s in sections)
        uncited = sum(1 for s in sections if not s.assigned_citations)

        logger.info("[ArgumentSkeleton] Built skeleton for run %s: %d sections, %d citations",
                     run_id, len(sections), total_citations)

        return {
            "sections": [s.to_dict() for s in sections],
            "stats": {
                "total_sections": len(sections),
                "total_citations": total_citations,
                "uncited_sections": uncited,
            },
        }

    def _get_paper_titles(self, run_id: str) -> str:
        from ...db import get_connection
        conn = get_connection()
        rows = conn.execute("""
            SELECT p.title FROM papers p
            JOIN run_papers rp ON p.paper_id = rp.paper_id
            WHERE rp.run_id = ?
            ORDER BY p.citation_count DESC LIMIT 20
        """, (run_id,)).fetchall()
        return "\n".join(f"- {r['title']}" for r in rows)

    def _parse_response(self, response: str) -> List[ArgumentSection]:
        sections = []
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)

            for i, item in enumerate(data.get("sections", [])):
                sections.append(ArgumentSection(
                    section_id=f"sec_{i}",
                    heading=item.get("heading", f"Section {i + 1}"),
                    purpose=item.get("purpose", ""),
                    key_points=item.get("key_points", []),
                    assigned_citations=item.get("assigned_citations", []),
                    order=i,
                ))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[ArgumentSkeleton] Parse error: %s", e)

        return sections
