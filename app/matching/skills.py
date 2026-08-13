"""Skill matching with alias normalization (Section 16).

"AWS" / "Amazon Web Services" / "AWS Cloud" must be recognized as the same
skill. This is deliberately a hand-maintained alias table, not embedding
similarity — Phase 38 adds embeddings as an additional signal, but exact
alias resolution should never regress to fuzzy matching for well-known
terms.
"""

from __future__ import annotations

import re

from pydantic import BaseModel

# canonical name -> alias strings (lowercased at lookup time). The canonical
# name itself does not need to be repeated in its alias list.
_SKILL_ALIASES: dict[str, list[str]] = {
    "AWS": ["amazon web services", "aws cloud"],
    "GCP": ["google cloud", "google cloud platform"],
    "Azure": ["microsoft azure", "azure cloud"],
    "Kubernetes": ["k8s"],
    "Machine Learning": ["ml"],
    "Artificial Intelligence": ["ai"],
    "VP Engineering": ["vice president engineering", "vp of engineering", "vp eng"],
    "VP Technology": ["vice president technology", "vp of technology"],
    "CTO": ["chief technology officer", "chief technical officer"],
}

_ALIAS_TO_CANONICAL: dict[str, str] = {
    canonical.lower(): canonical for canonical in _SKILL_ALIASES
} | {alias: canonical for canonical, aliases in _SKILL_ALIASES.items() for alias in aliases}


def normalize_skill(skill: str) -> str:
    key = re.sub(r"\s+", " ", skill.strip().lower())
    return _ALIAS_TO_CANONICAL.get(key, skill.strip())


class SkillMatchResult(BaseModel):
    matched_required: list[str]
    missing_required: list[str]
    matched_preferred: list[str]
    missing_preferred: list[str]
    score: float

    @property
    def matched(self) -> list[str]:
        return self.matched_required + self.matched_preferred

    @property
    def missing(self) -> list[str]:
        return self.missing_required


def match_skills(
    candidate_skills: list[str],
    required_skills: list[str],
    preferred_skills: list[str],
    *,
    weight: float,
) -> SkillMatchResult:
    candidate_normalized = {normalize_skill(s) for s in candidate_skills}

    def split(job_skills: list[str]) -> tuple[list[str], list[str]]:
        matched: list[str] = []
        missing: list[str] = []
        for skill in job_skills:
            (matched if normalize_skill(skill) in candidate_normalized else missing).append(skill)
        return matched, missing

    matched_required, missing_required = split(required_skills)
    matched_preferred, missing_preferred = split(preferred_skills)

    if not required_skills and not preferred_skills:
        # The job listed no specific skills to match against — nothing to
        # penalize the candidate for, so treat this as neutral/full credit.
        score = weight
    else:
        required_ratio = len(matched_required) / len(required_skills) if required_skills else 1.0
        preferred_ratio = (
            len(matched_preferred) / len(preferred_skills) if preferred_skills else 1.0
        )
        # Required skills matter more than preferred ones.
        combined = 0.7 * required_ratio + 0.3 * preferred_ratio
        score = weight * combined

    return SkillMatchResult(
        matched_required=matched_required,
        missing_required=missing_required,
        matched_preferred=matched_preferred,
        missing_preferred=missing_preferred,
        score=round(score, 2),
    )
