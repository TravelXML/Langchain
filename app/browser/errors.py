"""Browser-automation exceptions (Section 40's browser-specific subset).

The full portal/application hierarchy this docstring originally
promised for "Phase 7" now lives in `app/core/errors.py` (base) and
`app/portals/errors.py` (portal-specific) — built later than planned,
see the README's "Notes for contributors". These are the ones Phase 5's
form engine needs, now subclassing that shared base so every exception
in the codebase carries the same structured context.
"""

from __future__ import annotations

from app.core.errors import JobAutomationError


class BrowserAutomationError(JobAutomationError):
    """Base class for all app.browser errors."""


class SelectorNotFoundError(BrowserAutomationError):
    """No selector strategy located the target element."""


class FormValidationError(BrowserAutomationError):
    """The form failed validation after filling (required fields, HTML5
    constraints, etc.)."""


class FileUploadError(BrowserAutomationError):
    """A file input could not be set."""
