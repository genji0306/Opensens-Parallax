"""
Tests for P-3 Review Engine — models, revision history, revision tracker.
"""

import json
import pytest


class TestReviewModels:
    def test_review_comment_serialization(self, isolated_db):
        from app.models.review_models import ReviewComment
        c = ReviewComment(
            reviewer_type="methodological", section="Methods",
            text="Missing control group", severity="critical",
            confidence=0.9, impact="high", category="missing_control",
        )
        d = c.to_dict()
        assert d["comment_id"].startswith("rc_")
        assert d["severity"] == "critical"
        assert d["confidence"] == 0.9

        restored = ReviewComment.from_dict(d)
        assert restored.text == c.text

    def test_reviewer_result_serialization(self, isolated_db):
        from app.models.review_models import ReviewerResult, ReviewComment
        r = ReviewerResult(
            reviewer_type="novelty",
            reviewer_name="Novelty Reviewer",
            overall_score=7.5,
            summary="Good novelty",
            comments=[ReviewComment(text="Novel approach", severity="suggestion")],
            strengths=["Original idea"],
            weaknesses=["Weak baseline"],
        )
        d = r.to_dict()
        assert d["overall_score"] == 7.5
        assert len(d["comments"]) == 1
        assert len(d["strengths"]) == 1

    def test_revision_round_serialization(self, isolated_db):
        from app.models.review_models import RevisionRound, ReviewerResult
        rr = RevisionRound(
            run_id="test_run",
            round_number=1,
            rewrite_mode="conservative",
            reviewer_types=["methodological", "novelty"],
            results=[
                ReviewerResult(reviewer_type="methodological", overall_score=6.0),
                ReviewerResult(reviewer_type="novelty", overall_score=8.0),
            ],
            avg_score=7.0,
        )
        d = rr.to_dict()
        assert d["round_id"].startswith("rr_")
        assert d["round_number"] == 1
        assert len(d["results"]) == 2

        restored = RevisionRound.from_dict(d)
        assert restored.avg_score == 7.0
        assert len(restored.results) == 2

    def test_conflict_serialization(self, isolated_db):
        from app.models.review_models import ReviewConflict
        cf = ReviewConflict(
            reviewer_a="methodological", reviewer_b="novelty",
            description="Disagree on statistical approach",
            resolution_suggestion="Use both methods",
        )
        d = cf.to_dict()
        assert d["conflict_id"].startswith("cf_")

    def test_theme_serialization(self, isolated_db):
        from app.models.review_models import RevisionTheme
        th = RevisionTheme(
            title="Statistical Rigor", description="Improve stats",
            priority=1, impact="high",
            comment_ids=["rc_1", "rc_2"],
            suggested_action="Add ANOVA",
        )
        d = th.to_dict()
        assert d["theme_id"].startswith("th_")
        assert d["priority"] == 1


class TestRevisionHistoryDAO:
    def test_save_and_list(self, isolated_db):
        from app.models.review_models import RevisionRound, ReviewerResult, RevisionHistoryDAO

        rr1 = RevisionRound(
            run_id="run_a", round_number=1,
            results=[ReviewerResult(reviewer_type="novelty", overall_score=5.0)],
            avg_score=5.0,
        )
        rr2 = RevisionRound(
            run_id="run_a", round_number=2,
            results=[ReviewerResult(reviewer_type="novelty", overall_score=7.0)],
            avg_score=7.0,
        )
        RevisionHistoryDAO.save(rr1)
        RevisionHistoryDAO.save(rr2)

        rounds = RevisionHistoryDAO.list_by_run("run_a")
        assert len(rounds) == 2
        assert rounds[0].round_number == 1
        assert rounds[1].round_number == 2

    def test_latest(self, isolated_db):
        from app.models.review_models import RevisionRound, RevisionHistoryDAO

        RevisionHistoryDAO.save(RevisionRound(run_id="run_b", round_number=1, avg_score=4.0))
        RevisionHistoryDAO.save(RevisionRound(run_id="run_b", round_number=2, avg_score=6.0))
        RevisionHistoryDAO.save(RevisionRound(run_id="run_b", round_number=3, avg_score=8.0))

        latest = RevisionHistoryDAO.latest("run_b")
        assert latest is not None
        assert latest.round_number == 3
        assert latest.avg_score == 8.0

    def test_load_by_id(self, isolated_db):
        from app.models.review_models import RevisionRound, RevisionHistoryDAO

        rr = RevisionRound(run_id="run_c", round_number=1, avg_score=6.5)
        RevisionHistoryDAO.save(rr)

        loaded = RevisionHistoryDAO.load(rr.round_id)
        assert loaded is not None
        assert loaded.avg_score == 6.5

    def test_load_nonexistent(self, isolated_db):
        from app.models.review_models import RevisionHistoryDAO
        assert RevisionHistoryDAO.load("nonexistent") is None
        assert RevisionHistoryDAO.latest("nonexistent") is None


class TestRevisionTracker:
    def test_rewrite_modes(self, isolated_db):
        from app.services.review.revision_tracker import RevisionTracker
        modes = RevisionTracker().get_rewrite_modes()
        assert "conservative" in modes
        assert "novelty" in modes
        assert "clarity" in modes
        assert "journal" in modes

    def test_get_instruction(self, isolated_db):
        from app.services.review.revision_tracker import RevisionTracker
        instr = RevisionTracker().get_rewrite_instruction("novelty")
        assert "novelty" in instr.lower()

    def test_empty_history(self, isolated_db):
        from app.services.review.revision_tracker import RevisionTracker
        result = RevisionTracker().get_history("nonexistent")
        assert result["total_rounds"] == 0
        assert result["rounds"] == []

    def test_regression_detection(self, isolated_db):
        from app.models.review_models import RevisionRound, ReviewerResult, RevisionHistoryDAO
        from app.services.review.revision_tracker import RevisionTracker

        # Round 1: score 7
        RevisionHistoryDAO.save(RevisionRound(
            run_id="run_reg", round_number=1,
            results=[ReviewerResult(reviewer_type="novelty", reviewer_name="Novelty", overall_score=7.0)],
            avg_score=7.0,
        ))
        # Round 2: score drops to 4 (regression!)
        RevisionHistoryDAO.save(RevisionRound(
            run_id="run_reg", round_number=2,
            results=[ReviewerResult(reviewer_type="novelty", reviewer_name="Novelty", overall_score=4.0)],
            avg_score=4.0,
        ))

        result = RevisionTracker().get_history("run_reg")
        assert result["total_rounds"] == 2
        assert result["improving"] is False
        assert len(result["regression_warnings"]) >= 1
        assert result["regression_warnings"][0]["metric"] == "avg_score"

    def test_improving_trajectory(self, isolated_db):
        from app.models.review_models import RevisionRound, RevisionHistoryDAO
        from app.services.review.revision_tracker import RevisionTracker

        RevisionHistoryDAO.save(RevisionRound(run_id="run_imp", round_number=1, avg_score=5.0))
        RevisionHistoryDAO.save(RevisionRound(run_id="run_imp", round_number=2, avg_score=7.0))

        result = RevisionTracker().get_history("run_imp")
        assert result["improving"] is True
        assert result["latest_score"] == 7.0
        assert len(result["score_trajectory"]) == 2


class TestReviewerArchetypes:
    def test_all_archetypes_defined(self, isolated_db):
        from app.models.review_models import REVIEWER_ARCHETYPES
        expected = {"methodological", "novelty", "domain", "statistician", "harsh_editor"}
        assert set(REVIEWER_ARCHETYPES.keys()) == expected

    def test_archetypes_have_required_fields(self, isolated_db):
        from app.models.review_models import REVIEWER_ARCHETYPES
        for key, arch in REVIEWER_ARCHETYPES.items():
            assert "name" in arch, f"{key} missing name"
            assert "focus" in arch, f"{key} missing focus"
            assert "persona" in arch, f"{key} missing persona"
            assert "rubric" in arch, f"{key} missing rubric"
            assert len(arch["rubric"]) >= 3, f"{key} rubric too short"
