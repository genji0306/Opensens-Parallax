"""Sprint 5 — Refinement halt-rule state machine."""
from __future__ import annotations

from parallax_v3.contracts import RefinementState
from parallax_v3.llm.rubrics.halt_rules import evaluate_halt


def _state(iteration: int = 1, plateau_count: int = 0) -> RefinementState:
    return RefinementState(
        iteration=iteration,
        scores=[5.0] * 6,
        prev_scores=[5.0] * 6,
        plateau_count=plateau_count,
        verdict="accept",
    )


def test_accept_on_overall_increase():
    state = _state()
    result = evaluate_halt(state, overall_new=7.5, overall_prev=7.0, net_subaxis_delta=0.0)
    assert result.verdict == "accept"
    assert result.plateau_count == 0


def test_accept_on_tie_with_nonneg_subaxis_delta():
    state = _state()
    result = evaluate_halt(state, overall_new=7.0, overall_prev=7.0, net_subaxis_delta=0.5)
    assert result.verdict == "accept"


def test_revert_on_overall_decrease():
    state = _state()
    result = evaluate_halt(state, overall_new=6.0, overall_prev=7.5, net_subaxis_delta=0.0,
                            plateau_threshold=0.1)
    assert result.verdict == "revert"


def test_halt_plateau_after_window():
    state = _state(plateau_count=1)
    result = evaluate_halt(
        state,
        overall_new=7.0,
        overall_prev=7.4,   # small decrease within plateau threshold
        net_subaxis_delta=-0.1,
        plateau_threshold=1.0,
        plateau_window=2,
    )
    assert result.verdict == "halt_plateau"


def test_halt_cap():
    state = _state(iteration=3)
    result = evaluate_halt(
        state,
        overall_new=8.0,
        overall_prev=7.5,
        net_subaxis_delta=0.1,
        iter_cap=3,
    )
    assert result.verdict == "halt_cap"
