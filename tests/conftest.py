from __future__ import annotations

import os
import tempfile
from pathlib import Path

# Must be set before any app module reads Settings, so tests never touch a
# developer's real ./data/job_automation.db or ./data/uploads.
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("CONFIG_DIR", "./config")
os.environ.setdefault("AUTOMATION_DRY_RUN", "true")
os.environ.setdefault("UPLOAD_DIR", tempfile.mkdtemp(prefix="job_automation_test_uploads_"))
# A real file, not ":memory:" — app.graph.graph.compiled_graph() opens a
# fresh sqlite connection per call to prove state persists across "process
# restarts" (Section 26); an in-memory DB would lose everything between
# calls since each connection would be its own empty database.
os.environ.setdefault(
    "LANGGRAPH_CHECKPOINT_PATH",
    str(Path(tempfile.mkdtemp(prefix="job_automation_test_checkpoints_")) / "checkpoints.db"),
)

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

import app.database.models  # noqa: E402,F401  (registers ORM tables on Base.metadata)
from app.database.base import Base  # noqa: E402
from app.database.session import get_engine  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture(autouse=True)
async def _reset_database():
    """Fresh schema per test.

    The in-memory SQLite engine is a process-wide singleton (see
    app/database/session.py's StaticPool handling) so tests share one
    connection — recreate tables around each test to keep them isolated.
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
