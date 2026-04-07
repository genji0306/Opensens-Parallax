"""
Tests for the shared agent foundation layer added in the Agent Improvement
pass. These are pure-Python tests — no LLM calls, no DB.
"""

from __future__ import annotations

import pytest

from app.services._agents.base import AgentResult, parse_json_lenient
from app.services._agents.prompt_loader import SkillCard, load_skill
from app.services._agents.rollout import rollout_and_aggregate
from app.services._agents.schema import (
    Annotation,
    ReviewerPersona3D,
    ToolCall,
    Triple,
)


# ------------------------------------------------------------ parse_json


class TestParseJsonLenient:
    def test_plain_object(self) -> None:
        assert parse_json_lenient('{"a": 1}') == {"a": 1}

    def test_fenced_code_block(self) -> None:
        text = "```json\n{\"a\": 2}\n```"
        assert parse_json_lenient(text) == {"a": 2}

    def test_embedded_in_prose(self) -> None:
        text = "Here is the answer: {\"a\": 3} — that's it."
        assert parse_json_lenient(text) == {"a": 3}

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_json_lenient("")


# ------------------------------------------------------------ skill cards


class TestSkillLoader:
    def test_missing_card_returns_empty(self) -> None:
        card = load_skill("_does_not_exist_abcxyz")
        assert isinstance(card, SkillCard)
        assert card.prompt == ""

    def test_claim_graph_card_parses(self) -> None:
        card = load_skill("claim_graph_extractor")
        assert card.prompt, "claim_graph_extractor.md should have a Prompt section"
        rendered = card.render(claims="c", evidence="e", max_triples=5)
        assert "c" in rendered
        assert "e" in rendered

    def test_peer_reviewer_card_has_sections(self) -> None:
        card = load_skill("peer_reviewer")
        assert card.when_to_use
        assert card.output_schema
        assert card.prompt


# ------------------------------------------------------------ schemas


class TestSchemas:
    def test_annotation_to_dict_roundtrip(self) -> None:
        ann = Annotation(
            kind="comment",
            target_id="sec_intro",
            comment="clarify the objective",
            severity="major",
            reviewer_id="reviewer_2",
            confidence=0.8,
        )
        data = ann.to_dict()
        assert data["kind"] == "comment"
        assert data["severity"] == "major"
        assert data["annotation_id"].startswith("ann_")

    def test_triple_requires_relation(self) -> None:
        triple = Triple(
            subject_id="cl_1",
            relation="supports",
            object_id="cl_2",
            evidence_ids=["ev_1"],
        )
        assert triple.relation == "supports"
        assert triple.evidence_ids == ["ev_1"]

    def test_persona_prompt_fragment(self) -> None:
        persona = ReviewerPersona3D(
            name="Dr. Rigor",
            commitment=0.9,
            intention=0.85,
            knowledgeability=0.85,
            focus_areas=["methods"],
        )
        fragment = persona.prompt_fragment()
        assert "Dr. Rigor" in fragment
        assert "meticulous" in fragment  # commitment band = >=0.67

    def test_tool_call_envelope(self) -> None:
        call = ToolCall(tool_name="literature.search",
                        arguments={"query": "x"})
        assert call.to_dict()["tool_name"] == "literature.search"


# ------------------------------------------------------------ rollout


class TestRolloutAndAggregate:
    def test_picks_highest_scoring(self) -> None:
        results = [
            AgentResult(ok=True, data={"score": 0.3}),
            AgentResult(ok=True, data={"score": 0.9}),
            AgentResult(ok=True, data={"score": 0.5}),
        ]
        calls = iter(results)
        winner = rollout_and_aggregate(lambda: next(calls), n=3)
        assert winner.ok
        assert winner.data == {"score": 0.9}
        assert len(winner.rollouts) == 3
        assert winner.rollouts[0]["rank"] == 0

    def test_skips_failed_rollouts(self) -> None:
        results = [
            AgentResult(ok=False, error="boom"),
            AgentResult(ok=True, data={"score": 0.7}),
        ]
        calls = iter(results)
        winner = rollout_and_aggregate(lambda: next(calls), n=2)
        assert winner.ok
        assert winner.data == {"score": 0.7}

    def test_all_failed(self) -> None:
        fail = AgentResult(ok=False, error="boom")
        winner = rollout_and_aggregate(lambda: fail, n=2)
        assert not winner.ok

    def test_custom_rubric(self) -> None:
        results = [
            AgentResult(ok=True, data={"a": 1}),
            AgentResult(ok=True, data={"a": 5}),
        ]
        calls = iter(results)
        winner = rollout_and_aggregate(
            lambda: next(calls),
            n=2,
            rubric=lambda r: float(r.data["a"]),
        )
        assert winner.data == {"a": 5}
