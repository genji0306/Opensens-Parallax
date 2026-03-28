"""Tests for workflow runs, phases, and DAG operations."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_templates(client: AsyncClient):
    r = await client.get("/api/v3/templates")
    assert r.status_code == 200
    templates = r.json()["data"]
    assert len(templates) == 4
    ids = {t["template_id"] for t in templates}
    assert ids == {"academic_research", "experiment", "simulation", "full_research_experiment"}


@pytest.mark.asyncio
async def test_create_academic_run(client: AsyncClient, project: dict):
    r = await client.post("/api/v3/runs", json={
        "project_id": project["project_id"],
        "template_id": "academic_research",
        "config": {"research_idea": "GNN protein folding"},
    })
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["run_id"].startswith("run_")
    assert len(data["phases"]) == 9
    assert len(data["edges"]) == 12


@pytest.mark.asyncio
async def test_create_experiment_run(client: AsyncClient, project: dict):
    r = await client.post("/api/v3/runs", json={
        "project_id": project["project_id"],
        "template_id": "experiment",
        "config": {},
    })
    assert r.status_code == 201
    assert len(r.json()["data"]["phases"]) == 7


@pytest.mark.asyncio
async def test_create_simulation_run(client: AsyncClient, project: dict):
    r = await client.post("/api/v3/runs", json={
        "project_id": project["project_id"],
        "template_id": "simulation",
        "config": {},
    })
    assert r.status_code == 201
    assert len(r.json()["data"]["phases"]) == 9


@pytest.mark.asyncio
async def test_create_full_run(client: AsyncClient, project: dict):
    r = await client.post("/api/v3/runs", json={
        "project_id": project["project_id"],
        "template_id": "full_research_experiment",
        "config": {"research_idea": "test"},
    })
    assert r.status_code == 201
    data = r.json()["data"]
    assert len(data["phases"]) == 14
    assert len(data["edges"]) == 16


@pytest.mark.asyncio
async def test_invalid_template(client: AsyncClient, project: dict):
    r = await client.post("/api/v3/runs", json={
        "project_id": project["project_id"],
        "template_id": "nonexistent",
        "config": {},
    })
    assert r.status_code == 400
    assert "nonexistent" in r.json()["detail"]


@pytest.mark.asyncio
async def test_graph_state(client: AsyncClient, run_with_phases: dict):
    rid = run_with_phases["run_id"]
    r = await client.get(f"/api/v3/runs/{rid}/graph")
    assert r.status_code == 200
    graph = r.json()["data"]
    assert graph["summary"]["total_phases"] == 9
    assert graph["summary"]["completed"] == 0
    assert graph["summary"]["progress_pct"] == 0.0


@pytest.mark.asyncio
async def test_phase_complete_and_progress(client: AsyncClient, run_with_phases: dict):
    rid = run_with_phases["run_id"]
    phases = run_with_phases["phases"]
    first = phases[0]

    # Complete first phase
    r = await client.post(f"/api/v3/phases/{first['phase_id']}/complete", json={
        "outputs": {"papers": 42},
        "score": 7.5,
        "model_used": "claude-sonnet-4-20250514",
        "cost_usd": 0.05,
    })
    assert r.status_code == 200

    # Check graph progress
    r = await client.get(f"/api/v3/runs/{rid}/graph")
    graph = r.json()["data"]
    assert graph["summary"]["completed"] == 1
    assert graph["summary"]["progress_pct"] > 0


@pytest.mark.asyncio
async def test_phase_fail(client: AsyncClient, run_with_phases: dict):
    phases = run_with_phases["phases"]
    second = phases[1]

    r = await client.post(f"/api/v3/phases/{second['phase_id']}/fail", json={
        "error": "API timeout"
    })
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "failed"


@pytest.mark.asyncio
async def test_restart_from_phase(client: AsyncClient, run_with_phases: dict):
    rid = run_with_phases["run_id"]
    phases = run_with_phases["phases"]

    # Complete first two phases
    for p in phases[:2]:
        await client.post(f"/api/v3/phases/{p['phase_id']}/complete", json={
            "outputs": {"ok": True}, "cost_usd": 0.01,
        })

    # Restart from first phase
    r = await client.post(f"/api/v3/runs/{rid}/restart/{phases[0]['phase_id']}")
    assert r.status_code == 200
    result = r.json()["data"]
    assert result["invalidated_count"] > 0


@pytest.mark.asyncio
async def test_set_phase_model(client: AsyncClient, run_with_phases: dict):
    pid = run_with_phases["phases"][0]["phase_id"]
    r = await client.put(f"/api/v3/phases/{pid}/model", json={"model": "claude-opus-4-20250514"})
    assert r.status_code == 200
    assert r.json()["data"]["model"] == "claude-opus-4-20250514"


@pytest.mark.asyncio
async def test_set_phase_settings(client: AsyncClient, run_with_phases: dict):
    pid = run_with_phases["phases"][0]["phase_id"]
    r = await client.put(f"/api/v3/phases/{pid}/settings", json={
        "settings": {"max_papers": 200, "timeout_s": 600}
    })
    assert r.status_code == 200
    config = r.json()["data"]["config"]
    assert config["max_papers"] == 200
    assert config["timeout_s"] == 600


@pytest.mark.asyncio
async def test_start_run(client: AsyncClient, run_with_phases: dict):
    rid = run_with_phases["run_id"]
    r = await client.post(f"/api/v3/runs/{rid}/start")
    assert r.status_code == 202
    assert r.json()["data"]["status"] == "running"


@pytest.mark.asyncio
async def test_start_run_already_running(client: AsyncClient, run_with_phases: dict):
    rid = run_with_phases["run_id"]
    # First start
    await client.post(f"/api/v3/runs/{rid}/start")
    # Second start should fail
    r = await client.post(f"/api/v3/runs/{rid}/start")
    assert r.status_code == 400
