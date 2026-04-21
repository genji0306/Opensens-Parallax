"""Section integrator."""

from __future__ import annotations

from ...contracts import Phase, ScopeKey
from ._shared import OrchestraAgent


class Integrator(OrchestraAgent):
    scope = ScopeKey.FULL_PIPELINE
    phase = Phase.ACT
    prompt_name = "section_writing"

