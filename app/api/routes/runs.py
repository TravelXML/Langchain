from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.graph import service
from app.graph.service import RunResult

router = APIRouter(prefix="/api/runs", tags=["runs"])


class ResumeRequest(BaseModel):
    decisions: dict[str, str]


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
