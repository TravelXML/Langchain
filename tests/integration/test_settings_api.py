"""GET/PUT /api/settings writes real YAML files, so these tests point
CONFIG_DIR at an isolated copy for the duration of each test and always
restore the real env var + clear the settings caches afterward — never
touch the repo's actual config/*.yaml.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest
import yaml

from app.core import config as config_module
from app.scheduler.service import get_scheduler_service

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


async def test_get_settings_returns_all_sections(client, isolated_config_dir):
    response = await client.get("/api/settings")
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"automation", "scoring", "search", "portals", "notifications"}
    assert body["automation"]["approval"]["mode"] == "manual"


async def test_put_settings_updates_file_and_response(client, isolated_config_dir):
    current = (await client.get("/api/settings")).json()
    updated_automation = dict(current["automation"])
    updated_automation["approval"] = {**updated_automation["approval"], "mode": "hybrid"}

    response = await client.put("/api/settings", json={"automation": updated_automation})
    assert response.status_code == 200
    assert response.json()["automation"]["approval"]["mode"] == "hybrid"

    on_disk = yaml.safe_load((isolated_config_dir / "automation.yaml").read_text())
    assert on_disk["approval"]["mode"] == "hybrid"

    # Sections not included in the PUT are left untouched.
    on_disk_scoring = yaml.safe_load((isolated_config_dir / "scoring.yaml").read_text())
    assert on_disk_scoring == current["scoring"]


async def test_put_settings_automation_reloads_scheduler(client, isolated_config_dir):
    current = (await client.get("/api/settings")).json()
    updated_automation = dict(current["automation"])
    updated_automation["scheduler"] = {
        "enabled": True,
        "timezone": "UTC",
        "schedules": [{"type": "interval", "hours": 3}],
        "daily_summary_hour": 18,
    }

    response = await client.put("/api/settings", json={"automation": updated_automation})
    assert response.status_code == 200

    job_ids = {job["id"] for job in get_scheduler_service().list_jobs()}
    assert job_ids == {"discovery-run-0", "daily-summary"}

    # Disabling again clears the jobs — proves reload() actually re-reads
    # the file rather than only ever adding.
    updated_automation["scheduler"]["enabled"] = False
    await client.put("/api/settings", json={"automation": updated_automation})
    assert get_scheduler_service().list_jobs() == []


async def test_put_settings_with_no_sections_returns_422(client, isolated_config_dir):
    response = await client.put("/api/settings", json={})
    assert response.status_code == 422


async def test_real_config_dir_untouched_by_settings_tests():
    on_disk = yaml.safe_load((_REAL_CONFIG_DIR / "automation.yaml").read_text())
    assert on_disk["approval"]["mode"] == "manual"
