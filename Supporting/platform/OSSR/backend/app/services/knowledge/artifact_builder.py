"""
Artifact Builder (P-2, Sprint 5.1)

Extracts structured KnowledgeArtifact from pipeline run outputs:
- Claims from debate transcripts and draft sections
- Evidence from ingested papers
- Gaps from topic mapping and validation
"""

import json
import logging
from typing import Any, Dict, List, Optional

from opensens_common.llm_client import LLMClient

from ...db import get_connection
from ...models.ais_models import PipelineRunDAO
from ...models.knowledge_models import (
    Claim,
    Evidence,
    Gap,
    KnowledgeArtifact,
    KnowledgeArtifactDAO,
)

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """\
You are a research knowledge extraction agent. Given the following pipeline outputs,
extract structured knowledge artifacts.

Research Idea: {idea}

=== DEBATE TRANSCRIPT (key arguments) ===
{debate_summary}

=== DRAFT SECTIONS ===
{draft_sections}

=== VALIDATION RESULTS ===
{validation}

=== TOPIC MAP GAPS ===
{gaps}

Extract and return a JSON object with:
{{
  "claims": [
    {{
      "text": "the claim statement",
      "category": "finding|hypothesis|method|limitation",
      "confidence": 0.0-1.0,
      "supporting_evidence": ["paper titles or debate quotes that support"],
      "contradicting_evidence": ["quotes or papers that contradict"]
    }}
  ],
  "gaps": [
    {{
      "description": "what is missing",
      "severity": "critical|major|medium|minor",
      "suggested_approach": "how to fill this gap",
      "evidence_needed": "what evidence would resolve it"
    }}
  ]
}}

Extract 5-15 claims and 3-7 gaps. Be specific and cite evidence.
Return ONLY valid JSON."""


class ArtifactBuilder:
    """Builds KnowledgeArtifact from pipeline run outputs."""

    def __init__(self):
        self.llm = None

    def _get_llm(self) -> LLMClient:
        if self.llm is None:
            self.llm = LLMClient()
        return self.llm

    def build(self, run_id: str, model: str = "") -> KnowledgeArtifact:
        """
        Extract a KnowledgeArtifact from a completed pipeline run.

        Reads debate, draft, validation, and topic data from run outputs,
        then uses LLM to extract structured claims and gaps.
        """
        run = PipelineRunDAO.load(run_id)
        if not run:
            raise ValueError(f"Run not found: {run_id}")

        # Gather pipeline outputs
        sr = run.stage_results or {}
        idea = run.research_idea or ""

        debate_summary = self._get_debate_summary(run_id, sr)
        draft_sections = self._get_draft_sections(run_id, sr)
        validation = self._get_validation(sr)
        gaps = self._get_topic_gaps(run_id)
        paper_evidence = self._get_paper_evidence(run_id)

        # LLM extraction
        prompt = EXTRACTION_PROMPT.format(
            idea=idea,
            debate_summary=debate_summary[:3000],
            draft_sections=draft_sections[:4000],
            validation=validation[:2000],
            gaps=gaps[:1500],
        )

        model = model or "claude-sonnet-4-20250514"
        response = self._get_llm().chat(prompt, model=model)

        # Parse LLM response
        claims, extracted_gaps = self._parse_extraction(response)

        # Build evidence objects from papers
        evidence_objs = [
            Evidence(
                source_type="paper",
                source_id=p.get("paper_id", ""),
                title=p.get("title", ""),
                excerpt=p.get("abstract", "")[:200],
                confidence=0.7,
            )
            for p in paper_evidence[:20]
        ]

        # Link claims to evidence (by matching titles in supporting_evidence)
        for claim in claims:
            for ev in evidence_objs:
                sup = claim.metadata.get("supporting_evidence", [])
                if any(ev.title.lower() in s.lower() for s in sup if isinstance(s, str)):
                    claim.supporting.append(ev.evidence_id)
                con = claim.metadata.get("contradicting_evidence", [])
                if any(ev.title.lower() in c.lower() for c in con if isinstance(c, str)):
                    claim.contradicting.append(ev.evidence_id)

        # Build and save artifact
        artifact = KnowledgeArtifact(
            run_id=run_id,
            research_idea=idea,
            claims=claims,
            evidence=evidence_objs,
            gaps=extracted_gaps,
        )

        KnowledgeArtifactDAO.save(artifact)
        logger.info("[ArtifactBuilder] Built artifact %s for run %s: %d claims, %d evidence, %d gaps",
                     artifact.artifact_id, run_id, len(claims), len(evidence_objs), len(extracted_gaps))

        return artifact

    def _get_debate_summary(self, run_id: str, sr: Dict) -> str:
        s3 = sr.get("stage_3", {})
        if isinstance(s3, dict):
            sim_id = s3.get("simulation_id", "")
            if sim_id:
                conn = get_connection()
                row = conn.execute(
                    "SELECT data FROM simulations WHERE simulation_id = ?", (sim_id,)
                ).fetchone()
                if row and row["data"]:
                    sim = json.loads(row["data"])
                    turns = sim.get("turns", [])
                    return "\n".join(
                        f"[{t.get('agent', '?')}] {t.get('content', '')[:200]}"
                        for t in turns[-10:]
                    )
        return "No debate data available."

    def _get_draft_sections(self, run_id: str, sr: Dict) -> str:
        s5 = sr.get("stage_5", {})
        draft_id = s5.get("draft_id", "") if isinstance(s5, dict) else ""
        if draft_id:
            conn = get_connection()
            row = conn.execute(
                "SELECT data FROM paper_drafts WHERE draft_id = ?", (draft_id,)
            ).fetchone()
            if row and row["data"]:
                draft = json.loads(row["data"])
                sections = draft.get("sections", [])
                return "\n\n".join(
                    f"## {s.get('heading', 'Section')}\n{s.get('content', '')[:500]}"
                    for s in sections
                )
        return "No draft available."

    def _get_validation(self, sr: Dict) -> str:
        val = sr.get("validation", {})
        if isinstance(val, dict):
            reviews = val.get("reviews", [])
            if reviews:
                return "\n".join(
                    f"[{r.get('domain', '?')}] Score: {r.get('overall_score', '?')} - {r.get('summary', '')[:200]}"
                    for r in reviews[:5]
                )
        return "No validation data."

    def _get_topic_gaps(self, run_id: str) -> str:
        conn = get_connection()
        rows = conn.execute("""
            SELECT t.name, t.metadata FROM topics t
            JOIN run_topics rt ON t.topic_id = rt.topic_id
            WHERE rt.run_id = ?
        """, (run_id,)).fetchall()

        gaps = []
        for row in rows:
            data = json.loads(row["metadata"]) if row["metadata"] else {}
            topic_gaps = data.get("gaps", [])
            for g in topic_gaps:
                gaps.append(f"[{row['name']}] {g}")
        return "\n".join(gaps[:10]) or "No gaps identified."

    def _get_paper_evidence(self, run_id: str) -> List[Dict]:
        conn = get_connection()
        rows = conn.execute("""
            SELECT p.paper_id, p.title, p.abstract, p.source, p.citation_count
            FROM papers p
            JOIN run_papers rp ON p.paper_id = rp.paper_id
            WHERE rp.run_id = ?
            ORDER BY p.citation_count DESC
            LIMIT 20
        """, (run_id,)).fetchall()
        return [dict(r) for r in rows]

    def _parse_extraction(self, response: str):
        """Parse LLM JSON response into Claim and Gap objects."""
        claims = []
        gaps = []

        try:
            # Extract JSON from response
            text = response.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]

            data = json.loads(text)

            for c in data.get("claims", []):
                claims.append(Claim(
                    text=c.get("text", ""),
                    category=c.get("category", "finding"),
                    confidence=float(c.get("confidence", 0.5)),
                    metadata={
                        "supporting_evidence": c.get("supporting_evidence", []),
                        "contradicting_evidence": c.get("contradicting_evidence", []),
                    },
                ))

            for g in data.get("gaps", []):
                gaps.append(Gap(
                    description=g.get("description", ""),
                    severity=g.get("severity", "medium"),
                    suggested_approach=g.get("suggested_approach", ""),
                    evidence_needed=g.get("evidence_needed", ""),
                ))

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("[ArtifactBuilder] Failed to parse extraction: %s", e)

        return claims, gaps
