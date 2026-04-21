"""Introduction writer."""

from __future__ import annotations

from ....contracts import Phase, ScopeKey
from .._shared import OrchestraAgent


class IntroductionWriter(OrchestraAgent):
    scope = ScopeKey.SECTION_INTRO
    phase = Phase.ACT
    prompt_name = "section_writing"

