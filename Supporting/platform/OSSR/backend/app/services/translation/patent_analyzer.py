"""
Patent & Commercialization Analyzers (P-5, Sprint 19)

Patentability assessment (novelty, non-obviousness, utility) and
commercialization brief (market potential, applications, differentiators).
"""

import json
import logging
from typing import Any, Dict

from opensens_common.llm_client import LLMClient

from ...models.knowledge_models import KnowledgeArtifactDAO

logger = logging.getLogger(__name__)

PATENT_PROMPT = """\
You are a patent analysis specialist. Assess the patentability of this research.

Research: {idea}
Contribution: {contribution}
Novelty findings: {novelty}

Assess patentability. Return JSON:
{{
  "title": "potential patent title",
  "technical_field": "field classification",
  "novelty_assessment": {{
    "score": 0-10,
    "prior_art_risks": ["risk 1"],
    "novel_elements": ["element 1"]
  }},
  "non_obviousness": {{
    "score": 0-10,
    "rationale": "why this is non-obvious",
    "combination_risk": "risk of being obvious combination"
  }},
  "utility": {{
    "score": 0-10,
    "practical_applications": ["app 1"],
    "industrial_applicability": "description"
  }},
  "overall_patentability": 0-10,
  "recommendation": "proceed|needs_work|unlikely",
  "suggested_claims": ["claim 1", "claim 2"]
}}

Return ONLY valid JSON."""

COMMERCIAL_PROMPT = """\
You are a technology commercialization analyst. Assess the commercial potential.

Research: {idea}
Contribution: {contribution}
Differentiators: {differentiators}

Return JSON:
{{
  "market_overview": "target market description",
  "market_size_estimate": "TAM/SAM/SOM estimate",
  "target_applications": [
    {{"application": "name", "market_segment": "segment", "readiness": "near_term|mid_term|long_term"}}
  ],
  "competitive_landscape": {{
    "direct_competitors": ["competitor 1"],
    "indirect_competitors": ["competitor 1"],
    "differentiation": "what makes this unique"
  }},
  "business_model": "suggested model",
  "revenue_potential": "low|medium|high",
  "risks": ["risk 1"],
  "recommendation": "commercialize|license|further_research"
}}

Return ONLY valid JSON."""


class PatentAnalyzer:
    """Assesses patentability of research findings."""

    def __init__(self):
        self.llm = LLMClient()

    def analyze(self, run_id: str, model: str = "") -> Dict[str, Any]:
        artifact = KnowledgeArtifactDAO.load(run_id)
        idea = artifact.research_idea if artifact else ""
        hyp = artifact.hypothesis if artifact else None
        contribution = hyp.contribution if hyp else ""
        novelty = "\n".join(
            f"- {a.explanation} (score: {a.novelty_score:.1f})"
            for a in (artifact.novelty_assessments if artifact else [])[:5]
        )

        model = model or "claude-sonnet-4-20250514"
        response = self.llm.chat(
            PATENT_PROMPT.format(idea=idea, contribution=contribution, novelty=novelty or "None."),
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
            logger.warning("[PatentAnalyzer] Parse error: %s", e)
            return {"overall_patentability": 0, "recommendation": "error"}


class CommercialAnalyzer:
    """Assesses commercial potential of research findings."""

    def __init__(self):
        self.llm = LLMClient()

    def analyze(self, run_id: str, model: str = "") -> Dict[str, Any]:
        artifact = KnowledgeArtifactDAO.load(run_id)
        idea = artifact.research_idea if artifact else ""
        hyp = artifact.hypothesis if artifact else None
        contribution = hyp.contribution if hyp else ""
        differentiators = ", ".join(hyp.differentiators) if hyp else ""

        model = model or "claude-sonnet-4-20250514"
        response = self.llm.chat(
            COMMERCIAL_PROMPT.format(idea=idea, contribution=contribution, differentiators=differentiators or "None."),
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
            logger.warning("[CommercialAnalyzer] Parse error: %s", e)
            return {"revenue_potential": "unknown", "recommendation": "error"}
