from __future__ import annotations

from app.matching.title import match_title


def test_exact_family_match_scores_full_weight():
    result = match_title(["CTO"], "CTO", weight=25)
    assert result.score == 25
    assert result.matched_family == "CTO"


def test_synonym_within_same_family_scores_full_weight():
    result = match_title(["CTO"], "Chief Technology Officer", weight=25)
    assert result.score == 25
    assert result.matched_family == "CTO"


def test_different_target_synonym_still_matches_family():
    result = match_title(["Chief Technical Officer"], "Head of Technology", weight=25)
    assert result.score == 25


def test_unrelated_title_scores_zero():
    result = match_title(["CTO"], "Marketing Intern", weight=25)
    assert result.score == 0.0


def test_no_target_positions_is_neutral():
    result = match_title([], "Random Title", weight=25)
    assert result.score == 25


def test_partial_token_overlap_gives_partial_credit():
    result = match_title(["Senior Backend Engineer"], "Backend Engineer", weight=25)
    assert 0 < result.score < 25


def test_multiple_targets_picks_best_match():
    result = match_title(["Marketing Manager", "CTO"], "Chief Technical Officer", weight=25)
    assert result.score == 25
    assert result.matched_target == "CTO"
