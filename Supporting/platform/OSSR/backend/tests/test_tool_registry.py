"""
Tests for the ToolUniverse-style tool registry and the compact-mode
discover/describe/call interface.
"""

from __future__ import annotations

import pytest

from app.services.tools.tool_registry import (
    ToolInvocationError,
    ToolRegistry,
    default_registry,
)


@pytest.fixture()
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(
        name="echo",
        description="echo back the provided text",
        handler=lambda args: {"echoed": args.get("text", "")},
        parameters={"text": {"type": "string"}},
        category="util",
        tags=["debug", "testing"],
        required=["text"],
    )
    reg.register(
        name="math.add",
        description="add two numbers a and b",
        handler=lambda args: {"sum": args["a"] + args["b"]},
        category="math",
        required=["a", "b"],
    )
    return reg


class TestRegistration:
    def test_contains_and_len(self, registry: ToolRegistry) -> None:
        assert "echo" in registry
        assert len(registry) == 2

    def test_unregister(self, registry: ToolRegistry) -> None:
        registry.unregister("echo")
        assert "echo" not in registry


class TestDiscoverAndDescribe:
    def test_discover_by_keyword(self, registry: ToolRegistry) -> None:
        results = registry.discover_tools("add numbers", top_k=5)
        names = [r["name"] for r in results]
        assert "math.add" in names

    def test_discover_by_tag(self, registry: ToolRegistry) -> None:
        results = registry.discover_tools("debug", top_k=5)
        assert any(r["name"] == "echo" for r in results)

    def test_discover_empty_query_returns_all(self, registry: ToolRegistry) -> None:
        results = registry.discover_tools("", top_k=10)
        assert len(results) == 2

    def test_discover_by_category(self, registry: ToolRegistry) -> None:
        results = registry.discover_tools("", top_k=10, category="math")
        assert len(results) == 1
        assert results[0]["name"] == "math.add"

    def test_describe_tool(self, registry: ToolRegistry) -> None:
        spec = registry.describe_tool("echo")
        assert spec is not None
        assert spec["name"] == "echo"
        assert "text" in spec["parameters"]

    def test_describe_unknown_returns_none(self, registry: ToolRegistry) -> None:
        assert registry.describe_tool("ghost") is None


class TestCallTool:
    def test_successful_call(self, registry: ToolRegistry) -> None:
        call = registry.call_tool("echo", {"text": "hello"})
        assert call.error is None
        assert call.result == {"echoed": "hello"}
        assert call.duration_ms >= 0

    def test_unknown_tool_sets_error(self, registry: ToolRegistry) -> None:
        call = registry.call_tool("ghost")
        assert call.error and "unknown_tool" in call.error

    def test_missing_required_argument(self, registry: ToolRegistry) -> None:
        call = registry.call_tool("math.add", {"a": 1})
        assert call.error and "missing required" in call.error

    def test_handler_raises_captured(self, registry: ToolRegistry) -> None:
        registry.register(
            name="boom",
            description="always raises",
            handler=lambda _: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        call = registry.call_tool("boom", {})
        assert call.error and "boom" in call.error

    def test_history_records_calls(self, registry: ToolRegistry) -> None:
        registry.call_tool("echo", {"text": "one"})
        registry.call_tool("echo", {"text": "two"})
        history = registry.history()
        assert len(history) == 2
        assert history[-1]["arguments"]["text"] == "two"


class TestDefaultRegistryBootstrap:
    def test_literature_tools_present(self) -> None:
        reg = default_registry()
        assert "literature.search" in reg
        assert "literature.lookup" in reg
        assert "literature.classify" in reg

    def test_classify_heuristic_works(self) -> None:
        reg = default_registry()
        call = reg.call_tool(
            "literature.classify",
            {"text": "We train a transformer with attention for benchmark accuracy."},
        )
        assert call.error is None
        assert call.result["ok"]
        assert "ml" in call.result["domains"]
