from __future__ import annotations

from app.matching.experience import score_experience


def test_no_requirement_scores_full_weight():
    assert score_experience(3, None, None, weight=15) == 15


def test_meets_minimum_scores_full_weight():
    assert score_experience(12, 10, None, weight=15) == 15


def test_below_minimum_scores_proportionally():
    score = score_experience(5, 10, None, weight=15)
    assert 0 < score < 15


def test_unknown_candidate_experience_gets_partial_credit():
    assert score_experience(None, 10, None, weight=15) == 7.5


def test_significantly_overqualified_gets_mild_penalty():
    score = score_experience(30, None, 10, weight=15)
    assert score == 12.0


def test_moderately_over_max_is_not_penalized():
    # 12 years against a 10-year cap is not "significantly" over (< 1.5x).
    assert score_experience(12, None, 10, weight=15) == 15


def test_zero_years_against_any_minimum_scores_zero():
    assert score_experience(0, 10, None, weight=15) == 0
