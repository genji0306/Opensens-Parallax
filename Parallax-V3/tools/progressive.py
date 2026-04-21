"""Phase-based progressive tool expansion."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts import Phase, TypedTool
from .registry import ToolRegistry


@dataclass
class ProgressiveToolset:
    _unlocked_names: set[str] = field(default_factory=set)
    _highest_phase: Phase = field(default=Phase.EXPLORE)
    _has_phase: bool = field(default=False, init=False, repr=False)

    def unlock(self, phase: Phase, registry: ToolRegistry) -> None:
        if self._has_phase and phase.value <= self._highest_phase.value:
            return
        for tool in registry.all_registered():
            if tool.phase_unlock == phase:
                self._unlocked_names.add(tool.name)
        if not self._has_phase or phase.value > self._highest_phase.value:
            self._highest_phase = phase
            self._has_phase = True

    def available(self, registry: ToolRegistry | None = None) -> list[TypedTool]:
        if registry is None:
            return []
        return [tool for tool in registry.all_registered() if tool.name in self._unlocked_names]


