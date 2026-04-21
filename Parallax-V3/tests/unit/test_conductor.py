"""Sprint 4/7 — Conductor: session lifecycle, phase transitions, refinement loop."""
from __future__ import annotations

import pytest
import pytest_asyncio

from parallax_v3.contracts import Phase
from parallax_v3.runtime.conductor import Conductor


class _FakeRequest:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def conductor():
    return Conductor()


@pytest_asyncio.fixture
async def session_with_run(conductor):
    session = await conductor.create_session(_FakeRequest(
        research_question="Test research question for conductor",
        target_venue="neurips",
        citation_style="nature",
        budget_usd=10.0,
        max_refinement_iters=3,
    ))
    run = await conductor.run_pipeline(_FakeRequest(
        session_id=session["session_id"],
        pipeline="paper_orchestra",
    ))
    return session, run


@pytest.mark.asyncio
async def test_create_session_returns_session_id(conductor):
    result = await conductor.create_session(_FakeRequest(
        research_question="Does sparse attention improve summarisation?",
        target_venue="neurips",
        citation_style="nature",
        budget_usd=10.0,
        max_refinement_iters=3,
    ))
    assert "session_id" in result
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_get_session_roundtrip(conductor):
    created = await conductor.create_session(_FakeRequest(
        research_question="Round trip test research question for conductor",
        target_venue="icml",
        citation_style="apa",
        budget_usd=5.0,
        max_refinement_iters=2,
    ))
    fetched = await conductor.get_session(created["session_id"])
    assert fetched["session_id"] == created["session_id"]


@pytest.mark.asyncio
async def test_run_pipeline_creates_run_record(conductor):
    session = await conductor.create_session(_FakeRequest(
        research_question="Pipeline test research question for conductor",
        target_venue="neurips",
        citation_style="ieee",
        budget_usd=8.0,
        max_refinement_iters=3,
    ))
    run = await conductor.run_pipeline(_FakeRequest(
        session_id=session["session_id"],
        pipeline="paper_orchestra",
    ))
    assert run["status"] == "queued"
    assert "run_id" in run


@pytest.mark.asyncio
async def test_phase_transition_advances_forward(session_with_run, conductor):
    _, run = session_with_run
    # Start at EXPLORE (default)
    new_phase = conductor.transition_phase(run["run_id"], Phase.PLAN)
    assert new_phase.value >= Phase.PLAN.value


@pytest.mark.asyncio
async def test_phase_transition_requires_plan_before_act(session_with_run, conductor):
    _, run = session_with_run
    result = conductor.transition_phase(run["run_id"], Phase.ACT)
    assert result == Phase.PLAN


@pytest.mark.asyncio
async def test_phase_transition_cannot_go_backwards(session_with_run, conductor):
    _, run = session_with_run
    conductor.transition_phase(run["run_id"], Phase.PLAN)
    conductor.transition_phase(run["run_id"], Phase.ACT)
    # Trying to go back to EXPLORE should be no-op
    result = conductor.transition_phase(run["run_id"], Phase.EXPLORE)
    assert result.value >= Phase.ACT.value


@pytest.mark.asyncio
async def test_refinement_loop_accept_on_improvement(session_with_run, conductor):
    _, run = session_with_run
    conductor.init_refinement(run["run_id"])
    state = conductor.advance_refinement(run["run_id"], [7.0, 7.0, 7.0, 7.0, 7.0, 7.0])
    assert state.verdict == "accept"


@pytest.mark.asyncio
async def test_refinement_loop_halt_cap(session_with_run, conductor):
    _, run = session_with_run
    conductor.init_refinement(run["run_id"])
    # Advance 3 iterations (matching max_refinement_iters=3)
    for i in range(3):
        state = conductor.advance_refinement(
            run["run_id"],
            [6.0 + i * 0.5] * 6,
        )
    assert state.verdict == "halt_cap"


@pytest.mark.asyncio
async def test_stream_events_yields_heartbeat(session_with_run, conductor):
    _, run = session_with_run
    events = []
    async for event in conductor.stream_events(run["run_id"]):
        events.append(event)
    assert any(e["type"] == "heartbeat" for e in events)
