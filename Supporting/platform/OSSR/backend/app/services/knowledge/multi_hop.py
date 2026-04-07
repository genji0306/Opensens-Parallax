"""
Multi-hop retriever over the claim graph.

Given a seed node (claim, evidence, or gap) and a set of typed ``Triple``
edges, returns the N nearest grounding paths up to ``max_hops`` deep. This
is the small piece of Awesome-LLM-KG graph reasoning that ``NoveltyMapper``,
``ValidationService``, ``ConsistencyChecker`` and ``ArgumentSkeleton`` share.

Design notes
------------
* Pure in-memory. No database access — the caller passes the triples and
  node dictionaries. This keeps the retriever deterministic and test-friendly.
* Edge weight = ``triple.confidence``. Path score = product of weights.
* Emits the top-k paths sorted by score descending.
* Safely handles cycles via a visited-set.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from .._agents.schema import Triple

logger = logging.getLogger(__name__)


@dataclass
class RetrievalPath:
    nodes: List[str]
    triples: List[Triple]
    score: float = 1.0
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "triples": [t.to_dict() for t in self.triples],
            "score": self.score,
            "evidence_ids": list(self.evidence_ids),
        }


class MultiHopRetriever:
    def __init__(
        self,
        triples: Iterable[Triple],
        *,
        nodes: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        self.triples: List[Triple] = list(triples)
        self.nodes: Dict[str, Dict[str, Any]] = dict(nodes or {})
        self._out: Dict[str, List[Triple]] = {}
        self._in: Dict[str, List[Triple]] = {}
        for t in self.triples:
            self._out.setdefault(t.subject_id, []).append(t)
            self._in.setdefault(t.object_id, []).append(t)

    # ---------------------------------------------------------------- walk

    def walk(
        self,
        seed: str,
        *,
        max_hops: int = 2,
        top_k: int = 5,
        direction: str = "both",
    ) -> List[RetrievalPath]:
        """
        Return the top-k paths starting at ``seed`` up to ``max_hops`` deep.

        ``direction`` may be ``out``, ``in`` or ``both``.
        """
        if seed not in self.nodes and seed not in self._out and seed not in self._in:
            return []
        frontier: List[RetrievalPath] = [RetrievalPath(nodes=[seed], triples=[])]
        results: List[RetrievalPath] = []

        for _ in range(max_hops):
            next_frontier: List[RetrievalPath] = []
            for path in frontier:
                tail = path.nodes[-1]
                candidates: List[Tuple[Triple, str]] = []
                if direction in ("out", "both"):
                    for t in self._out.get(tail, []):
                        candidates.append((t, t.object_id))
                if direction in ("in", "both"):
                    for t in self._in.get(tail, []):
                        candidates.append((t, t.subject_id))

                for triple, next_node in candidates:
                    if next_node in path.nodes:
                        continue  # no cycles
                    new_score = path.score * max(0.01, triple.confidence)
                    evidence_ids = list(path.evidence_ids) + list(triple.evidence_ids)
                    new_path = RetrievalPath(
                        nodes=path.nodes + [next_node],
                        triples=path.triples + [triple],
                        score=new_score,
                        evidence_ids=evidence_ids,
                    )
                    next_frontier.append(new_path)
                    results.append(new_path)

            if not next_frontier:
                break
            frontier = next_frontier

        results.sort(key=lambda p: p.score, reverse=True)
        return results[:top_k]

    # ---------------------------------------------------- convenience API

    def evidence_for(self, claim_id: str, *, max_hops: int = 2) -> List[str]:
        """Return the de-duplicated evidence ids reachable from a claim."""
        seen: Set[str] = set()
        out: List[str] = []
        for path in self.walk(claim_id, max_hops=max_hops, top_k=20, direction="out"):
            for ev_id in path.evidence_ids:
                if ev_id not in seen:
                    seen.add(ev_id)
                    out.append(ev_id)
        return out

    def related_claims(self, claim_id: str, *, top_k: int = 5) -> List[Tuple[str, float]]:
        """Return the top claims connected to ``claim_id`` via any relation."""
        paths = self.walk(claim_id, max_hops=2, top_k=top_k * 3, direction="both")
        scored: Dict[str, float] = {}
        for path in paths:
            for node in path.nodes[1:]:
                if node == claim_id:
                    continue
                node_meta = self.nodes.get(node) or {}
                if node_meta.get("type", "claim") != "claim":
                    continue
                scored[node] = max(scored.get(node, 0.0), path.score)
        ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:top_k]

    def summarise(self) -> Dict[str, int]:
        return {
            "triples": len(self.triples),
            "nodes": len(self.nodes) or len(set(self._out) | set(self._in)),
            "out_degree_max": max((len(v) for v in self._out.values()), default=0),
        }
