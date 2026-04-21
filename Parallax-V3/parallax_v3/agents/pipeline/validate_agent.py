"""Validate agent."""

from __future__ import annotations

from ._shared import PipelineAgent


class ValidateAgent(PipelineAgent):
    prompt_name = "refinement"


