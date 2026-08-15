"""Tests for the shared portal-HTTP-error translation (app/portals/http.py)."""

from __future__ import annotations

import httpx
import pytest

from app.portals import http as portal_http
from app.portals.errors import PortalNavigationError, RateLimitError


def _response(status_code: int, url: str) -> httpx.Response:
    request = httpx.Request("GET", url)
    return httpx.Response(status_code, json={}, request=request)


async def test_request_returns_response_on_success(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        return _response(200, url)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    async with httpx.AsyncClient() as client:
        response = await portal_http.request(
            client, "GET", "https://api.example.com/jobs", portal="acme", step="list_jobs"
        )
    assert response.status_code == 200


async def test_request_429_raises_rate_limit_error(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        return _response(429, url)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    async with httpx.AsyncClient() as client:
        with pytest.raises(RateLimitError) as exc_info:
            await portal_http.request(
                client, "GET", "https://api.example.com/jobs", portal="acme", step="list_jobs"
            )
    exc = exc_info.value
    assert exc.portal == "acme"
    assert exc.step == "list_jobs"
    assert exc.url == "https://api.example.com/jobs"


async def test_request_other_4xx_raises_portal_navigation_error(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        return _response(404, url)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    async with httpx.AsyncClient() as client:
        with pytest.raises(PortalNavigationError) as exc_info:
            await portal_http.request(
                client, "GET", "https://api.example.com/jobs", portal="acme", step="get_job"
            )
    assert exc_info.value.portal == "acme"


async def test_request_500_raises_portal_navigation_error(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        return _response(500, url)

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    async with httpx.AsyncClient() as client:
        with pytest.raises(PortalNavigationError):
            await portal_http.request(
                client, "GET", "https://api.example.com/jobs", portal="acme", step="list_jobs"
            )


async def test_request_connection_error_raises_portal_navigation_error(monkeypatch):
    async def fake_request(self, method, url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx.AsyncClient, "request", fake_request)

    async with httpx.AsyncClient() as client:
        with pytest.raises(PortalNavigationError) as exc_info:
            await portal_http.request(
                client, "GET", "https://api.example.com/jobs", portal="acme", step="list_jobs"
            )
    assert "acme" in str(exc_info.value)
