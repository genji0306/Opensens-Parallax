"""Sprint 3 — PhaseGuard (Pattern #6: Explore-Plan-Act)."""
from __future__ import annotations

import pytest

from parallax_v3.contracts import Phase, RiskLevel, TypedTool
from parallax_v3.runtime.phase_guard import PhaseGuard, PhaseViolationError


def _tool(name: str, phase: Phase) -> TypedTool:
    return TypedTool(
        name=name,
        input_schema=dict,
        output_schema=dict,
        risk_level=RiskLevel.SAFE_AUTO,
        phase_unlock=phase,
    )


def test_explore_phase_allows_explore_tools():
    guard = PhaseGuard(current_phase=Phase.EXPLORE)
    guarded = guard.guard(_tool("read", Phase.EXPLORE))
    assert guarded.name == "read"


def test_explore_phase_blocks_act_tools():
    guard = PhaseGuard(current_phase=Phase.EXPLORE)
    with pytest.raises(PhaseViolationError) as exc_info:
        guard.guard(_tool("write", Phase.ACT))
    assert exc_info.value.tool_name == "write"
    assert exc_info.value.required_phase == Phase.ACT
    assert exc_info.value.current_phase == Phase.EXPLORE


def test_act_phase_allows_all_lower_tiers():
    guard = PhaseGuard(current_phase=Phase.ACT)
    # All three phases should be allowed in ACT
    guard.guard(_tool("r", Phase.EXPLORE))
    guard.guard(_tool("p", Phase.PLAN))
    guard.guard(_tool("w", Phase.ACT))


def test_plan_phase_blocks_act_tools():
    guard = PhaseGuard(current_phase=Phase.PLAN)
    with pytest.raises(PhaseViolationError):
        guard.guard(_tool("latex_compile", Phase.ACT))


def test_phase_guard_is_frozen():
    guard = PhaseGuard(current_phase=Phase.EXPLORE)
    with pytest.raises((AttributeError, Exception)):
        guard.current_phase = Phase.ACT  # type: ignore[misc]
