"""Debate agent."""

from __future__ import annotations

from ._shared import PipelineAgent


class DebateAgent(PipelineAgent):
    prompt_name = "litreview"


