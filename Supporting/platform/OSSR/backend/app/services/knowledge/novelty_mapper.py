"""
Novelty Mapper (P-2, Sprint 6.1)

Scores novelty per claim against ingested literature.
Produces a heatmap-ready data structure distinguishing novel vs well-covered zones.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

from ...models.knowledge_models import (
    KnowledgeArtifact,
    KnowledgeArtifactDAO,
    NoveltyAssessment,
)

logger = logging.getLogger(__name__)

NOVELTY_PROMPT = """\
You are a research novelty assessor. For each claim below, assess its novelty
against the provided literature context.

=== CLAIMS ===
{claims}

=== LITERATURE CONTEXT (top papers) ===
{literature}

For each claim, return a JSON array:
[
  {{
    "claim_index": 0,
    "novelty_score": 0.0-1.0,
    "explanation": "why this is/isn't novel",
    "closest_existing": ["paper titles that are most similar"],
    "differentiators": ["what makes this claim different from existing work"]
  }}
]

A score of 0.0 = well-covered in literature, 1.0 = completely novel.
Return ONLY valid JSON array."""


class NoveltyMapper:
    """Maps novelty scores across all claims in a knowledge artifact."""

    def __init__(self):
        self.llm = None

    def _get_llm(self) -> LLMClient:
        if self.llm is None:
            self.llm = LLMClient()
        return self.llm

    def map_novelty(self, run_id: str, model: str = "") -> Dict[str, Any]:
        """
        Score novelty for all claims in the artifact.

        Returns:
            {
                "assessments": [NoveltyAssessment.to_dict()],
                "heatmap": [{"claim_id", "text", "novelty_score", "zone": "novel"|"partial"|"covered"}],
                "stats": {"avg_novelty": float, "novel_count": int, "covered_count": int}
            }
        """
        artifact = KnowledgeArtifactDAO.load(run_id)
        if not artifact or not artifact.claims:
            return {"assessments": [], "heatmap": [], "stats": {"avg_novelty": 0, "novel_count": 0, "covered_count": 0}}

        literature = self._get_literature_context(run_id)
        claims_text = "\n".join(
            f"[{i}] {c.text}" for i, c in enumerate(artifact.claims)
        )

        model = model or "claude-sonnet-4-20250514"
        response = self._get_llm().chat(
            NOVELTY_PROMPT.format(claims=claims_text[:3000], literature=literature[:3000]),
            model=model,
        )

        assessments = self._parse_response(response, artifact)

        # Update artifact with novelty assessments
        artifact.novelty_assessments = assessments
        KnowledgeArtifactDAO.save(artifact)

        # Build heatmap
        heatmap = []
        for a in assessments:
            claim = next((c for c in artifact.claims if c.claim_id == a.claim_id), None)
            zone = "novel" if a.novelty_score >= 0.7 else "partial" if a.novelty_score >= 0.3 else "covered"
            heatmap.append({
                "claim_id": a.claim_id,
                "text": claim.text if claim else "",
                "novelty_score": a.novelty_score,
                "zone": zone,
                "explanation": a.explanation,
            })

        scores = [a.novelty_score for a in assessments]
        stats = {
            "avg_novelty": round(sum(scores) / max(len(scores), 1), 2),
            "novel_count": sum(1 for s in scores if s >= 0.7),
            "covered_count": sum(1 for s in scores if s < 0.3),
        }

        logger.info("[NoveltyMapper] Mapped %d claims for run %s: avg=%.2f",
                     len(assessments), run_id, stats["avg_novelty"])

        return {
            "assessments": [a.to_dict() for a in assessments],
            "heatmap": heatmap,
            "stats": stats,
        }

    def _get_literature_context(self, run_id: str) -> str:
        from ...db import get_connection
        conn = get_connection()
        rows = conn.execute("""
            SELECT p.title, p.abstract FROM papers p
            JOIN run_papers rp ON p.paper_id = rp.paper_id
            WHERE rp.run_id = ?
            ORDER BY p.citation_count DESC LIMIT 15
        """, (run_id,)).fetchall()
        return "\n".join(
            f"- {r['title']}: {(r['abstract'] or '')[:150]}" for r in rows
        )

    def _parse_response(self, response: str, artifact: KnowledgeArtifact) -> List[NoveltyAssessment]:
        assessments = []
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)
            if not isinstance(data, list):
                data = data.get("assessments", [])

            for item in data:
                idx = item.get("claim_index", 0)
                if idx < len(artifact.claims):
                    assessments.append(NoveltyAssessment(
                        claim_id=artifact.claims[idx].claim_id,
                        novelty_score=float(item.get("novelty_score", 0.5)),
                        explanation=item.get("explanation", ""),
                        closest_existing=item.get("closest_existing", []),
                        differentiators=item.get("differentiators", []),
                    ))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[NoveltyMapper] Parse error: %s", e)

        return assessments
