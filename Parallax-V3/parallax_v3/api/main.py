"""FastAPI application entrypoint for Parallax V3."""

from __future__ import annotations

from fastapi import FastAPI

from .routes import router


app = FastAPI(title="Parallax V3 API")
app.include_router(router)
