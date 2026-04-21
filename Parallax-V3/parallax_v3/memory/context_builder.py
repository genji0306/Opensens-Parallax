"""Context bundle assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..contracts import ContextBundle, ScopeKey
from .stores.cold import ColdStore
from .stores.hot import HotStore


@dataclass
class ContextBuilder:
    scope: ScopeKey
    hot_store: HotStore | None = None
    warm_summaries: list[str] = field(default_factory=list)
    cold_store: ColdStore | None = None

    def build(self) -> ContextBundle:
        hot_items: list[str] = []
        if self.hot_store is not None:
            hot_items = [f"{key}={value}" for key, value in self.hot_store.items()]
        cold_paths: list[Path] = []
        if self.cold_store is not None:
            cold_paths = [Path(path) for path in self.cold_store.list_files("")]
        token_estimate = sum(len(item.split()) for item in hot_items + self.warm_summaries)
        return ContextBundle(
            scope=self.scope,
            hot_items=hot_items,
            warm_summaries=list(self.warm_summaries),
            cold_paths=cold_paths,
            token_estimate=token_estimate,
        )

