"""Form-field-to-candidate-value mapping (Section 20).

Deliberately rule-based, not LLM-based — Phase 5 has no LLM available yet
(Phase 6), and per Section 2's core principle, label matching is exactly
the kind of thing a keyword pattern handles reliably without one. A future
LLM-backed classifier (Phase 6) can replace ``_match_pattern`` without
changing ``FieldMapping``'s shape or any caller.

Section 18's sensitive categories (gender, ethnicity, disability, veteran
status, religion, medical, security clearance, criminal history) have no
corresponding field anywhere in the candidate model — they always resolve
to ``requires_human=True``, never a guess, because there is structurally
nothing to guess from.
"""

from __future__ import annotations

import re
from collections.abc import Callable

from app.browser.models import DetectedField, FieldMapping
from app.core.config import get_settings
from app.profile.models import CandidateProfile

_Getter = Callable[[CandidateProfile], tuple[str | None, float]]


def _profile_field(value: str | None, confidence: float) -> tuple[str | None, float]:
    return (value, confidence) if value else (None, 0.0)


def _email(p: CandidateProfile) -> tuple[str | None, float]:
    if not p.resume:
        return (None, 0.0)
    f = p.resume.email
    return _profile_field(f.value, f.confidence)


def _phone(p: CandidateProfile) -> tuple[str | None, float]:
    if not p.resume:
        return (None, 0.0)
    f = p.resume.phone
    return _profile_field(f.value, f.confidence)


def _name(p: CandidateProfile) -> tuple[str | None, float]:
    if not p.resume:
        return (None, 0.0)
    f = p.resume.name
    return _profile_field(f.value, f.confidence)


def _current_title(p: CandidateProfile) -> tuple[str | None, float]:
    if not p.resume:
        return (None, 0.0)
    f = p.resume.current_title
    return _profile_field(f.value, f.confidence)


def _location(p: CandidateProfile) -> tuple[str | None, float]:
    if not p.resume:
        return (None, 0.0)
    f = p.resume.location
    return _profile_field(f.value, f.confidence)


def _experience_years(p: CandidateProfile) -> tuple[str | None, float]:
    if not p.resume:
        return (None, 0.0)
    f = p.resume.experience_years
    if f.value is None:
        return (None, 0.0)
    return (f"{f.value:g}", f.confidence)


def _work_authorization(p: CandidateProfile) -> tuple[str | None, float]:
    # Explicit stored answer only (Section 18) — never inferred.
    value = p.preferences.work_authorization
    return (value, 0.95) if value else (None, 0.0)


def _never_available(_: CandidateProfile) -> tuple[str | None, float]:
    return (None, 0.0)


def _work_mode(p: CandidateProfile) -> tuple[str | None, float]:
    modes = p.preferences.work_mode
    return (modes[0], 0.8) if modes else (None, 0.0)


# Order matters: first matching pattern wins. Sensitive categories are
# listed explicitly (Section 18) even though they always resolve to "no
# value" — that documents the decision rather than leaving it implicit.
_FIELD_PATTERNS: list[tuple[re.Pattern[str], _Getter, str]] = [
    (re.compile(r"\be-?mail\b", re.I), _email, "email"),
    (re.compile(r"\bphone|mobile|contact number\b", re.I), _phone, "phone"),
    (re.compile(r"\b(full |your |candidate )?name\b", re.I), _name, "name"),
    (
        re.compile(r"\byears?\s+of\s+experience|total\s+experience\b", re.I),
        _experience_years,
        "experience_years",
    ),
    (
        re.compile(r"\bcurrent\s+(job\s+)?title|current\s+role\b", re.I),
        _current_title,
        "current_title",
    ),
    (re.compile(r"\blocation|city\b", re.I), _location, "location"),
    (re.compile(r"\bwork\s+mode\b", re.I), _work_mode, "work_mode"),
    (
        re.compile(r"\bwork\s+authoriz|authorized\s+to\s+work|visa\s+sponsor", re.I),
        _work_authorization,
        "work_authorization",
    ),
    # Section 18 sensitive categories — no candidate-model field exists for
    # any of these, so they are always routed to a human.
    (re.compile(r"\bgender\b", re.I), _never_available, "gender"),
    (re.compile(r"\bethnicit|race\b", re.I), _never_available, "ethnicity"),
    (re.compile(r"\bdisabilit", re.I), _never_available, "disability"),
    (re.compile(r"\bveteran\b", re.I), _never_available, "veteran_status"),
    (re.compile(r"\breligio", re.I), _never_available, "religion"),
    (re.compile(r"\bsecurity\s+clearance\b", re.I), _never_available, "security_clearance"),
    (re.compile(r"\bcriminal\s+(history|record)\b", re.I), _never_available, "criminal_history"),
    (re.compile(r"\blinkedin\b", re.I), _never_available, "linkedin_url"),
]


def map_field(field: DetectedField, profile: CandidateProfile) -> FieldMapping:
    threshold = get_settings().form_mapping_confidence_threshold
    haystack = f"{field.label or ''} {field.placeholder or ''}".strip()

    for pattern, getter, canonical_name in _FIELD_PATTERNS:
        if pattern.search(haystack):
            value, confidence = getter(profile)
            if value is None:
                return FieldMapping(
                    field=canonical_name,
                    candidate_value=None,
                    confidence=0.0,
                    requires_human=True,
                    source="unmapped",
                    reason=f"recognized as '{canonical_name}' but no value is on file",
                )
            requires_human = confidence < threshold
            return FieldMapping(
                field=canonical_name,
                candidate_value=value,
                confidence=confidence,
                requires_human=requires_human,
                source="profile",
                reason=(
                    "matched from candidate profile"
                    if not requires_human
                    else f"confidence {confidence:.2f} is below threshold {threshold:.2f}"
                ),
            )

    return FieldMapping(
        field=field.name,
        candidate_value=None,
        confidence=0.0,
        requires_human=True,
        source="unmapped",
        reason="no known field pattern matched this label/placeholder",
    )


def map_fields(fields: list[DetectedField], profile: CandidateProfile) -> list[FieldMapping]:
    return [map_field(f, profile) for f in fields]
