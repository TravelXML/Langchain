"""LeverClient tests — mirrors test_greenhouse_client.py. Real API
behavior already verified live in Phase 10 (tests/fixtures/lever/*.json).
"""

from __future__ import annotations

import httpx
import pytest

from app.portals.errors import PortalNavigationError, RateLimitError
from app.portals.lever.client import LeverClient


def _response(status_code: int, url: str, json_body: dict | list | None = None) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(
        status_code, json=json_body if json_body is not None else {}, request=request
    )


async def test_list_postings_success(monkeypatch):
    captured = {}

    async def fake_request(self, method, url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs.get("params")
        return _response(200, url, [{"id": "abc"}])

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = LeverClient("leverdemo")
    postings = await client.list_postings()

    assert postings == [{"id": "abc"}]
    assert captured["url"] == "https://api.lever.co/v0/postings/leverdemo"
    assert captured["params"] == {"mode": "json"}


async def test_get_posting_success(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        return _response(200, url, {"id": "abc", "text": "Engineer"})

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = LeverClient("leverdemo")
    posting = await client.get_posting("abc")
    assert posting["id"] == "abc"


async def test_list_postings_rate_limited_raises_rate_limit_error(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        return _response(429, url)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = LeverClient("leverdemo")
    with pytest.raises(RateLimitError) as exc_info:
        await client.list_postings()
    assert exc_info.value.portal == "lever:leverdemo"


async def test_get_posting_not_found_raises_portal_navigation_error(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        return _response(404, url)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    client = LeverClient("leverdemo")
    with pytest.raises(PortalNavigationError):
        await client.get_posting("does-not-exist")
