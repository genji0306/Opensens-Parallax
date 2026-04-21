"""Discussion writer."""

from __future__ import annotations

from ....contracts import Phase, ScopeKey
from .._shared import OrchestraAgent


class DiscussionWriter(OrchestraAgent):
    scope = ScopeKey.SECTION_DISCUSS
    phase = Phase.ACT
    prompt_name = "section_writing"

