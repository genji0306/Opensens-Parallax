"""Unit tests for the tool registry."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from parallax_v3.contracts import Phase, RiskLevel, TypedTool
from parallax_v3.tools.registry import DuplicateToolError, ToolNotFoundError, ToolRegistry


class _In(BaseModel):
    x: int


class _Out(BaseModel):
    y: int


def _make_tool(name: str, phase: Phase = Phase.EXPLORE) -> TypedTool:
    return TypedTool(
        name=name,
        input_schema=_In,
        output_schema=_Out,
        risk_level=RiskLevel.SAFE_AUTO,
        phase_unlock=phase,
    )


def test_register_get_and_sort():
    registry = ToolRegistry()
    tool_a = _make_tool("alpha")
    tool_b = _make_tool("beta", Phase.PLAN)

    registry.register(tool_b)
    registry.register(tool_a)

    assert registry.get("alpha") is tool_a
    assert [tool.name for tool in registry.all_registered()] == ["alpha", "beta"]


def test_duplicate_and_missing():
    registry = ToolRegistry()
    registry.register(_make_tool("dup"))

    with pytest.raises(DuplicateToolError):
        registry.register(_make_tool("dup"))

    with pytest.raises(ToolNotFoundError):
        registry.get("missing")

