"""
Table Intelligence (P-4, Sprint 15)

Table extraction, summarization, and anomaly detection.
"""

import json
import logging
from typing import Any, Dict, List

from opensens_common.llm_client import LLMClient

logger = logging.getLogger(__name__)

TABLE_PROMPT = """\
You are a scientific data analyst reviewing tables in a research paper.

=== TABLE DATA ===
{table_data}

=== PAPER CONTEXT ===
{context}

Analyze this table:
1. Summarize what the table shows
2. Check for anomalies (outliers, inconsistencies, suspicious patterns)
3. Verify units and significant figures
4. Check if the table supports the paper's claims

Return JSON:
{{
  "summary": "what the table shows",
  "key_findings": ["finding 1", "finding 2"],
  "anomalies": [
    {{
      "type": "outlier|inconsistency|missing_data|unit_error|precision_issue",
      "severity": "critical|major|minor",
      "description": "the anomaly",
      "location": "which row/column",
      "recommendation": "how to fix"
    }}
  ],
  "quality_score": 0-10,
  "supports_claims": true
}}

Return ONLY valid JSON."""


class TableAnalyzer:
    """Analyzes tables in research papers for quality and anomalies."""

    def __init__(self):
        self.llm = LLMClient()

    def analyze(
        self,
        table_data: str,
        paper_context: str = "",
        model: str = "",
    ) -> Dict[str, Any]:
        """Analyze a single table."""
        model = model or "claude-sonnet-4-20250514"
        response = self.llm.chat(
            TABLE_PROMPT.format(
                table_data=table_data[:3000],
                context=paper_context[:2000],
            ),
            model=model,
        )
        return self._parse(response)

    def analyze_all(
        self,
        tables: List[Dict[str, str]],
        paper_context: str = "",
        model: str = "",
    ) -> Dict[str, Any]:
        """Analyze multiple tables. Each dict needs 'data' and optional 'label'."""
        results = []
        for table in tables:
            result = self.analyze(
                table_data=table.get("data", ""),
                paper_context=paper_context,
                model=model,
            )
            result["label"] = table.get("label", f"Table {len(results) + 1}")
            results.append(result)

        scores = [r.get("quality_score", 0) for r in results]
        total_anomalies = sum(len(r.get("anomalies", [])) for r in results)

        return {
            "tables": results,
            "stats": {
                "total_tables": len(results),
                "avg_quality": round(sum(scores) / max(len(scores), 1), 1),
                "total_anomalies": total_anomalies,
                "critical_anomalies": sum(
                    sum(1 for a in r.get("anomalies", []) if a.get("severity") == "critical")
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
            logger.warning("[TableAnalyzer] Parse error: %s", e)
            return {"summary": "Failed to parse", "anomalies": [], "quality_score": 0}
