"""
Claim-Evidence Graph (P-2, Sprint 5.2)

Builds a directed graph: claims <-> evidence with typed edges
("supports", "contradicts", "extends"). Serializable for D3 rendering.

Upgrade (Agent Improvement pass): typed-triple inference via an LLM
extractor (see ``services.knowledge.triples``) with a keyword-overlap
fallback. Every inter-claim edge emitted by the LLM path must cite at
least one evidence id — the UniScientist grounding requirement. The
legacy ``_infer_links`` heuristic remains as a safety net so the frontend
never sees an empty graph.
"""

import logging
import re
from typing import Any, Dict, List, Set, Tuple

from ...models.knowledge_models import KnowledgeArtifact, KnowledgeArtifactDAO
from .triples import extract_triples

logger = logging.getLogger(__name__)


def _tokenize(text: str) -> Set[str]:
    """Extract lowercase keyword tokens from text (>3 chars)."""
    stop = {
        "that", "this", "with", "from", "have", "been", "were", "will",
        "they", "their", "which", "more", "than", "also", "into", "such",
        "based", "using", "used", "through", "between", "both", "these",
        "other", "about", "when", "most", "some", "does", "each", "over",
        "very", "only", "could", "would", "should", "while", "after",
    }
    words = set(re.findall(r"[a-z]{3,}", text.lower()))
    return words - stop


def _keyword_overlap(text_a: str, text_b: str) -> float:
    """Compute Jaccard-like similarity between two texts."""
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union) if union else 0.0


class ClaimGraph:
    """Builds a D3-renderable claim-evidence graph from a KnowledgeArtifact."""

    # Minimum keyword overlap to infer a link
    SIMILARITY_THRESHOLD = 0.12

    # Feature flag — when False, falls back to the legacy keyword heuristic
    USE_TYPED_TRIPLES = True

    def build(self, run_id: str, *, model: str = "") -> Dict[str, Any]:
        """
        Build a force-directed graph from the knowledge artifact.

        Returns:
            {
                "nodes": [{"id": str, "type": "claim"|"evidence"|"gap", "label": str, ...}],
                "links": [{"source": str, "target": str, "type": "supports"|"contradicts"|"extends"}],
                "stats": {"claims": int, "evidence": int, "gaps": int, "links": int}
            }
        """
        artifact = KnowledgeArtifactDAO.load(run_id)
        if not artifact:
            return {"nodes": [], "links": [], "stats": {"claims": 0, "evidence": 0, "gaps": 0, "links": 0}}

        nodes: List[Dict[str, Any]] = []
        links: List[Dict[str, Any]] = []

        # Evidence map for quick lookup
        ev_map = {e.evidence_id: e for e in artifact.evidence}

        # Add claim nodes
        for claim in artifact.claims:
            nodes.append({
                "id": claim.claim_id,
                "type": "claim",
                "label": claim.text[:80] + ("..." if len(claim.text) > 80 else ""),
                "full_text": claim.text,
                "category": claim.category,
                "confidence": claim.confidence,
            })

            # Supporting links
            for ev_id in claim.supporting:
                if ev_id in ev_map:
                    links.append({
                        "source": ev_id,
                        "target": claim.claim_id,
                        "type": "supports",
                    })

            # Contradicting links
            for ev_id in claim.contradicting:
                if ev_id in ev_map:
                    links.append({
                        "source": ev_id,
                        "target": claim.claim_id,
                        "type": "contradicts",
                    })

            # Extending links
            for ev_id in claim.extending:
                if ev_id in ev_map:
                    links.append({
                        "source": ev_id,
                        "target": claim.claim_id,
                        "type": "extends",
                    })

        # ── Typed-triple extraction (Awesome-LLM-KG pattern) ──────────
        typed_triples: List[Dict[str, Any]] = []
        if (
            self.USE_TYPED_TRIPLES
            and len(artifact.claims) > 0
            and len(artifact.evidence) > 0
        ):
            try:
                claims_payload = [
                    {
                        "claim_id": c.claim_id,
                        "text": c.text,
                        "category": c.category,
                    }
                    for c in artifact.claims
                ]
                evidence_payload = [
                    {
                        "evidence_id": e.evidence_id,
                        "title": e.title,
                        "excerpt": e.excerpt,
                    }
                    for e in artifact.evidence
                ]
                extracted = extract_triples(
                    claims_payload,
                    evidence_payload,
                    model=model,
                    max_triples=30,
                )
                for triple in extracted:
                    typed_triples.append(triple.to_dict())
                    links.append({
                        "source": triple.subject_id,
                        "target": triple.object_id,
                        "type": triple.relation,
                        "confidence": triple.confidence,
                        "evidence_ids": triple.evidence_ids,
                        "typed": True,
                    })
            except Exception as exc:  # noqa: BLE001
                logger.warning("[ClaimGraph] typed-triple extraction failed: %s", exc)

        # ── Auto-infer links when still empty ─────────────────────────
        if len(links) == 0 and len(artifact.claims) > 0 and len(artifact.evidence) > 0:
            logger.info("[ClaimGraph] No explicit or typed links — inferring via keyword overlap")
            links = self._infer_links(artifact)

        # Add ALL evidence nodes (not just linked ones)
        linked_ev_ids = set()
        for link in links:
            linked_ev_ids.add(link["source"])
            linked_ev_ids.add(link["target"])

        for ev in artifact.evidence:
            nodes.append({
                "id": ev.evidence_id,
                "type": "evidence",
                "label": ev.title[:60] + ("..." if len(ev.title) > 60 else ""),
                "full_text": ev.excerpt,
                "source_type": ev.source_type,
                "confidence": ev.confidence,
                "linked": ev.evidence_id in linked_ev_ids,
            })

        # Add gap nodes
        for gap in artifact.gaps:
            nodes.append({
                "id": gap.gap_id,
                "type": "gap",
                "label": gap.description[:60] + ("..." if len(gap.description) > 60 else ""),
                "full_text": gap.description,
                "severity": gap.severity,
                "suggested_approach": gap.suggested_approach,
            })
            # Explicit gap-claim links
            for claim_id in gap.related_claims:
                links.append({
                    "source": gap.gap_id,
                    "target": claim_id,
                    "type": "gap_for",
                })

        # Auto-link gaps to claims when no explicit related_claims
        gaps_without_links = [
            g for g in artifact.gaps
            if not g.related_claims
        ]
        if gaps_without_links and artifact.claims:
            for gap in gaps_without_links:
                best_claim_id = None
                best_score = 0.0
                for claim in artifact.claims:
                    score = _keyword_overlap(gap.description, claim.text)
                    if score > best_score:
                        best_score = score
                        best_claim_id = claim.claim_id
                if best_claim_id and best_score > self.SIMILARITY_THRESHOLD:
                    links.append({
                        "source": gap.gap_id,
                        "target": best_claim_id,
                        "type": "gap_for",
                    })

        stats = {
            "claims": len(artifact.claims),
            "evidence": len(artifact.evidence),
            "gaps": len(artifact.gaps),
            "links": len(links),
            "typed_triples": len(typed_triples),
        }

        logger.info(
            "[ClaimGraph] Built graph for run %s: %d nodes, %d links (%d typed)",
            run_id, len(nodes), len(links), len(typed_triples),
        )

        return {
            "nodes": nodes,
            "links": links,
            "triples": typed_triples,  # Awesome-LLM-KG typed edges (additive)
            "stats": stats,
        }

    def _infer_links(self, artifact: KnowledgeArtifact) -> List[Dict[str, Any]]:
        """Infer claim-evidence links via keyword overlap when none are explicit."""
        links: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str]] = set()

        for claim in artifact.claims:
            scored: List[Tuple[float, str]] = []
            for ev in artifact.evidence:
                # Combine evidence title + excerpt for matching
                ev_text = f"{ev.title} {ev.excerpt}"
                score = _keyword_overlap(claim.text, ev_text)
                if score >= self.SIMILARITY_THRESHOLD:
                    scored.append((score, ev.evidence_id))

            # Link top-N most relevant evidence per claim (max 3)
            scored.sort(key=lambda x: x[0], reverse=True)
            for score, ev_id in scored[:3]:
                pair = (ev_id, claim.claim_id)
                if pair not in seen:
                    seen.add(pair)
                    links.append({
                        "source": ev_id,
                        "target": claim.claim_id,
                        "type": "supports",
                    })

        logger.info("[ClaimGraph] Inferred %d links via keyword overlap", len(links))
        return links

