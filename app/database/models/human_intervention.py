"""Persisted human-review queue (Section 27, Phase 8).

A row exists here for every interrupt raised across either graph — the
Phase 3 discovery supervisor (``kind="run"``) or the Phase 6 apply
subgraph (``kind="application"``) — so the dashboard's Human Review page
has one place to list pending items from both, instead of having to poll
each graph's checkpointer directly.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, generate_uuid


class HumanInterventionRecord(Base, TimestampMixin):
    __tablename__ = "human_interventions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=generate_uuid)
    kind: Mapped[str] = mapped_column(String, nullable=False)  # "run" | "application"
    ref_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
