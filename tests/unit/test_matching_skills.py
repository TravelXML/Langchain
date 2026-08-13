from __future__ import annotations

from app.matching.skills import match_skills, normalize_skill


def test_normalize_skill_resolves_known_alias():
    assert normalize_skill("Amazon Web Services") == "AWS"
    assert normalize_skill("aws cloud") == "AWS"
    assert normalize_skill("k8s") == "Kubernetes"


def test_normalize_skill_passes_through_unknown_skill():
    assert normalize_skill("Terraform") == "Terraform"


def test_all_required_and_preferred_matched_scores_full_weight():
    result = match_skills(
        ["Python", "AWS", "Kubernetes"],
        required_skills=["Python", "AWS"],
        preferred_skills=["Kubernetes"],
        weight=30,
    )
    assert result.score == 30
    assert result.missing_required == []


def test_alias_match_counts_as_matched():
    result = match_skills(
        ["Amazon Web Services"],
        required_skills=["AWS"],
        preferred_skills=[],
        weight=30,
    )
    assert "AWS" in result.matched_required


def test_missing_required_skill_reduces_score():
    result = match_skills(
        ["Python"],
        required_skills=["Python", "AWS"],
        preferred_skills=[],
        weight=30,
    )
    assert result.missing_required == ["AWS"]
    assert 0 < result.score < 30


def test_no_required_or_preferred_skills_is_neutral():
    result = match_skills(["Python"], required_skills=[], preferred_skills=[], weight=30)
    assert result.score == 30


def test_no_matching_skills_scores_zero():
    result = match_skills(["COBOL"], required_skills=["Python"], preferred_skills=["Go"], weight=30)
    assert result.score == 0
    assert result.missing_required == ["Python"]


def test_no_matching_required_but_no_preferred_stated_gets_partial_credit():
    # Nothing was asked for on the "preferred" side, so that portion of the
    # weighted score is trivially satisfied even though required skills
    # were completely missed — only the required 70% share is lost.
    result = match_skills(["COBOL"], required_skills=["Python"], preferred_skills=[], weight=30)
    assert result.score == 9.0


def test_required_skills_weighted_more_than_preferred():
    all_required_missing = match_skills(
        ["Kubernetes"], required_skills=["Python"], preferred_skills=["Kubernetes"], weight=30
    )
    all_preferred_missing = match_skills(
        ["Python"], required_skills=["Python"], preferred_skills=["Kubernetes"], weight=30
    )
    assert all_preferred_missing.score > all_required_missing.score
