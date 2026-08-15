"""Lever portal adapter — the second real, non-mock adapter (Phase 10:
"add each portal as an isolated adapter/subgraph, do not modify the
supervisor for every new portal").

Same shape as ``app/portals/greenhouse/adapter.py`` on purpose: discovery/
detail-fetching use the real public API (``client.py``), application
handling delegates entirely to the browser engine Phases 5-6 already
built, and ``discover_jobs`` returns the common raw shape
``app.jobs.parser.normalize_job`` expects so `app/graph/nodes.py`'s
discovery node needs zero portal-specific code (see
``app/portals/registry.py``, which is what actually lets this adapter
plug in without touching the supervisor).
"""

from __future__ import annotations

from contextlib import AsyncExitStack
from datetime import UTC, datetime
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
from app.portals.html import strip_html
from app.portals.lever.client import LeverClient
from app.profile.models import CandidateProfile

logger = get_logger(__name__)


def _epoch_ms_to_iso(epoch_ms: int | None) -> str | None:
    """Lever's ``createdAt`` is epoch *milliseconds* — passed raw, Pydantic
    v2 would parse it as epoch *seconds* (its default for a bare int/float)
    and land on a date thousands of years out. Caught before it ever
    reached ``NormalizedJob``, verified against Lever's real demo board.
    """
    if epoch_ms is None:
        return None
    return datetime.fromtimestamp(epoch_ms / 1000, tz=UTC).isoformat()


def _to_common_raw_shape(raw: dict[str, Any], company: str) -> dict[str, Any]:
    categories = raw.get("categories") or {}
    description = raw.get("descriptionPlain") or (
        strip_html(raw["description"]) if raw.get("description") else ""
    )
    extra_sections = [
        f"{item.get('text', '')}\n{strip_html(item['content'])}".strip()
        for item in raw.get("lists") or []
        if item.get("content")
    ]
    if extra_sections:
        description = "\n\n".join([description, *extra_sections]).strip()

    return {
        # Lever splits the descriptive posting page (``hostedUrl``, zero
        # form fields — confirmed live) from the actual application form
        # (``applyUrl``, ``hostedUrl`` + "/apply"). `url` must be the form
        # page since `prepare_application` navigates straight to it;
        # `hostedUrl` is kept in metadata for a human wanting the
        # human-readable posting instead.
        "external_job_id": raw["id"],
        "url": raw.get("applyUrl") or raw.get("hostedUrl"),
        "posting_url": raw.get("hostedUrl"),
        "title": raw["text"],
        "company": company,
        "location": categories.get("location"),
        "work_mode": raw.get("workplaceType"),
        "description": description,
        "industry": categories.get("department"),
        "employment_type": categories.get("commitment"),
        "posted_at": _epoch_ms_to_iso(raw.get("createdAt")),
        "team": categories.get("team"),
    }


class LeverAdapter(JobPortalAdapter):
    def __init__(self, company: str) -> None:
        self.company = company
        self._client = LeverClient(company)

        self._stack: AsyncExitStack | None = None
        self._page: Page | None = None
        self._detected_fields: list[DetectedField] = []
        self._mappings: list[FieldMapping] = []

    async def authenticate(self) -> None:
        # Lever's public postings API requires no authentication.
        return None

    async def discover_jobs(self, search_policy: dict[str, Any]) -> list[dict[str, Any]]:
        raw_postings = await self._client.list_postings()
        return [_to_common_raw_shape(raw, self.company) for raw in raw_postings]

    async def get_job_details(self, job: dict[str, Any]) -> dict[str, Any]:
        raw = await self._client.get_posting(job["external_job_id"])
        return _to_common_raw_shape(raw, self.company)

    async def normalize_job(self, raw_job: dict[str, Any]) -> NormalizedJob:
        return _normalize_job(raw_job, source=f"lever:{self.company}")

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

        raise NotImplementedError(
            "Real submission requires AUTOMATION_DRY_RUN=false, which this "
            "codebase does not implement a bypass for yet."
        )

    async def verify_submission(self) -> bool:
        return False

    async def close(self) -> None:
        if self._stack is not None:
            await self._stack.aclose()
            self._stack = None
            self._page = None
