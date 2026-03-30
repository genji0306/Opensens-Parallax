"""
Consistency Checker (P-4, Sprint 14)

Text-vs-figure contradiction detection and diagram-vs-methods consistency.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

logger = logging.getLogger(__name__)

CONSISTENCY_PROMPT = """\
You are a scientific consistency auditor. Check for contradictions between
the paper text and its figures/tables.

=== PAPER TEXT (key sections) ===
{text}

=== FIGURE/TABLE DESCRIPTIONS ===
{figures}

Check for:
1. Text claims that contradict figure data
2. Methods described in text that don't match diagrams
3. Numbers in text that differ from tables
4. Missing references to figures/tables
5. Figures that show data not discussed in text

Return JSON:
{{
  "contradictions": [
    {{
      "type": "text_vs_figure|text_vs_table|method_vs_diagram|missing_reference|unreferenced_figure",
      "severity": "critical|major|minor",
      "text_excerpt": "the text that contradicts",
      "figure_reference": "which figure/table",
      "description": "what the contradiction is",
      "recommendation": "how to resolve"
    }}
  ],
  "consistency_score": 0-10,
  "summary": "overall assessment"
}}

Return ONLY valid JSON."""


class ConsistencyChecker:
    """Detects inconsistencies between paper text and visual elements."""

    def __init__(self):
        self.llm = None

    def _get_llm(self) -> LLMClient:
        if self.llm is None:
            self.llm = LLMClient()
        return self.llm

    def check(
        self,
        text_content: str,
        figure_descriptions: List[Dict[str, str]],
        model: str = "",
    ) -> Dict[str, Any]:
        """
        Check for text-figure/table contradictions.

        Returns:
            {
                "contradictions": [...],
                "consistency_score": float,
                "summary": str,
                "stats": {"total": int, "critical": int, "major": int}
            }
        """
        figs_text = "\n".join(
            f"[{f.get('label', f'Fig {i+1}')}] ({f.get('type', 'unknown')}): {f.get('description', '')}"
            for i, f in enumerate(figure_descriptions)
        )

        model = model or "claude-sonnet-4-20250514"
        response = self._get_llm().chat(
            CONSISTENCY_PROMPT.format(
                text=text_content[:5000],
                figures=figs_text[:3000],
            ),
            model=model,
        )

        result = self._parse(response)

        contradictions = result.get("contradictions", [])
        result["stats"] = {
            "total": len(contradictions),
            "critical": sum(1 for c in contradictions if c.get("severity") == "critical"),
            "major": sum(1 for c in contradictions if c.get("severity") == "major"),
        }

        return result

    def _parse(self, response: str) -> Dict[str, Any]:
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[ConsistencyChecker] Parse error: %s", e)
            return {"contradictions": [], "consistency_score": 0, "summary": "Failed to parse"}
