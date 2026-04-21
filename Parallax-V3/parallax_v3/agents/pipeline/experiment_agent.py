"""Experiment agent."""

from __future__ import annotations

from ._shared import PipelineAgent


class ExperimentAgent(PipelineAgent):
    prompt_name = "plotting"


