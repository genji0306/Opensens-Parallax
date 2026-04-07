"""Shared fixtures for V3 gateway tests."""

import os

# Set in-memory DB BEFORE any v3_gateway imports so the engine and all
# `from ..models.base import async_session` bindings use the test DB.
os.environ["V3_DATABASE_URL"] = "sqlite+aiosqlite://"

# Clear cached settings in case config was already imported
from v3_gateway.config import get_settings  # noqa: E402
get_settings.cache_clear()

import asyncio  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import AsyncClient, ASGITransport  # noqa: E402

from v3_gateway.models.base import Base, engine  # noqa: E402
from v3_gateway.main import app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def setup_db():
    """Create all tables once per session."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest_asyncio.fixture
async def client(setup_db):
    """Async HTTP client against the V3 app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def project(client: AsyncClient):
    """Create a test project and return its data."""
    r = await client.post("/api/v3/projects", json={
        "name": "Test Project",
        "domain": "academic",
        "budget_cap_usd": 50.0,
    })
    return r.json()["data"]


@pytest_asyncio.fixture
async def run_with_phases(client: AsyncClient, project: dict):
    """Create a test run with academic_research template."""
    r = await client.post("/api/v3/runs", json={
        "project_id": project["project_id"],
        "template_id": "academic_research",
        "config": {"research_idea": "test idea"},
        "auto_start": False,
    })
    return r.json()["data"]
