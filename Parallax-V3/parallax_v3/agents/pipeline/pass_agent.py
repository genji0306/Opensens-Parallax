"""Pass agent."""

from __future__ import annotations

from ._shared import PipelineAgent


class PassAgent(PipelineAgent):
    prompt_name = "refinement"


