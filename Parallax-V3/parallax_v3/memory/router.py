"""Tiered memory router."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .stores.cold import ColdStore
from .stores.hot import HotStore


@dataclass
class MemoryRouter:
    hot: HotStore = field(default_factory=HotStore)
    warm: Any = None
    cold: ColdStore | None = None

    def put(self, key: str, value: Any, tier: str = "hot") -> None:
        if tier == "cold" and self.cold is not None:
            self.cold.write(key, str(value))
            return
        self.hot.set(key, value)

    def get(self, key: str, default: Any = None) -> Any:
        value = self.hot.get(key, default)
        if value is not default:
            return value
        return default

    def delete(self, key: str) -> None:
        self.hot.delete(key)

