"""
Tests for the typed-triple extractor and MultiHopRetriever added in the
Agent Improvement pass.
"""

from __future__ import annotations

from app.services._agents.schema import Triple
from app.services.knowledge.multi_hop import MultiHopRetriever
from app.services.knowledge.triples import ClaimGraphExtractor


# ------------------------------------------------------- extractor postprocess


class TestClaimGraphExtractor:
    def _mk(self) -> ClaimGraphExtractor:
        agent = ClaimGraphExtractor.__new__(ClaimGraphExtractor)
        # Build a minimal instance without running __init__ to avoid touching
        # LLM config during unit tests.
        agent.skill = type("S", (), {"prompt": "", "metadata": {}, "model": "",
                                       "temperature": 0.2})()
        agent.model = ""
        agent.temperature = 0.2
        agent.max_tokens = 2048
        agent.max_retries = 0
        return agent

    def test_filters_invalid_ids(self) -> None:
        agent = self._mk()
        inputs = {
            "claims": [{"claim_id": "c1"}, {"claim_id": "c2"}],
            "evidence": [{"evidence_id": "e1"}],
        }
        data = {
            "triples": [
                {"subject_id": "c1", "relation": "supports",
                 "object_id": "c2", "evidence_ids": ["e1"], "confidence": 0.9},
                {"subject_id": "c1", "relation": "supports",
                 "object_id": "ghost", "evidence_ids": ["e1"]},
            ]
        }
        triples = agent._postprocess(data, inputs)
        assert len(triples) == 1
        assert triples[0].relation == "supports"

    def test_rejects_ungrounded_inter_claim(self) -> None:
        agent = self._mk()
        inputs = {
            "claims": [{"claim_id": "c1"}, {"claim_id": "c2"}],
            "evidence": [{"evidence_id": "e1"}],
        }
        data = {
            "triples": [
                {"subject_id": "c1", "relation": "supports",
                 "object_id": "c2", "evidence_ids": []},
            ]
        }
        assert agent._postprocess(data, inputs) == []

    def test_grounded_in_does_not_need_extra_evidence(self) -> None:
        agent = self._mk()
        inputs = {
            "claims": [{"claim_id": "c1"}],
            "evidence": [{"evidence_id": "e1"}],
        }
        data = {
            "triples": [
                {"subject_id": "c1", "relation": "grounded_in",
                 "object_id": "e1", "evidence_ids": []},
            ]
        }
        triples = agent._postprocess(data, inputs)
        assert len(triples) == 1
        assert triples[0].relation == "grounded_in"

    def test_unknown_relation_dropped(self) -> None:
        agent = self._mk()
        inputs = {
            "claims": [{"claim_id": "c1"}, {"claim_id": "c2"}],
            "evidence": [{"evidence_id": "e1"}],
        }
        data = {
            "triples": [
                {"subject_id": "c1", "relation": "hints",
                 "object_id": "c2", "evidence_ids": ["e1"]},
            ]
        }
        assert agent._postprocess(data, inputs) == []


# ------------------------------------------------------------- retriever


class TestMultiHopRetriever:
    def _sample(self) -> MultiHopRetriever:
        triples = [
            Triple(subject_id="c1", relation="supports", object_id="c2",
                    evidence_ids=["e1"], confidence=0.9),
            Triple(subject_id="c2", relation="extends", object_id="c3",
                    evidence_ids=["e2"], confidence=0.7),
            Triple(subject_id="c1", relation="grounded_in", object_id="e1",
                    confidence=0.8),
        ]
        nodes = {
            "c1": {"type": "claim"},
            "c2": {"type": "claim"},
            "c3": {"type": "claim"},
            "e1": {"type": "evidence"},
            "e2": {"type": "evidence"},
        }
        return MultiHopRetriever(triples, nodes=nodes)

    def test_walk_out(self) -> None:
        retriever = self._sample()
        paths = retriever.walk("c1", max_hops=2, direction="out")
        assert paths
        assert any("c3" in p.nodes for p in paths)

    def test_evidence_for(self) -> None:
        retriever = self._sample()
        ev = retriever.evidence_for("c1", max_hops=2)
        assert "e1" in ev

    def test_related_claims(self) -> None:
        retriever = self._sample()
        related = retriever.related_claims("c1", top_k=5)
        related_ids = [node for node, _ in related]
        assert "c2" in related_ids

    def test_no_cycle(self) -> None:
        triples = [
            Triple(subject_id="a", relation="supports", object_id="b",
                    evidence_ids=["e1"], confidence=0.9),
            Triple(subject_id="b", relation="supports", object_id="a",
                    evidence_ids=["e2"], confidence=0.9),
        ]
        retriever = MultiHopRetriever(triples, nodes={"a": {}, "b": {}, "e1": {}, "e2": {}})
        paths = retriever.walk("a", max_hops=3, direction="out")
        # Every path's nodes must be unique
        for path in paths:
            assert len(set(path.nodes)) == len(path.nodes)
