"""
Grant Concept Note Generator (P-5, Sprint 17-18)

Generates grant concept notes with TRL/SRL framing from knowledge artifacts.
"""

import json
import logging
from typing import Any, Dict

from opensens_common.llm_client import LLMClient

from ...models.knowledge_models import KnowledgeArtifactDAO

logger = logging.getLogger(__name__)

GRANT_PROMPT = """\
You are a grant writing specialist. Create a grant concept note from this research.

=== RESEARCH ===
Idea: {idea}
Contribution: {contribution}
Differentiators: {differentiators}

=== EVIDENCE ===
Claims: {claims}
Gaps: {gaps}

Create a grant concept note. Return JSON:
{{
  "title": "grant title",
  "executive_summary": "200 words",
  "problem_statement": "clear articulation of the problem",
  "proposed_solution": "what this research proposes",
  "innovation_trl": {{
    "current_trl": 1-9,
    "target_trl": 1-9,
    "trl_justification": "why this TRL assessment",
    "srl": "societal readiness level description"
  }},
  "methodology": "research plan",
  "expected_outcomes": ["outcome 1", "outcome 2"],
  "impact": "broader impact statement",
  "budget_areas": [
    {{"category": "Personnel", "justification": "reason"}},
    {{"category": "Equipment", "justification": "reason"}}
  ],
  "timeline_months": 24,
  "key_risks": ["risk 1"]
}}

Return ONLY valid JSON."""


class GrantGenerator:
    """Generates grant concept notes from knowledge artifacts."""

    def __init__(self):
        self.llm = None

    def _get_llm(self) -> LLMClient:
        if self.llm is None:
            self.llm = LLMClient()
        return self.llm

    def generate(self, run_id: str, model: str = "") -> Dict[str, Any]:
        artifact = KnowledgeArtifactDAO.load(run_id)

        idea = artifact.research_idea if artifact else ""
        hyp = artifact.hypothesis if artifact else None
        contribution = hyp.contribution if hyp else ""
        differentiators = ", ".join(hyp.differentiators) if hyp else ""
        claims = "\n".join(f"- {c.text}" for c in (artifact.claims if artifact else [])[:6])
        gaps = "\n".join(f"- {g.description}" for g in (artifact.gaps if artifact else [])[:4])

        model = model or "claude-sonnet-4-20250514"
        response = self._get_llm().chat(
            GRANT_PROMPT.format(
                idea=idea, contribution=contribution,
                differentiators=differentiators,
                claims=claims or "None.", gaps=gaps or "None.",
            ),
            model=model,
        )

        return self._parse(response)

    def _parse(self, response: str) -> Dict[str, Any]:
        try:
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning("[GrantGenerator] Parse error: %s", e)
            return {"title": "Failed", "executive_summary": "Generation failed"}
