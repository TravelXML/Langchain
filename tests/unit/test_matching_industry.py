from __future__ import annotations

from app.matching.industry import score_industry


def test_matching_industry_scores_full_weight():
    assert score_industry("SaaS", ["SaaS", "TravelTech"], weight=10) == 10


def test_substring_match_counts():
    assert score_industry("Enterprise SaaS Platforms", ["SaaS"], weight=10) == 10


def test_non_matching_industry_scores_low():
    assert score_industry("Healthcare", ["SaaS", "TravelTech"], weight=10) == 2.0


def test_unknown_job_industry_gets_mild_credit():
    assert score_industry(None, ["SaaS"], weight=10) == 7.0


def test_no_preference_is_neutral():
    assert score_industry("Healthcare", [], weight=10) == 10
