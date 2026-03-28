"""Tests for costs, budget, approvals, and audit."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_project_cost_initially_zero(client: AsyncClient, project: dict):
    pid = project["project_id"]
    r = await client.get(f"/api/v3/costs/project/{pid}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total_cost_usd"] == 0
    assert data["entry_count"] == 0


@pytest.mark.asyncio
async def test_budget_check(client: AsyncClient, project: dict):
    pid = project["project_id"]
    r = await client.get(f"/api/v3/costs/project/{pid}/budget")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["allowed"] is True
    assert data["remaining_usd"] == project["budget_cap_usd"]
    assert data["spent_usd"] == 0


@pytest.mark.asyncio
async def test_cost_recorded_on_phase_complete(client: AsyncClient, run_with_phases: dict, project: dict):
    pid = project["project_id"]
    phase = run_with_phases["phases"][0]

    # Complete phase with cost
    await client.post(f"/api/v3/phases/{phase['phase_id']}/complete", json={
        "outputs": {"ok": True},
        "model_used": "claude-sonnet-4-20250514",
        "cost_usd": 0.12,
    })

    # Check cost recorded
    r = await client.get(f"/api/v3/costs/project/{pid}")
    data = r.json()["data"]
    assert data["total_cost_usd"] >= 0.12
    assert data["entry_count"] >= 1


@pytest.mark.asyncio
async def test_cost_entries_list(client: AsyncClient, project: dict):
    pid = project["project_id"]
    r = await client.get(f"/api/v3/costs/project/{pid}/entries")
    assert r.status_code == 200
    entries = r.json()["data"]
    assert isinstance(entries, list)


@pytest.mark.asyncio
async def test_run_cost_breakdown(client: AsyncClient, run_with_phases: dict):
    rid = run_with_phases["run_id"]
    r = await client.get(f"/api/v3/costs/run/{rid}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "total_cost_usd" in data
    assert "by_phase" in data


@pytest.mark.asyncio
async def test_audit_log_records_actions(client: AsyncClient, project: dict):
    r = await client.get("/api/v3/audit")
    assert r.status_code == 200
    entries = r.json()["data"]
    # Should have at least project.created
    actions = {e["action"] for e in entries}
    assert "project.created" in actions


@pytest.mark.asyncio
async def test_audit_filter_by_resource(client: AsyncClient, project: dict):
    pid = project["project_id"]
    r = await client.get("/api/v3/audit", params={"resource_type": "project", "resource_id": pid})
    assert r.status_code == 200
    entries = r.json()["data"]
    assert all(e["resource_id"] == pid for e in entries)


@pytest.mark.asyncio
async def test_approvals_list_empty(client: AsyncClient):
    r = await client.get("/api/v3/approvals")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)


@pytest.mark.asyncio
async def test_approval_gate_creates_awaiting(client: AsyncClient, project: dict):
    """When execute-next hits an approval_gate phase, it should set awaiting_approval."""
    # Create experiment run (has approval_gate)
    r = await client.post("/api/v3/runs", json={
        "project_id": project["project_id"],
        "template_id": "experiment",
        "config": {},
    })
    run = r.json()["data"]
    rid = run["run_id"]
    phases = run["phases"]

    # Complete experiment_plan and safety_check to reach approval_gate
    for p in phases[:2]:
        await client.post(f"/api/v3/phases/{p['phase_id']}/complete", json={
            "outputs": {"ok": True}, "cost_usd": 0.01,
        })

    # Execute next — should hit approval_gate
    r = await client.post(f"/api/v3/phases/run/{rid}/execute-next")
    executed = r.json()["data"]["executed"]
    gate = next((e for e in executed if e["status"] == "awaiting_approval"), None)
    assert gate is not None


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["service"] == "parallax-v3-gateway"
    assert "integrations" in data
