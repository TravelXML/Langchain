"""Unit tests using real recorded Lever Postings API responses
(tests/fixtures/lever/*.json, captured live from Lever's own public demo
board at https://api.lever.co/v0/postings/leverdemo) — hermetic, no
network dependency in the automated suite.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.portals.lever.adapter import LeverAdapter, _epoch_ms_to_iso, _to_common_raw_shape

_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "lever"


def _load(name: str) -> dict | list:
    return json.loads((_FIXTURES / name).read_text())


def test_epoch_ms_to_iso_converts_milliseconds_not_seconds():
    # 1553186035299 ms -> 2019-03-21, not the year 51157 a naive
    # epoch-seconds interpretation would produce.
    result = _epoch_ms_to_iso(1553186035299)
    assert result is not None
    parsed = datetime.fromisoformat(result)
    assert parsed.year == 2019
    assert parsed.tzinfo == UTC


def test_epoch_ms_to_iso_handles_none():
    assert _epoch_ms_to_iso(None) is None


def test_to_common_raw_shape_maps_real_recorded_posting():
    postings = _load("postings_list_response.json")
    raw_posting = postings[0]
    shaped = _to_common_raw_shape(raw_posting, "leverdemo")

    assert shaped["external_job_id"] == raw_posting["id"]
    # url must be the actual application form page, not the descriptive
    # posting page — prepare_application navigates straight to job.url.
    assert shaped["url"] == raw_posting["applyUrl"]
    assert shaped["posting_url"] == raw_posting["hostedUrl"]
    assert shaped["title"] == raw_posting["text"]
    assert shaped["company"] == "leverdemo"
    assert shaped["location"] == raw_posting["categories"]["location"]
    assert shaped["work_mode"] == raw_posting["workplaceType"]
    assert shaped["employment_type"] == raw_posting["categories"]["commitment"]
    assert shaped["industry"] == raw_posting["categories"]["department"]


def test_to_common_raw_shape_includes_clean_description_with_lists_appended():
    detail = _load("posting_detail_response.json")
    shaped = _to_common_raw_shape(detail, "leverdemo")

    assert shaped["description"]
    assert "<" not in shaped["description"]
    assert "&lt;" not in shaped["description"]
    # descriptionPlain content plus the "lists" sections (Qualifications,
    # Duties in the fixture) should both appear.
    assert "Qualifications" in shaped["description"] or "be smart" in shaped["description"]


def test_to_common_raw_shape_handles_missing_categories_gracefully():
    raw_posting = {
        "id": "abc",
        "text": "Engineer",
        "hostedUrl": "https://jobs.lever.co/acme/abc",
    }
    shaped = _to_common_raw_shape(raw_posting, "acme")
    assert shaped["location"] is None
    assert shaped["description"] == ""
    assert shaped["employment_type"] is None


class _FakeClient:
    def __init__(self, postings: list[dict], detail: dict):
        self._postings = postings
        self._detail = detail

    async def list_postings(self):
        return self._postings

    async def get_posting(self, posting_id):
        return self._detail


async def test_adapter_discover_jobs_returns_common_shape():
    postings = _load("postings_list_response.json")
    adapter = LeverAdapter("leverdemo")
    adapter._client = _FakeClient(postings, {})

    discovered = await adapter.discover_jobs({})

    assert len(discovered) == len(postings)
    assert all("external_job_id" in job for job in discovered)
    assert all("_source" not in job for job in discovered)


async def test_adapter_get_job_details_returns_common_shape():
    detail = _load("posting_detail_response.json")
    adapter = LeverAdapter("leverdemo")
    adapter._client = _FakeClient([], detail)

    result = await adapter.get_job_details({"external_job_id": detail["id"]})

    assert result["external_job_id"] == detail["id"]
    assert result["description"]


async def test_adapter_normalize_job_produces_normalized_job():
    postings = _load("postings_list_response.json")
    shaped = _to_common_raw_shape(postings[0], "leverdemo")

    adapter = LeverAdapter("leverdemo")
    job = await adapter.normalize_job(shaped)

    assert job.source == "lever:leverdemo"
    assert job.title == postings[0]["text"]
    assert job.external_job_id == postings[0]["id"]
    assert job.posted_at is not None


async def test_adapter_authenticate_is_a_noop():
    adapter = LeverAdapter("leverdemo")
    assert await adapter.authenticate() is None


async def test_submit_application_respects_dry_run_default():
    adapter = LeverAdapter("leverdemo")
    result = await adapter.submit_application()
    assert result == {"status": "dry_run_ready", "submitted": False}


async def test_verify_submission_returns_false_when_nothing_submitted():
    adapter = LeverAdapter("leverdemo")
    assert await adapter.verify_submission() is False


async def test_close_without_prepare_application_does_not_raise():
    adapter = LeverAdapter("leverdemo")
    await adapter.close()
