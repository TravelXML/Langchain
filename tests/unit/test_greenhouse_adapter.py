"""Unit tests using real recorded Greenhouse API responses
(tests/fixtures/greenhouse/*.json, captured from the live public API) —
hermetic, no network dependency in the automated suite.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.portals.greenhouse.adapter import GreenhouseAdapter, _to_common_raw_shape
from app.portals.greenhouse.client import strip_html

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "greenhouse"


def _load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text())


def test_strip_html_unescapes_and_strips_tags():
    raw = "&lt;p&gt;Hello &lt;b&gt;World&lt;/b&gt;&lt;/p&gt;"
    assert strip_html(raw) == "Hello World"


def test_to_common_raw_shape_maps_real_recorded_job():
    listing = _load("jobs_list_response.json")
    raw_job = listing["jobs"][0]
    shaped = _to_common_raw_shape(raw_job, "gitlab")

    assert shaped["external_job_id"] == str(raw_job["id"])
    assert shaped["url"] == raw_job["absolute_url"]
    assert shaped["title"] == raw_job["title"]
    assert shaped["company"] == "GitLab"
    assert shaped["location"] == raw_job["location"]["name"]


def test_to_common_raw_shape_includes_clean_description_from_detail_response():
    detail = _load("job_detail_response.json")
    shaped = _to_common_raw_shape(detail, "gitlab")

    assert shaped["description"]
    assert "<" not in shaped["description"]
    assert "&lt;" not in shaped["description"]


def test_to_common_raw_shape_handles_missing_location_gracefully():
    raw_job = {"id": 1, "absolute_url": "https://x", "title": "Engineer", "company_name": "Acme"}
    shaped = _to_common_raw_shape(raw_job, "acme")
    assert shaped["location"] is None
    assert shaped["description"] == ""


class _FakeClient:
    def __init__(self, jobs: list[dict], detail: dict):
        self._jobs = jobs
        self._detail = detail

    async def list_jobs(self):
        return self._jobs

    async def get_job(self, job_id):
        return self._detail


async def test_adapter_discover_jobs_returns_common_shape():
    listing = _load("jobs_list_response.json")
    adapter = GreenhouseAdapter("gitlab")
    adapter._client = _FakeClient(listing["jobs"], {})

    discovered = await adapter.discover_jobs({})

    assert len(discovered) == len(listing["jobs"])
    assert all("external_job_id" in job for job in discovered)
    # Tagging with a source is the graph node's job, not the adapter's.
    assert all("_source" not in job for job in discovered)


async def test_adapter_get_job_details_returns_common_shape():
    detail = _load("job_detail_response.json")
    adapter = GreenhouseAdapter("gitlab")
    adapter._client = _FakeClient([], detail)

    result = await adapter.get_job_details({"external_job_id": str(detail["id"])})

    assert result["external_job_id"] == str(detail["id"])
    assert result["description"]


async def test_adapter_normalize_job_produces_normalized_job():
    listing = _load("jobs_list_response.json")
    shaped = _to_common_raw_shape(listing["jobs"][0], "gitlab")

    adapter = GreenhouseAdapter("gitlab")
    job = await adapter.normalize_job(shaped)

    assert job.source == "greenhouse:gitlab"
    assert job.title == listing["jobs"][0]["title"]
    assert job.external_job_id == str(listing["jobs"][0]["id"])


async def test_adapter_authenticate_is_a_noop():
    adapter = GreenhouseAdapter("gitlab")
    assert await adapter.authenticate() is None


async def test_submit_application_respects_dry_run_default():
    adapter = GreenhouseAdapter("gitlab")
    result = await adapter.submit_application()
    assert result == {"status": "dry_run_ready", "submitted": False}


async def test_verify_submission_returns_false_when_nothing_submitted():
    adapter = GreenhouseAdapter("gitlab")
    assert await adapter.verify_submission() is False


async def test_close_without_prepare_application_does_not_raise():
    adapter = GreenhouseAdapter("gitlab")
    await adapter.close()
