"""
Automated Figure Critique (P-4, Sprint 13)

Specialized critique prompts per figure type (plots, micrographs, diagrams).
Auto-triggered during Validate stage, not manual.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

logger = logging.getLogger(__name__)

FIGURE_TYPES = {
    "plot": {
        "label": "Data Plot / Chart",
        "criteria": [
            "axes_labeled", "units_present", "error_bars", "legend_clarity",
            "data_to_ink_ratio", "color_accessibility", "scale_appropriate",
        ],
    },
    "micrograph": {
        "label": "Micrograph / Image",
        "criteria": [
            "scale_bar", "resolution_adequate", "contrast_appropriate",
            "annotation_clarity", "representative_sample", "processing_disclosed",
        ],
    },
    "diagram": {
        "label": "Schematic / Diagram",
        "criteria": [
            "flow_direction_clear", "labels_complete", "complexity_appropriate",
            "consistent_style", "key_components_identified", "self_contained",
        ],
    },
    "table": {
        "label": "Table",
        "criteria": [
            "headers_clear", "units_specified", "significant_figures_consistent",
            "comparison_meaningful", "notes_provided", "alignment_readable",
        ],
    },
}

CRITIQUE_PROMPT = """\
You are a scientific figure reviewer specializing in {figure_type} analysis.

=== FIGURE DESCRIPTION ===
{description}

=== PAPER CONTEXT ===
{context}

Evaluate this figure against these criteria: {criteria}

Return JSON:
{{
  "figure_type": "{figure_type_key}",
  "overall_quality": 0-10,
  "summary": "1-2 sentence assessment",
  "criteria_scores": {{
    "criterion_name": {{"score": 0-10, "note": "explanation"}}
  }},
  "issues": [
    {{
      "severity": "critical|major|minor|suggestion",
      "description": "the issue",
      "recommendation": "how to fix"
    }}
  ],
  "strengths": ["strength 1"]
}}

Return ONLY valid JSON."""


class FigureCritique:
    """Automated critique for scientific figures by type."""

    def __init__(self):
        self.llm = LLMClient()

    def get_figure_types(self) -> Dict[str, Dict]:
        return FIGURE_TYPES

    def critique(
        self,
        figure_description: str,
        figure_type: str = "plot",
        paper_context: str = "",
        model: str = "",
    ) -> Dict[str, Any]:
        """Critique a single figure."""
        ft = FIGURE_TYPES.get(figure_type, FIGURE_TYPES["plot"])
        criteria = ", ".join(ft["criteria"])

        model = model or "claude-sonnet-4-20250514"
        response = self.llm.chat(
            CRITIQUE_PROMPT.format(
                figure_type=ft["label"],
                figure_type_key=figure_type,
                description=figure_description[:2000],
                context=paper_context[:2000],
                criteria=criteria,
            ),
            model=model,
        )

        return self._parse(response)

    def critique_all(
        self,
        figures: List[Dict[str, str]],
        paper_context: str = "",
        model: str = "",
    ) -> Dict[str, Any]:
        """Critique multiple figures. Each dict needs 'description' and optional 'type'."""
        results = []
        for fig in figures:
            result = self.critique(
                figure_description=fig.get("description", ""),
                figure_type=fig.get("type", "plot"),
                paper_context=paper_context,
                model=model,
            )
            results.append(result)

        scores = [r.get("overall_quality", 0) for r in results]
        avg = round(sum(scores) / max(len(scores), 1), 1)

        return {
            "figures": results,
            "stats": {
                "total": len(results),
                "avg_quality": avg,
                "critical_issues": sum(
                    sum(1 for i in r.get("issues", []) if i.get("severity") == "critical")
                    for r in results
                ),
            },
        }

    def _parse(self, response: str) -> Dict[str, Any]:
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[FigureCritique] Parse error: %s", e)
            return {"overall_quality": 0, "summary": "Failed to parse critique", "issues": [], "strengths": []}
