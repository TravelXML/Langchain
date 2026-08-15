"""Persisted discovery-run summaries (Section 27, Phase 8).

``created_at`` (from ``TimestampMixin``) doubles as "started at" — a run
row is created the moment ``service.start_run()`` invokes the graph.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class AutomationRunRecord(Base, TimestampMixin):
    __tablename__ = "automation_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)  # run_id
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    enabled_portals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    metrics: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
