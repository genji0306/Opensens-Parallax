"""Draft agent."""

from __future__ import annotations

from ._shared import PipelineAgent


class DraftAgent(PipelineAgent):
    prompt_name = "section_writing"


