"""Response models for `/api/analytics/*` (Section 33)."""

from __future__ import annotations

from pydantic import BaseModel


class AnalyticsSummary(BaseModel):
    jobs_discovered_today: int
    jobs_by_status: dict[str, int]
    jobs_by_recommendation: dict[str, int]
    jobs_by_score_bucket: dict[str, int]
    applications_today: int
    applications_this_week: int
    applications_this_month: int
    applications_by_status: dict[str, int]
    applications_by_source: dict[str, int]
    top_matched_skills: list[list[object]]
    top_missing_skills: list[list[object]]
    companies_applied_to: list[str]
    human_review_pending: int


class PlatformBreakdown(BaseModel):
    source: str
    jobs_discovered: int
    jobs_queued: int
    jobs_rejected: int
    applications: int


class PlatformStats(BaseModel):
    platforms: list[PlatformBreakdown]


class ScoreStats(BaseModel):
    count: int
    min_score: float | None
    max_score: float | None
    average_score: float | None
    median_score: float | None
    score_buckets: dict[str, int]
    average_breakdown: dict[str, float]
