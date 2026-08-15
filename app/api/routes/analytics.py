"""Aggregate stats for the dashboard's Overview/Analytics pages
(Section 32/33). The computation itself lives in `app.analytics.service`
so the scheduler's daily-summary job (Phase 9) can reuse it without going
through HTTP.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics import service as analytics_service
from app.analytics.models import AnalyticsSummary, PlatformStats, ScoreStats
from app.database.session import get_session

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary", response_model=AnalyticsSummary)
async def get_analytics_summary(session: AsyncSession = Depends(get_session)) -> AnalyticsSummary:
    return await analytics_service.compute_summary(session)


@router.get("/platforms", response_model=PlatformStats)
async def get_analytics_platforms(session: AsyncSession = Depends(get_session)) -> PlatformStats:
    return await analytics_service.compute_platform_stats(session)


@router.get("/scores", response_model=ScoreStats)
async def get_analytics_scores(session: AsyncSession = Depends(get_session)) -> ScoreStats:
    return await analytics_service.compute_score_stats(session)
