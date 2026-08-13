from __future__ import annotations

from app.matching.salary import score_salary


def test_no_salary_disclosed_is_neutral():
    assert score_salary(None, None, None, 30, 50, "INR", weight=10) == 10


def test_meets_preferred_scores_full_weight():
    assert score_salary(None, 60, "INR", 30, 50, "INR", weight=10) == 10


def test_between_minimum_and_preferred_scores_partial():
    score = score_salary(None, 40, "INR", 30, 50, "INR", weight=10)
    assert 6 <= score < 10


def test_below_minimum_scores_low():
    score = score_salary(None, 15, "INR", 30, 50, "INR", weight=10)
    assert 0 <= score < 6


def test_currency_mismatch_is_neutral_not_penalized():
    assert score_salary(None, 60, "USD", 30, 50, "INR", weight=10) == 5


def test_no_candidate_minimum_stated_scores_full_weight():
    assert score_salary(None, 40, "INR", 0, 0, "INR", weight=10) == 10


def test_uses_salary_max_over_min_when_both_present():
    score = score_salary(20, 60, "INR", 30, 50, "INR", weight=10)
    assert score == 10
