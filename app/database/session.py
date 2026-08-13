"""Async SQLAlchemy engine/session management.

Switching between SQLite (dev) and PostgreSQL (prod) is purely a matter of
``DATABASE_URL`` — no code branches on environment here.

``get_engine``/``get_sessionmaker`` take no arguments and always resolve
settings via ``get_settings()`` (itself a cached singleton). Do not add an
optional ``settings`` override here: ``functools.lru_cache`` keys strictly
on the arguments a call site actually passes, so ``get_engine()`` and
``get_engine(some_settings)`` — or even ``get_engine(None)`` vs.
``get_engine()`` — hash to *different* cache entries and silently produce
two unrelated engines/connection pools. For file-based SQLite or Postgres
that's merely wasteful; for in-memory SQLite it's fatal, since each engine
sees a completely separate database.
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
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


def _ensure_sqlite_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite"):
        return
    # sqlite+aiosqlite:///./data/job_automation.db -> ./data/job_automation.db
    path_part = database_url.split("///", maxsplit=1)[-1]
    if path_part in (":memory:", ""):
        return
    Path(path_part).parent.mkdir(parents=True, exist_ok=True)


@functools.lru_cache
def get_engine() -> AsyncEngine:
    settings = get_settings()
    _ensure_sqlite_dir(settings.database_url)

    # An in-memory SQLite database is per-connection: without a single shared
    # connection, a session opened by one code path can't see tables/rows
    # created by another (e.g. test setup vs. the API request handler).
    if "sqlite" in settings.database_url and ":memory:" in settings.database_url:
        return create_async_engine(
            settings.database_url, echo=False, future=True, poolclass=StaticPool
        )

    return create_async_engine(settings.database_url, echo=False, future=True)


@functools.lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped session."""
    async with get_sessionmaker()() as session:
        yield session


async def check_database_connection() -> bool:
    """Lightweight connectivity check used by /health."""
    from sqlalchemy import text

    try:
        async with get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
