"""Persisted job records (Section 27).

Combines what the spec lists as separate ``jobs``/``job_scores`` tables
into one row — this system scores a job once per discovery, so there's no
score-history-over-time to justify a separate table yet (same pragmatic
merge as Phase 1's `candidate_profiles` folding in resume/cover-letter
versions).

Written by ``app/graph/persistence.py`` after a discovery run completes
(Phase 8) — Phases 3/4 deliberately used only the LangGraph checkpointer
for run state, which is correct for resuming a single in-flight run but
leaves nothing to list/filter/chart once a run finishes. This table is
that missing history.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class JobRecord(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # NormalizedJob.id
    run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    external_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, nullable=False)
    url: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    work_mode: Mapped[str | None] = mapped_column(String, nullable=True)
    salary_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    salary_currency: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    industry: Mapped[str | None] = mapped_column(String, nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # "queued" | "rejected" | "human_review" | "duplicate"
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)

    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    matched_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    missing_skills: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    recommendation: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
