"""Client for Greenhouse's public Job Board API.

Read-only, unauthenticated, and officially public — every company running
their careers page on Greenhouse exposes
``https://boards-api.greenhouse.io/v1/boards/<token>/jobs`` for exactly
this purpose. This is the "prefer official/public APIs when available"
path (Section 12); nothing here scrapes HTML or touches a real
application form — that only happens later, in the browser, driven by the
candidate's own automation (``app/browser/``, Phases 5-6).
"""

from __future__ import annotations

from typing import Any

import httpx

from app.portals import http as portal_http
from app.portals.html import strip_html

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards"

__all__ = ["GreenhouseClient", "strip_html"]


class GreenhouseClient:
    def __init__(self, board_token: str, *, timeout: float = 15.0) -> None:
        self.board_token = board_token
        self._timeout = timeout
        self._portal_id = f"greenhouse:{board_token}"

    async def list_jobs(self) -> list[dict[str, Any]]:
        url = f"{_BASE_URL}/{self.board_token}/jobs"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await portal_http.request(
                client, "GET", url, portal=self._portal_id, step="list_jobs"
            )
            data: dict[str, Any] = response.json()
            return data.get("jobs", [])

    async def get_job(self, job_id: int | str) -> dict[str, Any]:
        url = f"{_BASE_URL}/{self.board_token}/jobs/{job_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await portal_http.request(
                client,
                "GET",
                url,
                portal=self._portal_id,
                step="get_job",
                params={"questions": "true"},
            )
            result: dict[str, Any] = response.json()
            return result
