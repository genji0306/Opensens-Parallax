"""Sprint 5 — PaperOrchestra pipeline smoke test.

Verifies the pipeline DAG instantiates correctly and all 9 agents are wired.
Does NOT make LLM calls — just exercises the topology.
"""
from __future__ import annotations

from parallax_v3.agents.orchestra.integrator import Integrator
from parallax_v3.agents.orchestra.litreview_agent import LitReviewAgent
from parallax_v3.agents.orchestra.outline_agent import OutlineAgent
from parallax_v3.agents.orchestra.plotting_agent import PlottingAgent
from parallax_v3.agents.orchestra.refinement_agent import RefinementAgent
from parallax_v3.agents.orchestra.section_writers.discussion import DiscussionWriter
from parallax_v3.agents.orchestra.section_writers.introduction import IntroductionWriter
from parallax_v3.agents.orchestra.section_writers.methods import MethodsWriter
from parallax_v3.agents.orchestra.section_writers.results import ResultsWriter
from parallax_v3.contracts import Phase, ScopeKey
from parallax_v3.pipelines.paper_orchestra import PaperOrchestraPipeline


def test_pipeline_wires_nine_agents():
    pipeline = PaperOrchestraPipeline()
    assert len(pipeline.agents) == 9


def test_pipeline_agent_order_matches_paperorchestra():
    pipeline = PaperOrchestraPipeline()
    expected_types = (
        OutlineAgent,
        PlottingAgent,
        LitReviewAgent,
        IntroductionWriter,
        MethodsWriter,
        ResultsWriter,
        DiscussionWriter,
        Integrator,
        RefinementAgent,
    )
    for agent, expected in zip(pipeline.agents, expected_types):
        assert isinstance(agent, expected), f"Wrong agent at position: {type(agent)}"


def test_section_writers_have_section_scopes():
    assert IntroductionWriter().scope == ScopeKey.SECTION_INTRO
    assert MethodsWriter().scope == ScopeKey.SECTION_METHODS
    assert ResultsWriter().scope == ScopeKey.SECTION_RESULTS
    assert DiscussionWriter().scope == ScopeKey.SECTION_DISCUSS


def test_outline_agent_is_plan_phase():
    """Outline runs before heavy act-phase work."""
    assert OutlineAgent().phase == Phase.PLAN


def test_agents_expose_allowed_tools_list():
    """All orchestra agents declare a non-empty allowed_tools list."""
    for agent_cls in (
        OutlineAgent, PlottingAgent, LitReviewAgent,
        IntroductionWriter, MethodsWriter, ResultsWriter, DiscussionWriter,
        Integrator, RefinementAgent,
    ):
        agent = agent_cls()
        assert isinstance(agent.allowed_tools, list)
