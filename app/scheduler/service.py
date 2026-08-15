"""Scheduler service (Section 34) — deliberately independent from
LangGraph: every scheduled job calls a graph *service* function
(`graph.service.start_run`), the same public entrypoint
`POST /api/runs` uses. Nothing here knows about graph internals, nodes,
or checkpointing.

A single process-wide `AsyncIOScheduler` (APScheduler) is started once in
`app.main`'s lifespan and lives for the process lifetime. `reload()`
re-reads `config/automation.yaml`'s `scheduler` section and replaces
every registered job — called once at startup and again whenever
`PUT /api/settings` changes the automation section, so a schedule edit
takes effect with no restart, matching every other config-editable
behavior in this app.
"""

from __future__ import annotations

from typing import Any

from apscheduler.events import EVENT_JOB_ERROR, JobExecutionEvent
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.analytics import service as analytics_service
from app.core.config import get_yaml_config_loader
from app.core.logging import get_logger
from app.database.session import get_sessionmaker
from app.graph import service as run_service
from app.notifications.models import NotificationEvent, NotificationKind
from app.notifications.service import notify_all
from app.scheduler.models import CronSchedule, IntervalSchedule, parse_schedule

logger = get_logger(__name__)


def _build_trigger(schedule: CronSchedule | IntervalSchedule, timezone: str) -> Any:
    if isinstance(schedule, CronSchedule):
        return CronTrigger.from_crontab(schedule.expression, timezone=timezone)
    return IntervalTrigger(hours=schedule.hours, minutes=schedule.minutes, seconds=schedule.seconds)


async def _run_discovery_job() -> None:
    """The scheduled-run entrypoint (Section 34's "daily execution" /
    "specific weekdays" / "business-hour execution" — all expressed as
    cron expressions, see config/automation.yaml). Run completed/failed/
    human-review notifications are sent from inside `start_run()` itself
    (Phase 9's wiring into graph/service.py), so this stays a one-liner.
    """
    logger.info("scheduled_discovery_run_starting")
    await run_service.start_run()


async def _daily_summary_job() -> None:
    async with get_sessionmaker()() as session:
        summary = await analytics_service.compute_summary(session)
    await notify_all(
        NotificationEvent(
            kind=NotificationKind.DAILY_SUMMARY,
            title="Daily job automation summary",
            message=(
                f"{summary.jobs_discovered_today} jobs discovered today, "
                f"{summary.applications_today} applications today, "
                f"{summary.human_review_pending} pending human review."
            ),
            metadata=summary.model_dump(mode="json"),
        )
    )


def _on_job_error(event: JobExecutionEvent) -> None:
    logger.error("scheduled_job_failed", job_id=event.job_id, error=str(event.exception))


class SchedulerService:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()
        self._scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)
        self._started = False

    def start(self) -> None:
        self._scheduler.start()
        self._started = True
        self.reload()

    def reload(self) -> None:
        self._scheduler.remove_all_jobs()
        config = get_yaml_config_loader().load("automation").get("scheduler", {})
        if not config.get("enabled", False):
            logger.info("scheduler_disabled")
            return

        timezone = config.get("timezone", "UTC")
        for index, raw in enumerate(config.get("schedules", [])):
            try:
                trigger = _build_trigger(parse_schedule(raw), timezone)
            except Exception as exc:
                logger.error("invalid_schedule_config", index=index, raw=raw, error=str(exc))
                continue
            self._scheduler.add_job(
                _run_discovery_job, trigger, id=f"discovery-run-{index}", replace_existing=True
            )

        daily_summary_hour = config.get("daily_summary_hour", 18)
        self._scheduler.add_job(
            _daily_summary_job,
            CronTrigger(hour=daily_summary_hour, minute=0, timezone=timezone),
            id="daily-summary",
            replace_existing=True,
        )
        logger.info("scheduler_reloaded", registered_jobs=len(self._scheduler.get_jobs()))

    def shutdown(self) -> None:
        if self._started:
            self._scheduler.shutdown(wait=False)
            self._started = False

    def list_jobs(self) -> list[dict[str, Any]]:
        # `next_run_time` is an unset `__slots__` attribute (not merely
        # None) on a job added before the scheduler has actually started
        # — accessing it directly raises AttributeError in that case.
        jobs = []
        for job in self._scheduler.get_jobs():
            next_run_time = getattr(job, "next_run_time", None)
            jobs.append(
                {
                    "id": job.id,
                    "next_run_time": next_run_time.isoformat() if next_run_time else None,
                }
            )
        return jobs


_scheduler_service: SchedulerService | None = None


def get_scheduler_service() -> SchedulerService:
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service
