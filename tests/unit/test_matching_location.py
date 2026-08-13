from __future__ import annotations

from app.matching.location import score_location


def test_remote_job_remote_candidate_scores_full_weight():
    score = score_location(
        None,
        "remote",
        preferred_locations=["Bengaluru"],
        preferred_work_modes=["remote"],
        relocation_allowed=False,
        weight=10,
    )
    assert score == 10


def test_hybrid_with_matching_location_scores_full_weight():
    score = score_location(
        "Bengaluru, India",
        "hybrid",
        preferred_locations=["Bengaluru"],
        preferred_work_modes=["hybrid"],
        relocation_allowed=False,
        weight=10,
    )
    assert score == 10


def test_onsite_no_match_no_relocation_scores_low():
    score = score_location(
        "Berlin",
        "onsite",
        preferred_locations=["Bengaluru"],
        preferred_work_modes=["remote"],
        relocation_allowed=False,
        weight=10,
    )
    assert score == 1.0


def test_onsite_no_match_but_relocation_allowed_scores_moderately():
    score = score_location(
        "Bengaluru",
        "onsite",
        preferred_locations=["Bengaluru"],
        preferred_work_modes=["remote"],
        relocation_allowed=True,
        weight=10,
    )
    assert score == 5.0


def test_hybrid_wrong_location_no_relocation_scores_low():
    score = score_location(
        "Berlin",
        "hybrid",
        preferred_locations=["Bengaluru"],
        preferred_work_modes=["hybrid"],
        relocation_allowed=False,
        weight=10,
    )
    assert score == 2.0


def test_hybrid_wrong_location_with_relocation_scores_partial():
    score = score_location(
        "Berlin",
        "hybrid",
        preferred_locations=["Bengaluru"],
        preferred_work_modes=["hybrid"],
        relocation_allowed=True,
        weight=10,
    )
    assert score == 6.0


def test_unknown_work_mode_falls_back_to_location_match():
    matched = score_location(
        "Bengaluru",
        None,
        preferred_locations=["Bengaluru"],
        preferred_work_modes=["remote"],
        relocation_allowed=False,
        weight=10,
    )
    unmatched = score_location(
        "Berlin",
        None,
        preferred_locations=["Bengaluru"],
        preferred_work_modes=["remote"],
        relocation_allowed=False,
        weight=10,
    )
    assert matched == 10
    assert unmatched == 5.0
