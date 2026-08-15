"""Structured logging setup.

All logs are JSON by default so later phases (audit trail, observability)
can rely on machine-parseable output. A contextvar-backed correlation id is
bound once per request/run and automatically merged into every log line
without threading it through every function signature.
"""

from __future__ import annotations

import logging
import sys
from typing import Any, TextIO

import structlog

from app.core.config import Settings

_SENSITIVE_KEYS = {
    "password",
    "otp",
    "token",
    "authorization",
    "cookie",
    "session_token",
    "api_key",
    "secret",
}


def _redact_sensitive(
    _logger: Any, _method_name: str, event_dict: dict[str, Any]
) -> dict[str, Any]:
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "***REDACTED***"
    return event_dict


def configure_logging(settings: Settings, *, stream: TextIO = sys.stdout) -> None:
    """`stream` defaults to stdout (the server's own logs are its whole
    output, nothing else parses it). `app/cli/main.py` passes stderr
    instead — a CLI's stdout is a human or a script's parseable product
    output (JSON, status text), and log lines mixed into it would
    silently break that, exactly as `tests/integration/test_cli.py`
    caught when a notification's console log line landed inside what was
    supposed to be a clean JSON response body.
    """
    logging.basicConfig(
        format="%(message)s",
        stream=stream,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        _redact_sensitive,
    ]

    renderer: Any
    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(stream),
        # Deliberately not cached: a module-level `logger = get_logger(...)`
        # (the pattern used throughout this codebase) would otherwise
        # freeze its resolved output stream the *first* time it logs
        # anything and keep using it even after a later
        # `configure_logging()` call points elsewhere — exactly what
        # happens every time `app/cli/main.py`'s startup callback runs
        # (once per invocation, by design). The negligible per-call
        # re-resolution cost is the right trade for a local, human-paced
        # tool; a stale, possibly-closed stream reference in a
        # correctness-sensitive log path is not.
        cache_logger_on_first_use=False,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_correlation_id(correlation_id: str, **extra: Any) -> None:
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id, **extra)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()
