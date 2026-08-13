"""Form-intelligence schema (Section 20).

``FieldMapping`` is the structured output the spec calls for: every field
gets a candidate value (or none), a confidence, and an explicit
``requires_human`` flag — never a silent guess.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

FieldType = Literal[
    "text", "email", "tel", "number", "textarea", "select", "checkbox", "radio", "file", "unknown"
]


class DetectedField(BaseModel):
    """A form field as found on the page, before any mapping is attempted."""

    name: str  # stable identifier: name/id attribute, or a synthesized one
    label: str | None = None
    placeholder: str | None = None
    field_type: FieldType = "unknown"
    options: list[str] = Field(default_factory=list)  # select/radio choices
    required: bool = False
    selector: str  # the selector that located this field


class FieldMapping(BaseModel):
    field: str
    candidate_value: str | None
    confidence: float = Field(ge=0.0, le=1.0)
    requires_human: bool
    # "human" (Phase 6): the value came from a human answering an
    # unknown-field interrupt, not from the candidate profile directly.
    source: Literal["profile", "unmapped", "human"]
    reason: str


class FormFillResult(BaseModel):
    mappings: list[FieldMapping]
    filled: list[str] = Field(default_factory=list)
    skipped_for_human: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
