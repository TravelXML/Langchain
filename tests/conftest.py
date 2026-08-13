from __future__ import annotations

import os

# Must be set before any app module reads Settings, so tests never touch a
# developer's real ./data/job_automation.db.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CONFIG_DIR", "./config")
os.environ.setdefault("AUTOMATION_DRY_RUN", "true")

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
