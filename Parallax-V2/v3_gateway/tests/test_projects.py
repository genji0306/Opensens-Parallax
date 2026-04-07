"""Tests for project CRUD endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_project(client: AsyncClient):
    r = await client.post("/api/v3/projects", json={
        "name": "My Research",
        "domain": "academic",
        "budget_cap_usd": 25.0,
    })
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["name"] == "My Research"
    assert data["domain"] == "academic"
    assert data["budget_cap_usd"] == 25.0
    assert data["project_id"].startswith("prj_")


@pytest.mark.asyncio
async def test_list_projects(client: AsyncClient, project: dict):
    r = await client.get("/api/v3/projects")
    assert r.status_code == 200
    projects = r.json()["data"]
    assert any(p["project_id"] == project["project_id"] for p in projects)


@pytest.mark.asyncio
async def test_get_project(client: AsyncClient, project: dict):
    r = await client.get(f"/api/v3/projects/{project['project_id']}")
    assert r.status_code == 200
    assert r.json()["data"]["name"] == project["name"]


@pytest.mark.asyncio
async def test_get_project_not_found(client: AsyncClient):
    r = await client.get("/api/v3/projects/nonexistent")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_project(client: AsyncClient, project: dict):
    r = await client.patch(f"/api/v3/projects/{project['project_id']}", json={
        "name": "Updated Name",
        "status": "paused",
    })
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["name"] == "Updated Name"
    assert data["status"] == "paused"
