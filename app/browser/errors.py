"""Browser-automation exceptions (Section 40's browser-specific subset).

Full portal/application exceptions (PortalAuthenticationError,
SubmissionVerificationError, ...) land in Phase 7 once there's a real
portal to raise them against — these are the ones Phase 5's form engine
needs today.
"""

from __future__ import annotations


class BrowserAutomationError(Exception):
    """Base class for all app.browser errors."""


class SelectorNotFoundError(BrowserAutomationError):
    """No selector strategy located the target element."""


class FormValidationError(BrowserAutomationError):
    """The form failed validation after filling (required fields, HTML5
    constraints, etc.)."""


class FileUploadError(BrowserAutomationError):
    """A file input could not be set."""
