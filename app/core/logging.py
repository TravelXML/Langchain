"""Structured logging setup.

All logs are JSON by default so later phases (audit trail, observability)
can rely on machine-parseable output. A contextvar-backed correlation id is
bound once per request/run and automatically merged into every log line
without threading it through every function signature.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

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


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
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
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


def bind_correlation_id(correlation_id: str, **extra: Any) -> None:
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id, **extra)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()
