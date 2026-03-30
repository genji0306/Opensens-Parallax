"""
Template Engine (P-5, Sprint 17-18)

Maps KnowledgeArtifact to 5 output modes:
journal paper, grant concept note, funding brief, patent assessment, commercial brief.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

from ...models.knowledge_models import KnowledgeArtifact, KnowledgeArtifactDAO

logger = logging.getLogger(__name__)

OUTPUT_MODES = {
    "journal": {
        "name": "Journal Paper",
        "description": "Full academic paper structured for journal submission",
        "sections": ["Abstract", "Introduction", "Related Work", "Methodology", "Results", "Discussion", "Conclusion"],
    },
    "grant": {
        "name": "Grant Concept Note",
        "description": "Funding proposal with TRL/SRL framing and budget justification",
        "sections": ["Executive Summary", "Problem Statement", "Proposed Solution", "Innovation & TRL", "Methodology", "Expected Outcomes", "Budget Justification"],
    },
    "funding": {
        "name": "Funding Brief",
        "description": "Short funding pitch for internal/external stakeholders",
        "sections": ["Problem", "Solution", "Market Opportunity", "Technical Approach", "Team", "Ask"],
    },
    "patent": {
        "name": "Patent Assessment",
        "description": "Patentability analysis with novelty, non-obviousness, and utility",
        "sections": ["Title", "Technical Field", "Background", "Summary of Invention", "Novelty Analysis", "Non-Obviousness", "Utility", "Claims Outline"],
    },
    "commercial": {
        "name": "Commercialization Brief",
        "description": "Market potential, applications, and differentiation analysis",
        "sections": ["Market Overview", "Target Applications", "Competitive Landscape", "Differentiation", "Go-to-Market", "Revenue Model", "Risks"],
    },
}

TRANSLATE_PROMPT = """\
You are a research translation specialist. Convert the following knowledge
artifact into a {mode_name}.

=== KNOWLEDGE ARTIFACT ===
Research Idea: {idea}

Key Claims:
{claims}

Gaps:
{gaps}

Hypothesis:
{hypothesis}

Create a {mode_name} with these sections: {sections}

Return JSON:
{{
  "title": "document title",
  "mode": "{mode_key}",
  "sections": [
    {{
      "heading": "section heading",
      "content": "section content (2-4 paragraphs)"
    }}
  ],
  "metadata": {{
    "word_count": 0,
    "key_terms": ["term1", "term2"]
  }}
}}

Return ONLY valid JSON."""


class TemplateEngine:
    """Translates KnowledgeArtifact into multiple output formats."""

    def __init__(self):
        self.llm = None

    def _get_llm(self) -> LLMClient:
        if self.llm is None:
            self.llm = LLMClient()
        return self.llm

    def get_output_modes(self) -> Dict[str, Dict[str, Any]]:
        return {k: {"name": v["name"], "description": v["description"]} for k, v in OUTPUT_MODES.items()}

    def translate(
        self,
        run_id: str,
        mode: str = "journal",
        model: str = "",
    ) -> Dict[str, Any]:
        """
        Translate a knowledge artifact into the specified output mode.

        Returns:
            {"title": str, "mode": str, "sections": [...], "metadata": {...}}
        """
        artifact = KnowledgeArtifactDAO.load(run_id)
        mode_info = OUTPUT_MODES.get(mode, OUTPUT_MODES["journal"])

        idea = artifact.research_idea if artifact else ""
        claims = "\n".join(f"- {c.text}" for c in (artifact.claims if artifact else [])[:8])
        gaps = "\n".join(f"- {g.description}" for g in (artifact.gaps if artifact else [])[:5])
        hyp = artifact.hypothesis
        hypothesis = f"Problem: {hyp.problem_statement}\nContribution: {hyp.contribution}" if hyp else "Not defined"

        model = model or "claude-sonnet-4-20250514"
        response = self._get_llm().chat(
            TRANSLATE_PROMPT.format(
                mode_name=mode_info["name"],
                mode_key=mode,
                idea=idea,
                claims=claims or "No claims.",
                gaps=gaps or "No gaps.",
                hypothesis=hypothesis,
                sections=", ".join(mode_info["sections"]),
            ),
            model=model,
        )

        return self._parse(response, mode)

    def translate_all(self, run_id: str, model: str = "") -> Dict[str, Any]:
        """Translate to all 5 output modes simultaneously."""
        results = {}
        for mode_key in OUTPUT_MODES:
            results[mode_key] = self.translate(run_id, mode=mode_key, model=model)
        return {
            "outputs": results,
            "stats": {"modes_generated": len(results)},
        }

    def _parse(self, response: str, mode: str) -> Dict[str, Any]:
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[TemplateEngine] Parse error for %s: %s", mode, e)
            return {"title": "Failed", "mode": mode, "sections": [], "metadata": {}}
