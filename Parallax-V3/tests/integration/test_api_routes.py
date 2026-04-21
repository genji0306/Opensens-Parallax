"""Sprint 7 — API route smoke tests.

Exercises the FastAPI scaffold end-to-end against the in-memory Conductor.
Does NOT run LLMs — verifies the route shapes and envelope contract.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from parallax_v3.api.routes import conductor, router


async def _collect_events(run_id: str) -> list[dict]:
    events = []
    async for event in conductor.stream_events(run_id):
        events.append(event)
    return events


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_create_session_returns_envelope(client):
    response = client.post("/api/v3/sessions", json={
        "research_question": "Does sparse attention improve summarisation vs cost?",
        "target_venue": "neurips",
        "citation_style": "nature",
        "budget_usd": 8.0,
        "max_refinement_iters": 3,
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert "session_id" in payload["data"]
    assert payload["data"]["status"] == "active"


def test_get_session_roundtrip(client):
    create = client.post("/api/v3/sessions", json={
        "research_question": "Long-document summarisation research question test",
        "target_venue": "icml",
        "citation_style": "apa",
        "budget_usd": 5.0,
        "max_refinement_iters": 2,
    }).json()
    session_id = create["data"]["session_id"]
    get = client.get(f"/api/v3/sessions/{session_id}").json()
    assert get["success"] is True
    assert get["data"]["session_id"] == session_id


def test_run_pipeline_returns_run_id(client, tmp_path):
    idea_path = tmp_path / "idea.md"
    log_path = tmp_path / "experimental_log.md"
    idea_path.write_text("Hydrolysis note.\n", encoding="utf-8")
    log_path.write_text("Observed zinc flake coating response.\n", encoding="utf-8")
    session = client.post("/api/v3/sessions", json={
        "research_question": "Research question used for pipeline run smoke test",
        "target_venue": "neurips",
        "citation_style": "ieee",
        "budget_usd": 10.0,
        "max_refinement_iters": 3,
    }).json()
    session_id = session["data"]["session_id"]
    run = client.post("/api/v3/run", json={
        "session_id": session_id,
        "pipeline": "paper_orchestra",
        "idea_path": str(idea_path),
        "log_path": str(log_path),
    }).json()
    assert run["success"] is True
    assert "run_id" in run["data"]
    assert run["data"]["status"] in {"queued", "running"}

    events = asyncio.run(_collect_events(run["data"]["run_id"]))
    event_types = {event["type"] for event in events}
    assert "progress" in event_types
    assert "complete" in event_types

    inputs_dir = Path(__file__).resolve().parents[2] / "workspace" / session_id / "inputs"
    assert (inputs_dir / "idea.md").exists()
    assert (inputs_dir / "experimental_log.md").exists()


def test_unknown_session_returns_envelope_error(client):
    resp = client.get("/api/v3/sessions/does-not-exist").json()
    assert resp["success"] is False
    assert resp["error"] is not None
