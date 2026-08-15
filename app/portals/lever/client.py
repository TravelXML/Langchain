"""Client for Lever's public Postings API.

Read-only, unauthenticated, and officially public — every company running
their careers page on Lever exposes
``https://api.lever.co/v0/postings/<company>?mode=json`` for exactly this
purpose (the same embed feed ``jobs.lever.co/<company>`` itself renders
from). Verified live against Lever's own public demo board
(``leverdemo``) — see ``tests/fixtures/lever/`` for real captured
responses. Section 12's "prefer official/public APIs when available"
path, same as ``app/portals/greenhouse/client.py``.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.portals import http as portal_http

_BASE_URL = "https://api.lever.co/v0/postings"


class LeverClient:
    def __init__(self, company: str, *, timeout: float = 15.0) -> None:
        self.company = company
        self._timeout = timeout
        self._portal_id = f"lever:{company}"

    async def list_postings(self) -> list[dict[str, Any]]:
        url = f"{_BASE_URL}/{self.company}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await portal_http.request(
                client,
                "GET",
                url,
                portal=self._portal_id,
                step="list_postings",
                params={"mode": "json"},
            )
            result: list[dict[str, Any]] = response.json()
            return result

    async def get_posting(self, posting_id: str) -> dict[str, Any]:
        url = f"{_BASE_URL}/{self.company}/{posting_id}"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await portal_http.request(
                client,
                "GET",
                url,
                portal=self._portal_id,
                step="get_posting",
                params={"mode": "json"},
            )
            result: dict[str, Any] = response.json()
            return result
