"""
Methods Figure Pack / Figure Brief Generator (P-4, Sprint 16)

Generate briefs for missing figures: graphical abstract, workflow diagram, results plots.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

logger = logging.getLogger(__name__)

BRIEF_PROMPT = """\
You are a scientific visualization consultant. Based on the paper content,
suggest figures that are missing and would strengthen the paper.

=== PAPER SECTIONS ===
{sections}

=== EXISTING FIGURES ===
{existing_figures}

Suggest 3-5 missing figures. For each, provide a detailed brief. Return JSON:
{{
  "briefs": [
    {{
      "figure_type": "graphical_abstract|workflow|results_plot|comparison_table|schematic|micrograph",
      "title": "suggested figure title",
      "purpose": "what this figure communicates",
      "content_description": "detailed description of what to include",
      "data_source": "which results/methods this visualizes",
      "priority": "essential|recommended|nice_to_have",
      "placement": "which section this belongs in"
    }}
  ]
}}

Return ONLY valid JSON."""


class FigureBriefGenerator:
    """Generates briefs for missing figures in a paper."""

    def __init__(self):
        self.llm = None

    def _get_llm(self) -> LLMClient:
        if self.llm is None:
            self.llm = LLMClient()
        return self.llm

    def generate(
        self,
        paper_sections: str,
        existing_figures: List[str] = None,
        model: str = "",
    ) -> Dict[str, Any]:
        """
        Generate figure briefs for a paper.

        Returns:
            {
                "briefs": [...],
                "stats": {"total": int, "essential": int, "recommended": int}
            }
        """
        existing = "\n".join(f"- {f}" for f in (existing_figures or [])) or "None listed."

        model = model or "claude-sonnet-4-20250514"
        response = self._get_llm().chat(
            BRIEF_PROMPT.format(
                sections=paper_sections[:5000],
                existing_figures=existing[:1000],
            ),
            model=model,
        )

        briefs = self._parse(response)

        return {
            "briefs": briefs,
            "stats": {
                "total": len(briefs),
                "essential": sum(1 for b in briefs if b.get("priority") == "essential"),
                "recommended": sum(1 for b in briefs if b.get("priority") == "recommended"),
            },
        }

    def _parse(self, response: str) -> List[Dict[str, Any]]:
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            data = json.loads(text)
            return data.get("briefs", [])
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[FigureBriefGenerator] Parse error: %s", e)
            return []
