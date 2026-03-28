"""
Parallax V3 Gateway — FastAPI application entry point.

Usage:
    cd Parallax-V2
    python -m v3_gateway.main              # Development server on :5003
    uvicorn v3_gateway.main:app --reload   # With auto-reload
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .models.base import init_db

logger = logging.getLogger("v3_gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    settings = get_settings()

    # Create database tables
    logger.info("Initializing V3 database...")
    await init_db()
    logger.info("V3 database ready (%s)", settings.database_url.split("@")[-1] if "@" in settings.database_url else settings.database_url)

    # Log integration status
    logger.info("V2 backend: %s", settings.v2_backend_url)
    logger.info("Redis DRVP: %s (enabled=%s)", settings.redis_url, settings.redis_enabled)
    logger.info("Paperclip: %s (enabled=%s)", settings.paperclip_url, settings.paperclip_enabled)
    logger.info("DarkLab: %s (enabled=%s)", settings.darklab_gateway_url, settings.darklab_enabled)
    logger.info("DAMD: %s (enabled=%s)", settings.damd_coordinator_url, settings.damd_enabled)

    yield

    logger.info("V3 Gateway shutting down.")


def create_app() -> FastAPI:
    """Create the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Parallax V3 Gateway",
        description="Autonomous Research Operating System — unified gateway for research, experiment, simulation, and compute workflows",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API routers
    from .api.projects import router as projects_router
    from .api.runs import router as runs_router
    from .api.phases import router as phases_router
    from .api.events import router as events_router
    from .api.costs import router as costs_router
    from .api.templates import router as templates_router
    from .api.approvals import router as approvals_router
    from .api.audit import router as audit_router

    api_prefix = "/api/v3"
    app.include_router(projects_router, prefix=api_prefix)
    app.include_router(runs_router, prefix=api_prefix)
    app.include_router(phases_router, prefix=api_prefix)
    app.include_router(events_router, prefix=api_prefix)
    app.include_router(costs_router, prefix=api_prefix)
    app.include_router(templates_router, prefix=api_prefix)
    app.include_router(approvals_router, prefix=api_prefix)
    app.include_router(audit_router, prefix=api_prefix)

    # Health check
    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "service": "parallax-v3-gateway",
            "version": "0.1.0",
            "integrations": {
                "redis": settings.redis_enabled,
                "paperclip": settings.paperclip_enabled,
                "darklab": settings.darklab_enabled,
                "damd": settings.damd_enabled,
            },
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    uvicorn.run(
        "v3_gateway.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
