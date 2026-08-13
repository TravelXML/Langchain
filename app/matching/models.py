"""Matching engine schema and configuration (Section 15).

Weights and thresholds are never hardcoded — they're loaded from
``config/scoring.yaml`` (see ``load_scoring_weights``/``load_scoring_thresholds``)
so they're editable without touching Python.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import get_yaml_config_loader

Recommendation = Literal[
    "priority_apply", "normal_apply", "apply_if_capacity", "human_review", "reject"
]


class ScoringWeights(BaseModel):
    title: float = 25
    skills: float = 30
    experience: float = 15
    industry: float = 10
    location: float = 10
    compensation: float = 10

    @classmethod
    def from_yaml(cls, raw: dict) -> ScoringWeights:
        weights = raw.get("scoring", {}).get("weights", {})
        return cls(**weights) if weights else cls()


class ScoringThresholds(BaseModel):
    priority_apply: float = 90
    normal_apply: float = 80
    apply_if_capacity: float = 75
    human_review: float = 60

    @classmethod
    def from_yaml(cls, raw: dict) -> ScoringThresholds:
        thresholds = raw.get("scoring", {}).get("thresholds", {})
        return cls(**thresholds) if thresholds else cls()

    def recommendation_for(self, score: float) -> Recommendation:
        if score >= self.priority_apply:
            return "priority_apply"
        if score >= self.normal_apply:
            return "normal_apply"
        if score >= self.apply_if_capacity:
            return "apply_if_capacity"
        if score >= self.human_review:
            return "human_review"
        return "reject"


def load_scoring_weights() -> ScoringWeights:
    return ScoringWeights.from_yaml(get_yaml_config_loader().load("scoring"))


def load_scoring_thresholds() -> ScoringThresholds:
    return ScoringThresholds.from_yaml(get_yaml_config_loader().load("scoring"))


class ScoreBreakdown(BaseModel):
    title: float
    skills: float
    experience: float
    industry: float
    location: float
    compensation: float


class MatchResult(BaseModel):
    overall_score: float
    breakdown: ScoreBreakdown
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    reason: str
    recommendation: Recommendation
