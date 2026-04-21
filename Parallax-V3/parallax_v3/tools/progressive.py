"""Phase-based progressive tool expansion."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import Phase, TypedTool
from .registry import ToolRegistry


@dataclass
class ProgressiveToolset:
    _unlocked_tools: dict[str, TypedTool] = field(default_factory=dict)
    _highest_phase: Phase = field(default=Phase.EXPLORE)
    _has_phase: bool = field(default=False, init=False, repr=False)

    def unlock(self, phase: Phase, registry: ToolRegistry) -> None:
        if self._has_phase and phase.value <= self._highest_phase.value:
            return
        for tool in registry.all_registered():
            if tool.phase_unlock == phase:
                self._unlocked_tools[tool.name] = tool
        if not self._has_phase or phase.value > self._highest_phase.value:
            self._highest_phase = phase
            self._has_phase = True

    def available(self) -> list[TypedTool]:
        return [self._unlocked_tools[name] for name in sorted(self._unlocked_tools)]
