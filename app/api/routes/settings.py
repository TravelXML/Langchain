"""Read/write access to the editable domain config (Section 51's Settings
page): ``config/automation.yaml``, ``scoring.yaml``, ``search.yaml``, and
``portals.yaml``. These are exactly the files ``YamlConfigLoader`` already
serves to the rest of the app (candidate preferences, scoring weights,
portal registry) — deliberately kept separate from ``Settings``
(``app/core/config.py``), which is process/env-level and not meant to be
edited at runtime.

Each PUT rewrites its file wholesale via ``yaml.safe_dump`` — comments in
the shipped config files are not preserved across an edit made through
this API. Acceptable for a local single-operator tool; not something to
build a comment-preserving YAML round-trip for.
"""

from __future__ import annotations

from typing import Any

import yaml
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings, get_yaml_config_loader
from app.scheduler.service import get_scheduler_service

router = APIRouter(prefix="/api/settings", tags=["settings"])

_EDITABLE_SECTIONS = ("automation", "scoring", "search", "portals", "notifications")


class SettingsOut(BaseModel):
    automation: dict[str, Any]
    scoring: dict[str, Any]
    search: dict[str, Any]
    portals: dict[str, Any]
    notifications: dict[str, Any]


class SettingsUpdate(BaseModel):
    automation: dict[str, Any] | None = None
    scoring: dict[str, Any] | None = None
    search: dict[str, Any] | None = None
    portals: dict[str, Any] | None = None
    notifications: dict[str, Any] | None = None


@router.get("", response_model=SettingsOut)
async def get_settings_config() -> SettingsOut:
    loader = get_yaml_config_loader()
    return SettingsOut(**{name: loader.load(name) for name in _EDITABLE_SECTIONS})


@router.put("", response_model=SettingsOut)
async def update_settings_config(body: SettingsUpdate) -> SettingsOut:
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="No settings sections provided")

    config_dir = get_settings().config_dir
    loader = get_yaml_config_loader()
    for name, content in updates.items():
        path = config_dir / f"{name}.yaml"
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(content, f, sort_keys=False)
        loader.reload(name)

    if "automation" in updates:
        # scheduler.* lives inside automation.yaml — re-register jobs
        # against the new config immediately, no restart required.
        get_scheduler_service().reload()

    return SettingsOut(**{name: loader.load(name) for name in _EDITABLE_SECTIONS})
