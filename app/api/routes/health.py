from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings
from app.database.session import check_database_connection

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app_env: str
    database_connected: bool
    dry_run: bool


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    db_ok = await check_database_connection()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        app_env=settings.app_env,
        database_connected=db_ok,
        dry_run=settings.automation_dry_run,
    )
