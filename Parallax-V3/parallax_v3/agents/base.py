"""Base agent contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from ..contracts import AgentResult, ContextBundle, Phase, ScopeKey, SessionManifest


class Agent(ABC):
    scope: ScopeKey
    allowed_tools: list[str]
    phase: Phase

    @abstractmethod
    async def run(self, ctx: ContextBundle, manifest: SessionManifest) -> AgentResult:
        raise NotImplementedError


