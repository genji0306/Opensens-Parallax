"""Typed tool registry."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import TypedTool
from ..errors import ParallaxV3Error


class DuplicateToolError(ParallaxV3Error):
    """Raised when a tool is registered twice."""


class ToolNotFoundError(ParallaxV3Error):
    """Raised when a tool cannot be found."""


@dataclass
class ToolRegistry:
    _tools: dict[str, TypedTool] = field(default_factory=dict)

    def register(self, tool: TypedTool) -> TypedTool:
        if tool.name in self._tools:
            raise DuplicateToolError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool
        return tool

    def get(self, name: str) -> TypedTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(f"Tool not found: {name}") from exc

    def all_registered(self) -> list[TypedTool]:
        return [self._tools[name] for name in sorted(self._tools)]


