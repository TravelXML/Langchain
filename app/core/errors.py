"""Central error handling (Section 40).

`app/browser/errors.py`'s docstring (Phase 5) promised "full portal/
application exceptions land in Phase 7 once there's a real portal to
raise them against" — Phase 7 shipped Greenhouse without them. This
module is that follow-through: one shared base every error type in the
codebase (browser-, LLM-, and portal/application-level) now inherits
from, carrying exactly the context Section 40 asks for.

Every exception here captures the same structured context — url,
portal, job_id, run_id, screenshot_path, step, occurred_at — so any
catcher (a graph node, an API route, the CLI) can log or persist a
uniform shape regardless of which specific error fired, via
``.to_dict()``. Deliberately excludes anything credential-shaped: no
field here is ever a password/token/cookie/API key, and `url` has its
query string stripped in `to_dict()` specifically because a query string
is the most common accidental place a secret leaks into a URL — none of
this codebase's own captured URLs need one to be useful for debugging.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit


def _strip_query(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


class JobAutomationError(Exception):
    """Base class for every structured error this app raises
    deliberately (as opposed to a third-party library's own exception
    type propagating unwrapped)."""

    def __init__(
        self,
        message: str,
        *,
        url: str | None = None,
        portal: str | None = None,
        job_id: str | None = None,
        run_id: str | None = None,
        screenshot_path: str | None = None,
        step: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.url = url
        self.portal = portal
        self.job_id = job_id
        self.run_id = run_id
        self.screenshot_path = screenshot_path
        self.step = step
        self.occurred_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_type": type(self).__name__,
            "message": self.message,
            "url": _strip_query(self.url),
            "portal": self.portal,
            "job_id": self.job_id,
            "run_id": self.run_id,
            "screenshot": self.screenshot_path,
            "step": self.step,
            "timestamp": self.occurred_at.isoformat(),
        }


class ApplicationValidationError(JobAutomationError):
    """An application's field mappings/values fail validation at a level
    above a single form field (`app/browser/errors.py`'s
    `FormValidationError` is the field-level counterpart). Not currently
    raised anywhere — the apply graph's own design deliberately treats
    invalid fields as a warning + human review rather than a hard
    failure (`apply_nodes.fill_and_validate_node`); available for a
    future caller that wants strict behavior instead.
    """


class DuplicateApplicationError(JobAutomationError):
    """An application already exists for this job (Section 50: "before
    submitting, check existing application"). Raised by
    `app.graph.apply_service.start_application` — see that module."""


class SubmissionVerificationError(JobAutomationError):
    """A submission's success could not be confirmed (Section 50: "never
    assume a button click means submission succeeded"). Not currently
    raised anywhere — every portal adapter's `submit_application()`
    returns `dry_run_ready` or raises `NotImplementedError` today, since
    `AUTOMATION_DRY_RUN=true` is enforced everywhere and no code path in
    this repository actually submits anything yet. This exists for the
    real-submission path whenever that's built.
    """


class HumanActionRequired(JobAutomationError):
    """A step needs a human decision. Not raised anywhere in the graph
    paths — `interrupt()` (Section 19, `app/graph/apply_nodes.py`)
    already solves this properly (pausing with checkpointed state a
    human can resume later), which a plain exception cannot do. This
    exists only for a portal adapter used directly, outside the apply
    graph's interrupt wiring — not a path this codebase exercises today.
    """
