"""Greenhouse portal adapter — the first real, non-mock adapter (Phase 7).

Discovery/detail-fetching use the real public API (`client.py`). Everything
touching an actual application page reuses the same browser engine Phases
5-6 already built and tested against local fixtures (`app/browser/`) —
this adapter's job is translating Greenhouse's shapes into ours, not
reimplementing form automation.

``discover_jobs`` deliberately returns dicts already in the common raw
shape ``app.jobs.parser.normalize_job`` expects (not Greenhouse's native
shape) — that lets `app/graph/nodes.py`'s existing, already-tested
``normalize_jobs_node`` handle every portal (mock or real) identically,
with zero changes. ``normalize_job`` still exists on this adapter per
Section 9's interface, and does the same conversion for direct/standalone
callers.
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from typing import Any

from playwright.async_api import Page

from app.browser.forms import detect_fields, fill_form, validate_form
from app.browser.manager import launch_browser
from app.browser.mapping import map_fields
from app.browser.models import DetectedField, FieldMapping, FormFillResult
from app.core.config import get_settings
from app.core.logging import get_logger
from app.jobs.models import NormalizedJob
from app.jobs.parser import normalize_job as _normalize_job
from app.portals.base import JobPortalAdapter
from app.portals.greenhouse.client import GreenhouseClient, strip_html
from app.profile.models import CandidateProfile

logger = get_logger(__name__)


def _to_common_raw_shape(raw: dict[str, Any], board_token: str) -> dict[str, Any]:
    location = raw.get("location") or {}
    departments = raw.get("departments") or []
    offices = raw.get("offices") or []
    return {
        "external_job_id": str(raw["id"]),
        "url": raw["absolute_url"],
        "title": raw["title"],
        "company": raw.get("company_name") or board_token,
        "location": location.get("name"),
        "description": strip_html(raw["content"]) if raw.get("content") else "",
        "industry": departments[0]["name"] if departments else None,
        "posted_at": raw.get("first_published"),
        "requisition_id": raw.get("requisition_id"),
        "offices": [o.get("name") for o in offices if o.get("name")],
    }


class GreenhouseAdapter(JobPortalAdapter):
    def __init__(self, board_token: str) -> None:
        self.board_token = board_token
        self._client = GreenhouseClient(board_token)

        self._stack: AsyncExitStack | None = None
        self._page: Page | None = None
        self._detected_fields: list[DetectedField] = []
        self._mappings: list[FieldMapping] = []

    async def authenticate(self) -> None:
        # Greenhouse's public job board API requires no authentication.
        return None

    async def discover_jobs(self, search_policy: dict[str, Any]) -> list[dict[str, Any]]:
        raw_jobs = await self._client.list_jobs()
        return [_to_common_raw_shape(raw, self.board_token) for raw in raw_jobs]

    async def get_job_details(self, job: dict[str, Any]) -> dict[str, Any]:
        raw = await self._client.get_job(job["external_job_id"])
        return _to_common_raw_shape(raw, self.board_token)

    async def normalize_job(self, raw_job: dict[str, Any]) -> NormalizedJob:
        return _normalize_job(raw_job, source=f"greenhouse:{self.board_token}")

    async def prepare_application(
        self, job: NormalizedJob, candidate: CandidateProfile
    ) -> dict[str, Any]:
        self._stack = AsyncExitStack()
        browser = await self._stack.enter_async_context(launch_browser())
        self._page = await browser.new_page()
        await self._page.goto(job.url)

        self._detected_fields = await detect_fields(self._page)
        self._mappings = map_fields(self._detected_fields, candidate)

        return {
            "job_id": job.id,
            "url": job.url,
            "mappings": [m.model_dump() for m in self._mappings],
        }

    async def fill_application(self, application: dict[str, Any]) -> FormFillResult:
        assert self._page is not None, "call prepare_application() first"
        return await fill_form(self._page, self._detected_fields, self._mappings)

    async def validate_application(self) -> list[str]:
        assert self._page is not None, "call prepare_application() first"
        return await validate_form(self._page)

    async def submit_application(self) -> dict[str, Any]:
        if get_settings().automation_dry_run:
            # Section 47: dry-run must never submit, regardless of how far
            # preparation got.
            return {"status": "dry_run_ready", "submitted": False}

        # Real submission is deliberately not implemented: every phase up
        # to and including this one has kept AUTOMATION_DRY_RUN enforced
        # (Section 47's mandatory default), and flipping that is a
        # separate, explicit decision outside this phase's scope — not
        # something a code path should silently make possible.
        raise NotImplementedError(
            "Real submission requires AUTOMATION_DRY_RUN=false, which this "
            "codebase does not implement a bypass for yet."
        )

    async def verify_submission(self) -> bool:
        # Never reached while dry_run is enforced (submit_application
        # returns before doing anything) — exists for interface
        # completeness and so a future real-submission path has somewhere
        # to plug in Section 50's "never assume a click means success".
        return False

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._page = None
