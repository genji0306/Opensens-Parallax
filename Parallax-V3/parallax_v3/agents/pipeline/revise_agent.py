"""Revise agent."""

from __future__ import annotations

from ._shared import PipelineAgent


class ReviseAgent(PipelineAgent):
    prompt_name = "refinement"


