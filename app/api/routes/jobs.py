from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_session
from app.graph import persistence

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobOut(BaseModel):
    id: str
    run_id: str | None
    source: str
    url: str
    title: str
    company: str
    location: str | None
    work_mode: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    description: str
    industry: str | None
    employment_type: str | None
    posted_at: datetime | None
    discovered_at: datetime
    status: str
    overall_score: float | None
    breakdown: dict | None
    matched_skills: list[str]
    missing_skills: list[str]
    recommendation: str | None
    reason: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[JobOut])
async def list_jobs(
    status: str | None = None,
    company: str | None = None,
    source: str | None = None,
    run_id: str | None = None,
    min_score: float | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: AsyncSession = Depends(get_session),
) -> list[JobOut]:
    records = await persistence.list_jobs(
        session,
        status=status,
        company=company,
        source=source,
        run_id=run_id,
        min_score=min_score,
        limit=limit,
        offset=offset,
    )
    return [JobOut.model_validate(r) for r in records]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str, session: AsyncSession = Depends(get_session)) -> JobOut:
    record = await persistence.get_job(session, job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobOut.model_validate(record)
