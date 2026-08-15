"""Persisted application records (Section 27, Phase 8).

Written by ``app/graph/persistence.py`` from ``apply_service.py`` on every
start/resume of the Phase 6 apply subgraph, so the dashboard has an
application history to list — the apply graph itself remains
LangGraph-checkpointer-only for *resuming* an in-flight application; this
table is a separate, append-friendly summary for *listing* them.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class ApplicationRecord(Base, TimestampMixin):
    __tablename__ = "applications"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # application_id
    job_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    job_title: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    form_page_url: Mapped[str] = mapped_column(String, nullable=False)

    # "waiting_human" | "dry_run_ready" | "rejected_by_human" | "submitted_mock"
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)

    interrupt_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
