"""Phase-based tool gate."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts import Phase, TypedTool
from ..errors import ParallaxV3Error


class PhaseViolationError(ParallaxV3Error):
    def __init__(self, tool_name: str, required_phase: Phase, current_phase: Phase):
        self.tool_name = tool_name
        self.required_phase = required_phase
        self.current_phase = current_phase
        super().__init__(
            f"Tool '{tool_name}' requires phase {required_phase.name}, current phase is {current_phase.name}"
        )


@dataclass(frozen=True)
class PhaseGuard:
    current_phase: Phase

    def guard(self, tool: TypedTool) -> TypedTool:
        if tool.phase_unlock.value > self.current_phase.value:
            raise PhaseViolationError(tool.name, tool.phase_unlock, self.current_phase)
        return tool


