"""Sprint 3 — ProgressiveToolset (Pattern #9: Progressive Tool Expansion)."""
from __future__ import annotations

from parallax_v3.contracts import Phase, RiskLevel, TypedTool
from parallax_v3.tools.progressive import ProgressiveToolset
from parallax_v3.tools.registry import ToolRegistry


def _tool(name: str, phase: Phase) -> TypedTool:
    return TypedTool(
        name=name,
        input_schema=dict,
        output_schema=dict,
        risk_level=RiskLevel.SAFE_AUTO,
        phase_unlock=phase,
    )


def _populated_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(_tool("read", Phase.EXPLORE))
    reg.register(_tool("grep", Phase.EXPLORE))
    reg.register(_tool("figure_render", Phase.PLAN))
    reg.register(_tool("write", Phase.ACT))
    reg.register(_tool("latex_compile", Phase.ACT))
    return reg


def test_explore_unlocks_explore_only():
    ts = ProgressiveToolset()
    ts.unlock(Phase.EXPLORE, _populated_registry())
    names = [t.name for t in ts.available()]
    assert "read" in names
    assert "grep" in names
    assert "write" not in names
    assert "latex_compile" not in names


def test_plan_unlocks_additive():
    ts = ProgressiveToolset()
    reg = _populated_registry()
    ts.unlock(Phase.EXPLORE, reg)
    ts.unlock(Phase.PLAN, reg)
    names = [t.name for t in ts.available()]
    assert {"read", "grep", "figure_render"}.issubset(set(names))
    assert "write" not in names


def test_act_unlocks_all():
    ts = ProgressiveToolset()
    reg = _populated_registry()
    ts.unlock(Phase.EXPLORE, reg)
    ts.unlock(Phase.PLAN, reg)
    ts.unlock(Phase.ACT, reg)
    names = [t.name for t in ts.available()]
    assert {"read", "grep", "figure_render", "write", "latex_compile"}.issubset(set(names))


def test_unlock_idempotent():
    ts = ProgressiveToolset()
    reg = _populated_registry()
    ts.unlock(Phase.EXPLORE, reg)
    count_first = len(ts.available())
    ts.unlock(Phase.EXPLORE, reg)  # duplicate unlock should be no-op
    assert len(ts.available()) == count_first
