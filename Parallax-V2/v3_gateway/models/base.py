"""Database engine and session factory for V3 Gateway."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from ..config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all V3 models."""
    pass


_settings = get_settings()
engine = create_async_engine(
    _settings.database_url,
    echo=_settings.debug,
    # For SQLite async: need check_same_thread=False
    connect_args={"check_same_thread": False} if "sqlite" in _settings.database_url else {},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """Create all tables. Called once at startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
