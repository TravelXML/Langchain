"""LLM-specific exceptions (Section 40's `LLMUnavailableError`/
`LLMValidationError`, scoped to `app/llm/` since that's the only place
that raises them).

Every caller of this package must be prepared to catch these and degrade
gracefully (Section 36: "disable semantic functionality gracefully, DO
NOT crash entire application") — none of this package's failures are
allowed to propagate as an unhandled exception into a graph node or API
route.

Both subclass the shared `JobAutomationError` (`app/core/errors.py`) —
existing call sites are unaffected (every context field is optional,
keyword-only), but a caller that wants it now gets the same `.to_dict()`
shape every other error in the codebase does.
"""

from __future__ import annotations

from app.core.errors import JobAutomationError


class LLMUnavailableError(JobAutomationError):
    """Ollama (or the configured fallback) could not be reached, or the
    configured model doesn't exist on it."""


class LLMValidationError(JobAutomationError):
    """The model responded, but its output wasn't valid JSON or didn't
    validate against the requested Pydantic schema."""
