from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.graph import persistence, service
from app.graph.service import RunResult

router = APIRouter(prefix="/api/runs", tags=["runs"])


class ResumeRequest(BaseModel):
    decisions: dict[str, str]


class RunListItem(BaseModel):
    id: str
    status: str
    enabled_portals: list[str]
    metrics: dict[str, Any] | None
    warnings: list[str]
    errors: list[dict[str, Any]]
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("", response_model=list[RunListItem])
async def list_runs(
    limit: int = Query(default=20, le=100),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[RunListItem]:
    records = await persistence.list_runs(session, limit=limit, offset=offset)
    return [RunListItem.model_validate(r) for r in records]


@router.post("", response_model=RunResult)
async def create_run() -> RunResult:
    return await service.start_run()


@router.get("/{run_id}", response_model=RunResult)
async def get_run(run_id: str) -> RunResult:
    result = await service.get_run_state(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@router.post("/{run_id}/resume", response_model=RunResult)
async def resume_run(run_id: str, body: ResumeRequest) -> RunResult:
    result = await service.resume_run(run_id, body.decisions)
    if result is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return result
