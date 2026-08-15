"""Shared httpx-error-to-portal-error translation (Section 40) — every
real portal client (`greenhouse/client.py`, `lever/client.py`) routes
its requests through this so the translation logic exists exactly once,
not once per portal.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.portals.errors import PortalNavigationError, RateLimitError


async def request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    portal: str,
    step: str,
    **kwargs: Any,
) -> httpx.Response:
    try:
        response = await client.request(method, url, **kwargs)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise RateLimitError(
                f"{portal} rate-limited this request ({step})",
                url=url,
                portal=portal,
                step=step,
            ) from exc
        raise PortalNavigationError(
            f"{portal} returned {exc.response.status_code} ({step})",
            url=url,
            portal=portal,
            step=step,
        ) from exc
    except httpx.HTTPError as exc:
        raise PortalNavigationError(
            f"could not reach {portal} ({step}): {exc}",
            url=url,
            portal=portal,
            step=step,
        ) from exc
    return response
