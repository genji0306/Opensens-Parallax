"""
Claim-Evidence Graph (P-2, Sprint 5.2)

Builds a directed graph: claims <-> evidence with typed edges
("supports", "contradicts", "extends"). Serializable for D3 rendering.
"""

import logging
from typing import Any, Dict, List

from ...models.knowledge_models import KnowledgeArtifact, KnowledgeArtifactDAO

logger = logging.getLogger(__name__)


class ClaimGraph:
    """Builds a D3-renderable claim-evidence graph from a KnowledgeArtifact."""

    def build(self, run_id: str) -> Dict[str, Any]:
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

        nodes = []
        links = []

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

        # Add evidence nodes (only those that have at least one link)
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
            # Link gaps to related claims
            for claim_id in gap.related_claims:
                links.append({
                    "source": gap.gap_id,
                    "target": claim_id,
                    "type": "gap_for",
                })

        stats = {
            "claims": len(artifact.claims),
            "evidence": len(artifact.evidence),
            "gaps": len(artifact.gaps),
            "links": len(links),
        }

        logger.info("[ClaimGraph] Built graph for run %s: %d nodes, %d links",
                     run_id, len(nodes), len(links))

        return {"nodes": nodes, "links": links, "stats": stats}
