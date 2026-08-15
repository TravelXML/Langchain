"""GreenhouseClient tests — confirms it routes through the shared
portal_http.request() translation (Section 40) with the right URL/portal
id, using mocked HTTP (real API behavior already verified live in
Phase 7 — tests/fixtures/greenhouse/*.json).
"""

from __future__ import annotations

import httpx
import pytest

from app.portals.errors import PortalNavigationError, RateLimitError
from app.portals.greenhouse.client import GreenhouseClient


def _response(status_code: int, url: str, json_body: dict | list | None = None) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(
        status_code, json=json_body if json_body is not None else {}, request=request
    )


async def test_list_jobs_success(monkeypatch):
    captured = {}

    async def fake_request(self, method, url, **kwargs):
        captured["url"] = url
        return _response(200, url, {"jobs": [{"id": 1}]})

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = GreenhouseClient("gitlab")
    jobs = await client.list_jobs()

    assert jobs == [{"id": 1}]
    assert captured["url"] == "https://boards-api.greenhouse.io/v1/boards/gitlab/jobs"


async def test_get_job_success(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        return _response(200, url, {"id": 42, "title": "Engineer"})

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = GreenhouseClient("gitlab")
    job = await client.get_job(42)
    assert job["id"] == 42


async def test_list_jobs_rate_limited_raises_rate_limit_error(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        return _response(429, url)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = GreenhouseClient("gitlab")
    with pytest.raises(RateLimitError) as exc_info:
        await client.list_jobs()
    assert exc_info.value.portal == "greenhouse:gitlab"


async def test_get_job_not_found_raises_portal_navigation_error(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        return _response(404, url)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = GreenhouseClient("gitlab")
    with pytest.raises(PortalNavigationError):
        await client.get_job(999999)
