"""Shared Pydantic schemas for the LLM subsystem (Section 39: "All LLM
output must prefer structured Pydantic schemas")."""

from __future__ import annotations

from pydantic import BaseModel


class LLMHealthStatus(BaseModel):
    """Result of the four startup checks Section 36 requires. Never
    raised — `app.llm.health.check_llm_health` always returns one of
    these, healthy or not, so a caller can log it and move on rather than
    handling an exception.
    """

    reachable: bool
    model_exists: bool
    returns_valid_json: bool
    structured_output_valid: bool
    checked_model: str
    error: str | None = None

    @property
    def healthy(self) -> bool:
        return (
            self.reachable
            and self.model_exists
            and self.returns_valid_json
            and self.structured_output_valid
        )


class _JSONCapabilityProbe(BaseModel):
    """Minimal schema used only by the health check's "does structured
    output pass validation?" step — not a domain model."""

    ok: bool
