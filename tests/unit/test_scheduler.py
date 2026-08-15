"""Scheduler tests (Section 34). SchedulerService.reload() reads
`config/automation.yaml`'s `scheduler` section via the same
CONFIG_DIR-override pattern `test_settings_api.py` uses — an isolated
copy of the real config directory, restored/cache-cleared afterward so
these tests never touch the repo's actual config files.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
import yaml

from app.core import config as config_module
from app.scheduler.models import CronSchedule, IntervalSchedule, parse_schedule
from app.scheduler.service import SchedulerService, _build_trigger

_REAL_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"


@pytest.fixture
def isolated_config_dir(tmp_path):
    temp_config_dir = tmp_path / "config"
    shutil.copytree(_REAL_CONFIG_DIR, temp_config_dir)

    original = os.environ.get("CONFIG_DIR")
    os.environ["CONFIG_DIR"] = str(temp_config_dir)
    config_module.get_settings.cache_clear()
    config_module.get_yaml_config_loader.cache_clear()
    try:
        yield temp_config_dir
    finally:
        if original is None:
            os.environ.pop("CONFIG_DIR", None)
        else:
            os.environ["CONFIG_DIR"] = original
        config_module.get_settings.cache_clear()
        config_module.get_yaml_config_loader.cache_clear()


def _write_automation_yaml(config_dir: Path, scheduler: dict) -> None:
    content = {
        "automation": {"dry_run": True, "discovery_concurrency": 3, "application_concurrency": 1},
        "limits": {"applications_per_day": 30, "applications_per_company_per_day": 2},
        "approval": {"mode": "manual"},
        "scheduler": scheduler,
    }
    (config_dir / "automation.yaml").write_text(yaml.safe_dump(content))


# --- parse_schedule / _build_trigger -----------------------------------


def test_parse_schedule_cron():
    schedule = parse_schedule({"type": "cron", "expression": "0 9 * * 1-5"})
    assert isinstance(schedule, CronSchedule)
    assert schedule.expression == "0 9 * * 1-5"


def test_parse_schedule_interval():
    schedule = parse_schedule({"type": "interval", "hours": 2})
    assert isinstance(schedule, IntervalSchedule)
    assert schedule.hours == 2


def test_parse_schedule_unknown_type_raises():
    with pytest.raises(ValueError, match="unknown schedule type"):
        parse_schedule({"type": "weekly"})


def test_build_trigger_cron_uses_crontab_expression():
    trigger = _build_trigger(CronSchedule(expression="0 9 * * *"), "UTC")
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields["hour"] == "9"
    assert fields["minute"] == "0"


def test_build_trigger_interval_uses_given_hours():
    trigger = _build_trigger(IntervalSchedule(hours=2), "UTC")
    assert trigger.interval.total_seconds() == 2 * 3600


# --- SchedulerService.reload() ------------------------------------------


def test_reload_disabled_registers_no_jobs(isolated_config_dir):
    _write_automation_yaml(
        isolated_config_dir, {"enabled": False, "timezone": "UTC", "schedules": []}
    )
    service = SchedulerService()
    service.reload()
    assert service.list_jobs() == []


def test_reload_enabled_registers_schedules_plus_daily_summary(isolated_config_dir):
    _write_automation_yaml(
        isolated_config_dir,
        {
            "enabled": True,
            "timezone": "UTC",
            "schedules": [
                {"type": "cron", "expression": "0 9 * * *"},
                {"type": "interval", "hours": 2},
            ],
            "daily_summary_hour": 20,
        },
    )
    service = SchedulerService()
    service.reload()
    job_ids = {job["id"] for job in service.list_jobs()}
    assert job_ids == {"discovery-run-0", "discovery-run-1", "daily-summary"}


def test_reload_skips_invalid_schedule_entry_but_keeps_others(isolated_config_dir):
    _write_automation_yaml(
        isolated_config_dir,
        {
            "enabled": True,
            "timezone": "UTC",
            "schedules": [
                {"type": "cron", "expression": "0 9 * * *"},
                {"type": "not-a-real-type"},
            ],
        },
    )
    service = SchedulerService()
    service.reload()
    job_ids = {job["id"] for job in service.list_jobs()}
    assert job_ids == {"discovery-run-0", "daily-summary"}


def test_reload_is_idempotent_and_replaces_prior_jobs(isolated_config_dir):
    _write_automation_yaml(
        isolated_config_dir,
        {"enabled": True, "timezone": "UTC", "schedules": [{"type": "interval", "hours": 1}]},
    )
    service = SchedulerService()
    service.reload()
    assert len(service.list_jobs()) == 2  # discovery-run-0 + daily-summary

    _write_automation_yaml(
        isolated_config_dir, {"enabled": False, "timezone": "UTC", "schedules": []}
    )
    config_module.get_yaml_config_loader().reload("automation")
    service.reload()
    assert service.list_jobs() == []
