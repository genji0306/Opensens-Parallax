"""
Tests for the AgentReview 5-phase pipeline additions to BoardManager and
the LLM-Peer annotation projection. These tests stub out the underlying
LLM calls so they run offline.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.models.review_models import (
    ReviewComment,
    ReviewerResult,
    RevisionRound,
)
from app.services._agents.schema import ReviewerPersona3D
from app.services.review.board_manager import BoardManager
from app.services.review.conflict_detector import ConflictDetector


@pytest.fixture()
def board() -> BoardManager:
    return BoardManager()


def _fake_round() -> RevisionRound:
    results = [
        ReviewerResult(
            reviewer_type="methodologist",
            reviewer_name="Dr. Method",
            overall_score=7.0,
            summary="Solid",
            comments=[
                ReviewComment(
                    reviewer_type="methodologist",
                    section="Methods",
                    text="Clarify sample size",
                    severity="major",
                    confidence=0.8,
                    impact="high",
                    category="rigor",
                    quote="we collected data",
                ),
            ],
        ),
        ReviewerResult(
            reviewer_type="reviewer_2",
            reviewer_name="Reviewer 2",
            overall_score=5.5,
            summary="Borderline",
            comments=[
                ReviewComment(
                    reviewer_type="reviewer_2",
                    section="Results",
                    text="Missing baseline comparison",
                    severity="critical",
                    confidence=0.9,
                    impact="high",
                    category="rigor",
                ),
            ],
        ),
        ReviewerResult(
            reviewer_type="novelty_hunter",
            reviewer_name="Novelty",
            overall_score=8.5,
            summary="Very novel",
            comments=[],
        ),
    ]
    return RevisionRound(
        run_id="run_test",
        round_number=1,
        rewrite_mode="conservative",
        reviewer_types=["methodologist", "reviewer_2", "novelty_hunter"],
        results=results,
        avg_score=7.0,
    )


class TestPersona3D:
    def test_default_axes(self, board: BoardManager) -> None:
        persona = board.build_persona_3d("methodologist", strictness=0.8)
        assert isinstance(persona, ReviewerPersona3D)
        assert 0.0 <= persona.commitment <= 1.0
        assert persona.strictness == 0.8

    def test_override(self, board: BoardManager) -> None:
        persona = board.build_persona_3d(
            "methodologist",
            strictness=0.5,
            overrides={"knowledgeability": 0.2},
        )
        assert persona.knowledgeability == 0.2

    def test_prompt_fragment_mentions_focus(self, board: BoardManager) -> None:
        persona = board.build_persona_3d("editor")
        fragment = persona.prompt_fragment()
        assert persona.name in fragment


class TestAnnotationProjection:
    def test_comments_to_annotations(self, board: BoardManager) -> None:
        round_obj = _fake_round()
        first = round_obj.results[0]
        anns = board.comments_to_annotations(first, target_id="draft")
        assert len(anns) == 1
        ann = anns[0]
        assert ann["kind"] == "comment"
        assert ann["severity"] == "major"
        assert ann["reviewer_id"] == "methodologist"
        assert ann["target_id"] == "Methods"


class TestFivePhasePipeline:
    def test_meta_score_and_decision(self, board: BoardManager) -> None:
        round_obj = _fake_round()

        # Stub out run_review_round so it returns our prebaked round without
        # touching the DB or calling LLMs.
        with patch.object(board, "run_review_round", return_value=round_obj), \
             patch.object(
                 ConflictDetector,
                 "detect_conflicts",
                 return_value={"conflicts": [], "themes": [], "bias": {}, "stats": {}},
             ):
            result = board.run_5phase_review_round(
                run_id="run_test",
                content="draft text",
                reviewer_types=["methodologist", "reviewer_2", "novelty_hunter"],
                strictness=0.7,
            )

        phases = result["phases"]
        assert set(phases.keys()) == {"independent", "rebuttal", "discussion", "meta", "decision"}
        meta_score = phases["meta"]["meta_score"]
        assert 5.0 <= meta_score <= 9.0
        decision = phases["decision"]["verdict"]
        assert decision in (
            "accept", "weak_accept", "borderline", "weak_reject", "reject",
        )
        assert "personas" in phases["independent"]

    def test_authority_bias_detected(self, board: BoardManager) -> None:
        # Build a round where novelty_hunter is far above the mean —
        # should trigger authority bias flag.
        round_obj = _fake_round()
        with patch.object(board, "run_review_round", return_value=round_obj), \
             patch.object(
                 ConflictDetector,
                 "detect_conflicts",
                 return_value={"conflicts": [], "themes": [], "bias": {}, "stats": {}},
             ):
            result = board.run_5phase_review_round(
                run_id="run_test",
                content="draft text",
            )
        # Mean of [7.0, 5.5, 8.5] = 7.0; novelty_hunter is +1.5 → flag
        assert result["phases"]["discussion"]["authority_bias"] is True


class TestConflictDetectorBias:
    def test_groupthink_flag(self) -> None:
        detector = ConflictDetector()
        round_obj = _fake_round()
        for r in round_obj.results:
            r.overall_score = 6.5  # tight cluster
        # Stub out the LLM call path by monkey-patching _get_llm to raise,
        # so detect_conflicts falls through to the bias heuristic only.
        with patch.object(detector, "_get_llm", side_effect=RuntimeError("no llm")):
            result = detector.detect_conflicts(round_obj)
        assert result["bias"]["groupthink"] is True
        assert result["bias"]["authority"] is False
