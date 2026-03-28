"""V3 Gateway configuration from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Gateway configuration. Reads from env vars or .env file."""

    # ── Server ───────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 5003
    debug: bool = False

    # ── Database ─────────────────────────────────────────────
    # PostgreSQL for V3 tables (projects, costs, audit, approvals)
    database_url: str = "sqlite+aiosqlite:///v3_gateway/data/v3.db"
    # Falls back to async SQLite for local dev — switch to PostgreSQL for prod:
    # database_url: str = "postgresql+asyncpg://user:pass@localhost:5432/parallax_v3"

    # ── Redis (DRVP event bus) ───────────────────────────────
    redis_url: str = "redis://localhost:6379/0"
    redis_enabled: bool = False  # Disable if Redis not running

    # ── V2 Backend ───────────────────────────────────────────
    v2_backend_url: str = "http://localhost:5002"

    # ── Paperclip Governance ─────────────────────────────────
    paperclip_url: str = "http://localhost:3100"
    paperclip_enabled: bool = False

    # ── DarkLab Cluster ──────────────────────────────────────
    darklab_gateway_url: str = "ws://localhost:18789"
    darklab_enabled: bool = False

    # ── DAMD Compute ─────────────────────────────────────────
    damd_coordinator_url: str = "http://localhost:8200"
    damd_enabled: bool = False

    # ── Budget Defaults ──────────────────────────────────────
    default_project_budget_usd: float = 50.0
    default_run_budget_usd: float = 25.0

    # ── CORS ─────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3002", "http://localhost:5173"]

    model_config = {"env_prefix": "V3_", "env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
