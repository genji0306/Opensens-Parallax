"""Refinement agent."""

from __future__ import annotations

from ...contracts import Phase, ScopeKey
from ._shared import OrchestraAgent


class RefinementAgent(OrchestraAgent):
    scope = ScopeKey.REVIEW
    phase = Phase.ACT
    prompt_name = "refinement"

