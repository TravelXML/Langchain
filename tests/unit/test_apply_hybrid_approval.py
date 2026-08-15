"""Tests for hybrid approval mode's auto-approve carve-out (Section 48),
the gap Phase 6's `manual_approval_node` docstring explicitly flagged as
unimplemented ("Phase 6 doesn't yet implement hybrid's score/confidence
auto-approval carve-out") and left for later.
"""

from __future__ import annotations

from app.browser.models import FieldMapping
from app.graph.apply_nodes import _hybrid_auto_approves

_DEFAULT_CONFIG = {"hybrid_min_score": 90, "hybrid_min_confidence": 0.85}


def _mapping(field: str, *, confidence: float, requires_human: bool = False) -> FieldMapping:
    return FieldMapping(
        field=field,
        candidate_value="x" if not requires_human else None,
        confidence=confidence,
        requires_human=requires_human,
        source="profile" if not requires_human else "unmapped",
        reason="test",
    )


def test_high_score_high_confidence_no_human_fields_auto_approves():
    state = {
        "match_score": 95.0,
        "field_mappings": [_mapping("email", confidence=0.95), _mapping("name", confidence=0.9)],
    }
    assert _hybrid_auto_approves(state, _DEFAULT_CONFIG) is True


def test_missing_match_score_never_auto_approves():
    state = {
        "match_score": None,
        "field_mappings": [_mapping("email", confidence=0.99)],
    }
    assert _hybrid_auto_approves(state, _DEFAULT_CONFIG) is False


def test_low_score_does_not_auto_approve():
    state = {
        "match_score": 70.0,
        "field_mappings": [_mapping("email", confidence=0.99)],
    }
    assert _hybrid_auto_approves(state, _DEFAULT_CONFIG) is False


def test_any_field_requiring_human_blocks_auto_approve_even_with_high_score():
    state = {
        "match_score": 99.0,
        "field_mappings": [
            _mapping("email", confidence=0.99),
            _mapping("linkedin_url", confidence=0.0, requires_human=True),
        ],
    }
    assert _hybrid_auto_approves(state, _DEFAULT_CONFIG) is False


def test_low_average_confidence_does_not_auto_approve():
    state = {
        "match_score": 95.0,
        "field_mappings": [_mapping("email", confidence=0.5), _mapping("name", confidence=0.4)],
    }
    assert _hybrid_auto_approves(state, _DEFAULT_CONFIG) is False


def test_no_field_mappings_at_all_does_not_auto_approve():
    state = {"match_score": 95.0, "field_mappings": []}
    assert _hybrid_auto_approves(state, _DEFAULT_CONFIG) is False


def test_thresholds_are_configurable():
    state = {
        "match_score": 80.0,
        "field_mappings": [_mapping("email", confidence=0.7)],
    }
    lenient_config = {"hybrid_min_score": 75, "hybrid_min_confidence": 0.6}
    assert _hybrid_auto_approves(state, lenient_config) is True
    assert _hybrid_auto_approves(state, _DEFAULT_CONFIG) is False


def test_score_exactly_at_threshold_is_inclusive():
    state = {
        "match_score": 90.0,
        "field_mappings": [_mapping("email", confidence=0.85)],
    }
    assert _hybrid_auto_approves(state, _DEFAULT_CONFIG) is True
