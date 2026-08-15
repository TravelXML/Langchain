"""Portal-adapter exceptions (Section 40's portal-specific subset —
the follow-through on `app/browser/errors.py`'s Phase 5 promise).
"""

from __future__ import annotations

from app.core.errors import JobAutomationError


class PortalAuthenticationError(JobAutomationError):
    """A portal rejected or requires credentials this adapter doesn't
    have. Not currently raised — Greenhouse and Lever's public Job
    Board/Postings APIs both require no authentication at all
    (`authenticate()` is a no-op on both adapters). Exists for a future
    portal that does require it.
    """


class PortalNavigationError(JobAutomationError):
    """A portal's API or a job's application page could not be reached
    — a network failure, timeout, or non-2xx response that isn't a rate
    limit (see `RateLimitError`). Raised by `app.portals.greenhouse.client`
    and `app.portals.lever.client` when their real HTTP calls fail.
    """


class RateLimitError(JobAutomationError):
    """A portal responded 429. Raised by `app.portals.greenhouse.client`
    and `app.portals.lever.client` — distinguished from
    `PortalNavigationError` specifically so a caller can choose to back
    off and retry rather than treating it as a hard failure, without
    this codebase actually implementing that retry policy itself yet.
    """
