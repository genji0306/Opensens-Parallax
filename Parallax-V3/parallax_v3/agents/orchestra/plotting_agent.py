"""Plotting agent."""

from __future__ import annotations

from ...contracts import Phase, ScopeKey
from ._shared import OrchestraAgent


class PlottingAgent(OrchestraAgent):
    scope = ScopeKey.FULL_PIPELINE
    phase = Phase.ACT
    prompt_name = "plotting"

