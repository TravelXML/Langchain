"""Analytics computation, shared by the `/api/analytics/*` routes and the
scheduler's daily-summary job (Section 35) — one place computes these
numbers, HTTP and the scheduler both just call into it.

Metrics that would require observing real employer responses (response
rate, interview rate, average response time) have no data source
anywhere in this system — no inbound email/webhook monitoring — so they
are deliberately omitted rather than reported as fabricated zeros.
"""

from __future__ import annotations

import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import (
    AnalyticsSummary,
    PlatformBreakdown,
    PlatformStats,
    ScoreStats,
)
from app.database.models.application import ApplicationRecord
from app.database.models.human_intervention import HumanInterventionRecord
from app.database.models.job import JobRecord

_BREAKDOWN_DIMENSIONS = ("title", "skills", "experience", "industry", "location", "compensation")


def _as_utc(value: datetime) -> datetime:
    """SQLite drops tzinfo on read even for ``DateTime(timezone=True)``
    columns — every value this app writes is UTC, so a naive read is
    always UTC, never local time.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _score_bucket(score: float) -> str:
    if score >= 90:
        return "90-100"
    if score >= 80:
        return "80-89"
    if score >= 75:
        return "75-79"
    if score >= 60:
        return "60-74"
    return "0-59"


async def _load(
    session: AsyncSession,
) -> tuple[list[JobRecord], list[ApplicationRecord], list[HumanInterventionRecord]]:
    jobs = list((await session.execute(select(JobRecord))).scalars().all())
    apps = list((await session.execute(select(ApplicationRecord))).scalars().all())
    pending = list(
        (
            await session.execute(
                select(HumanInterventionRecord).where(HumanInterventionRecord.status == "pending")
            )
        )
        .scalars()
        .all()
    )
    return jobs, apps, pending


async def compute_summary(session: AsyncSession) -> AnalyticsSummary:
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=today_start.weekday())
    month_start = today_start.replace(day=1)

    jobs, apps, pending = await _load(session)
    job_by_id = {job.id: job for job in jobs}

    return AnalyticsSummary(
        jobs_discovered_today=sum(1 for j in jobs if _as_utc(j.discovered_at) >= today_start),
        jobs_by_status=dict(Counter(j.status for j in jobs)),
        jobs_by_recommendation=dict(Counter(j.recommendation for j in jobs if j.recommendation)),
        jobs_by_score_bucket=dict(
            Counter(_score_bucket(j.overall_score) for j in jobs if j.overall_score is not None)
        ),
        applications_today=sum(1 for a in apps if _as_utc(a.created_at) >= today_start),
        applications_this_week=sum(1 for a in apps if _as_utc(a.created_at) >= week_start),
        applications_this_month=sum(1 for a in apps if _as_utc(a.created_at) >= month_start),
        applications_by_status=dict(Counter(a.status for a in apps)),
        applications_by_source=dict(
            Counter(
                job_by_id[a.job_id].source if a.job_id in job_by_id else "unknown" for a in apps
            )
        ),
        top_matched_skills=[
            list(pair)
            for pair in Counter(s for j in jobs for s in j.matched_skills).most_common(10)
        ],
        top_missing_skills=[
            list(pair)
            for pair in Counter(s for j in jobs for s in j.missing_skills).most_common(10)
        ],
        companies_applied_to=sorted({a.company for a in apps}),
        human_review_pending=len(pending),
    )


async def compute_platform_stats(session: AsyncSession) -> PlatformStats:
    jobs, apps, _ = await _load(session)
    job_by_id = {job.id: job for job in jobs}

    def app_source(app_record: ApplicationRecord) -> str:
        job = job_by_id.get(app_record.job_id) if app_record.job_id else None
        return job.source if job is not None else "unknown"

    by_source_apps: dict[str, int] = defaultdict(int)
    for app_record in apps:
        by_source_apps[app_source(app_record)] += 1

    sources = sorted({j.source for j in jobs} | set(by_source_apps))

    platforms = []
    for source in sources:
        source_jobs = [j for j in jobs if j.source == source]
        platforms.append(
            PlatformBreakdown(
                source=source,
                jobs_discovered=len(source_jobs),
                jobs_queued=sum(1 for j in source_jobs if j.status == "queued"),
                jobs_rejected=sum(1 for j in source_jobs if j.status == "rejected"),
                applications=by_source_apps.get(source, 0),
            )
        )
    return PlatformStats(platforms=platforms)


async def compute_score_stats(session: AsyncSession) -> ScoreStats:
    jobs, _, _ = await _load(session)
    scored = [j for j in jobs if j.overall_score is not None]
    scores = [j.overall_score for j in scored if j.overall_score is not None]

    average_breakdown: dict[str, float] = {}
    breakdowns = [j.breakdown for j in scored if j.breakdown]
    for dimension in _BREAKDOWN_DIMENSIONS:
        values = [b[dimension] for b in breakdowns if dimension in b]
        if values:
            average_breakdown[dimension] = round(statistics.mean(values), 2)

    return ScoreStats(
        count=len(scores),
        min_score=min(scores) if scores else None,
        max_score=max(scores) if scores else None,
        average_score=round(statistics.mean(scores), 2) if scores else None,
        median_score=round(statistics.median(scores), 2) if scores else None,
        score_buckets=dict(Counter(_score_bucket(s) for s in scores)),
        average_breakdown=average_breakdown,
    )
