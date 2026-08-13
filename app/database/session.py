"""Async SQLAlchemy engine/session management.

Switching between SQLite (dev) and PostgreSQL (prod) is purely a matter of
``DATABASE_URL`` — no code branches on environment here.
"""

from __future__ import annotations

import functools
from collections.abc import AsyncIterator
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import Settings, get_settings


def _ensure_sqlite_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return
    # sqlite+aiosqlite:///./data/job_automation.db -> ./data/job_automation.db
    path_part = database_url.split("///", maxsplit=1)[-1]
    if path_part in (":memory:", ""):
        return
    Path(path_part).parent.mkdir(parents=True, exist_ok=True)


@functools.lru_cache
def get_engine(settings: Settings | None = None) -> AsyncEngine:
    settings = settings or get_settings()
    _ensure_sqlite_dir(settings.database_url)
    return create_async_engine(settings.database_url, echo=False, future=True)


@functools.lru_cache
def get_sessionmaker(
    settings: Settings | None = None,
) -> async_sessionmaker[AsyncSession]:
    engine = get_engine(settings)
    return async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session."""
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session


async def check_database_connection() -> bool:
    """Lightweight connectivity check used by /health."""
    from sqlalchemy import text

    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
