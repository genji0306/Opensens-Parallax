"""Outline agent."""

from __future__ import annotations

from ...contracts import Phase, ScopeKey
from ._shared import OrchestraAgent


class OutlineAgent(OrchestraAgent):
    scope = ScopeKey.OUTLINE
    phase = Phase.PLAN
    prompt_name = "outline"

