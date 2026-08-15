"""Schedule entry models, parsed from `config/automation.yaml`'s
`scheduler.schedules` list (Section 34).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class CronSchedule(BaseModel):
    type: Literal["cron"] = "cron"
    expression: str


class IntervalSchedule(BaseModel):
    type: Literal["interval"] = "interval"
    hours: float = 0
    minutes: float = 0
    seconds: float = 0


def parse_schedule(raw: dict[str, Any]) -> CronSchedule | IntervalSchedule:
    schedule_type = raw.get("type")
    if schedule_type == "cron":
        return CronSchedule(**raw)
    if schedule_type == "interval":
        return IntervalSchedule(**raw)
    raise ValueError(f"unknown schedule type: {schedule_type!r}")
