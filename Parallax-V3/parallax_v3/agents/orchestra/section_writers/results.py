"""Results writer."""

from __future__ import annotations

from ....contracts import Phase, ScopeKey
from .._shared import OrchestraAgent


class ResultsWriter(OrchestraAgent):
    scope = ScopeKey.SECTION_RESULTS
    phase = Phase.ACT
    prompt_name = "section_writing"

