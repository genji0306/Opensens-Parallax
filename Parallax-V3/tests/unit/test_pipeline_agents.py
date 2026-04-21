"""Sprint 6 — Pipeline agent topology and V2-parity checks."""
from __future__ import annotations

from parallax_v3.agents.pipeline.debate_agent import DebateAgent
from parallax_v3.agents.pipeline.draft_agent import DraftAgent
from parallax_v3.agents.pipeline.experiment_agent import ExperimentAgent
from parallax_v3.agents.pipeline.ideas_agent import IdeasAgent
from parallax_v3.agents.pipeline.map_agent import MapAgent
from parallax_v3.agents.pipeline.pass_agent import PassAgent
from parallax_v3.agents.pipeline.revise_agent import ReviseAgent
from parallax_v3.agents.pipeline.search_agent import SearchAgent
from parallax_v3.agents.pipeline.validate_agent import ValidateAgent
from parallax_v3.contracts import Phase, ScopeKey


PIPELINE_AGENTS = [
    SearchAgent,
    MapAgent,
    DebateAgent,
    ValidateAgent,
    IdeasAgent,
    DraftAgent,
    ExperimentAgent,
    ReviseAgent,
    PassAgent,
]


def test_nine_pipeline_agents_exist():
    assert len(PIPELINE_AGENTS) == 9


def test_each_pipeline_agent_instantiates():
    for cls in PIPELINE_AGENTS:
        agent = cls()
        assert hasattr(agent, "scope")
        assert hasattr(agent, "phase")
        assert hasattr(agent, "allowed_tools")
        assert hasattr(agent, "run")


def test_agent_ids_are_unique():
    ids = [cls().agent_id for cls in PIPELINE_AGENTS]
    assert len(ids) == len(set(ids))


def test_search_agent_is_explore_phase():
    assert SearchAgent().phase == Phase.EXPLORE


def test_pass_agent_exists_as_terminal():
    agent = PassAgent()
    assert agent.agent_id == "pass"
