"""
Typed-triple extractor for the claim graph (Awesome-LLM-KG pattern).

Upgrades the legacy keyword-overlap link inference in
``services/knowledge/claim_graph.py`` to an entity-relation-entity schema.
A ``Triple`` is ``(subject_id, relation, object_id, evidence_ids)`` where
``relation`` is one of: ``supports``, ``contradicts``, ``extends``,
``grounded_in``. Every inter-claim triple MUST cite at least one
supporting evidence id — this is the UniScientist grounding requirement.

The extractor is additive: it writes triples to ``artifact.metadata["triples"]``
so the existing DB schema does not need to change. The claim-graph builder
reads this list when present and falls back to keyword overlap otherwise.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .._agents.base import BaseAgent, llm_call_with_retry
from .._agents.schema import Triple

logger = logging.getLogger(__name__)

_VALID_RELATIONS = {"supports", "contradicts", "extends", "grounded_in"}


class ClaimGraphExtractor(BaseAgent):
    """
    Extract typed triples between claims and evidence nodes.

    This subclass opts into the ``claim_graph_extractor`` skill card. The
    default prompt emits 10-30 high-confidence triples per artifact.
    """

    name = "claim_graph_extractor"
    skill_name = "claim_graph_extractor"
    expects_json = True
    default_temperature = 0.2
    default_max_tokens = 3000

    def _compose(self, inputs: Dict[str, Any]) -> str:
        claims = inputs.get("claims") or []
        evidence = inputs.get("evidence") or []
        max_triples = int(inputs.get("max_triples", 30))

        # Compact representation — don't bloat context with unused fields
        claim_lines = [
            f"- {c.get('claim_id')}: [{c.get('category','claim')}] {c.get('text','')[:220]}"
            for c in claims
        ]
        evidence_lines = [
            f"- {e.get('evidence_id')}: {e.get('title','')[:120]}"
            for e in evidence
        ]

        return self.skill.render(
            claims="\n".join(claim_lines) or "(none)",
            evidence="\n".join(evidence_lines) or "(none)",
            max_triples=max_triples,
        )

    def _postprocess(self, data: Any, inputs: Dict[str, Any]) -> List[Triple]:
        if not isinstance(data, dict):
            return []
        raw_triples = data.get("triples") or []
        valid_claim_ids = {c.get("claim_id") for c in (inputs.get("claims") or [])}
        valid_evidence_ids = {e.get("evidence_id") for e in (inputs.get("evidence") or [])}

        out: List[Triple] = []
        for raw in raw_triples:
            if not isinstance(raw, dict):
                continue
            relation = str(raw.get("relation", "")).lower()
            if relation not in _VALID_RELATIONS:
                continue
            subject_id = str(raw.get("subject_id", ""))
            object_id = str(raw.get("object_id", ""))
            if subject_id not in valid_claim_ids and subject_id not in valid_evidence_ids:
                continue
            if object_id not in valid_claim_ids and object_id not in valid_evidence_ids:
                continue

            evidence_ids = [
                e for e in (raw.get("evidence_ids") or []) if e in valid_evidence_ids
            ]
            # Grounding requirement for inter-claim edges
            if relation in {"supports", "contradicts", "extends"} and not evidence_ids:
                logger.debug(
                    "[ClaimGraphExtractor] dropping ungrounded %s %s->%s",
                    relation, subject_id, object_id,
                )
                continue

            try:
                confidence = float(raw.get("confidence", 0.5))
            except (TypeError, ValueError):
                confidence = 0.5
            confidence = max(0.0, min(1.0, confidence))

            out.append(
                Triple(
                    subject_id=subject_id,
                    relation=relation,  # type: ignore[arg-type]
                    object_id=object_id,
                    confidence=confidence,
                    evidence_ids=evidence_ids,
                    source="llm",
                    metadata={"rationale": str(raw.get("rationale", ""))[:240]},
                )
            )
        logger.info("[ClaimGraphExtractor] emitted %d typed triples", len(out))
        return out


def extract_triples(
    claims: List[Dict[str, Any]],
    evidence: List[Dict[str, Any]],
    *,
    model: str = "",
    max_triples: int = 30,
) -> List[Triple]:
    """
    Convenience wrapper for callers that already have plain-dict claims and
    evidence and just want the list of ``Triple`` objects back. Silently
    returns ``[]`` on any LLM failure so the caller can fall back to the
    legacy keyword heuristic.
    """
    if not claims or not evidence:
        return []
    try:
        agent = ClaimGraphExtractor(model=model)
        result = agent.run({
            "claims": claims,
            "evidence": evidence,
            "max_triples": max_triples,
        })
        if result.ok:
            return result.data or []  # type: ignore[return-value]
        logger.info("[extract_triples] extractor returned error: %s", result.error)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[extract_triples] raised: %s", exc)
    return []
