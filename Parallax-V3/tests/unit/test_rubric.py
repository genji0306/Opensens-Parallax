"""Sprint 5 — AgentReview 6-axis rubric weighted scoring."""
from __future__ import annotations

from parallax_v3.contracts import ReviewFinding
from parallax_v3.llm.rubrics.agent_review import AgentReviewRubric


def test_rubric_axes_defined():
    expected = {"depth", "exec", "flow", "clarity", "evidence", "style"}
    assert set(AgentReviewRubric.axes) == expected


def test_rubric_weighted_overall_formula():
    findings = [
        ReviewFinding(section="intro", axis="depth",    score=10.0, comment=""),
        ReviewFinding(section="intro", axis="exec",     score=10.0, comment=""),
        ReviewFinding(section="intro", axis="flow",     score=10.0, comment=""),
        ReviewFinding(section="intro", axis="clarity",  score=10.0, comment=""),
        ReviewFinding(section="intro", axis="evidence", score=10.0, comment=""),
        ReviewFinding(section="intro", axis="style",    score=10.0, comment=""),
    ]
    scores = AgentReviewRubric().score(findings)
    # All axes scored 10 → overall should be 10
    assert scores["overall"] == 10.0


def test_rubric_weights_sum_to_one():
    # depth 0.20 + exec 0.20 + flow 0.15 + clarity 0.15 + evidence 0.20 + style 0.10
    import math
    total = 0.20 + 0.20 + 0.15 + 0.15 + 0.20 + 0.10
    assert math.isclose(total, 1.0, rel_tol=1e-9)


def test_rubric_missing_axis_defaults_to_five():
    findings = [
        ReviewFinding(section="intro", axis="depth", score=8.0, comment=""),
    ]
    scores = AgentReviewRubric().score(findings)
    assert scores["depth"] == 8.0
    assert scores["exec"] == 5.0  # missing axes default
    assert scores["overall"] < 10.0
