"""Methods writer."""

from __future__ import annotations

from ....contracts import Phase, ScopeKey
from .._shared import OrchestraAgent


class MethodsWriter(OrchestraAgent):
    scope = ScopeKey.SECTION_METHODS
    phase = Phase.ACT
    prompt_name = "section_writing"

