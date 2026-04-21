"""Lit review agent."""

from __future__ import annotations

from ...contracts import Phase, ScopeKey
from ._shared import OrchestraAgent


class LitReviewAgent(OrchestraAgent):
    scope = ScopeKey.CITE_CHECK
    phase = Phase.ACT
    prompt_name = "litreview"

