"""Deterministic resume text parser.

Phase 1 has no LLM available yet (Ollama integration is Phase 6), and per
the platform's core design principle an LLM should never be used where a
deterministic rule can safely produce the result. So this parser only
populates fields it can extract with a defensible rule: regex for
email/phone/years-of-experience, section-header scanning for
education/certifications/languages/achievements, and vocabulary matching
for skills.

Fields that genuinely require semantic understanding to extract reliably
(previous job titles, companies, industries) are deliberately left
unextracted (``confidence=0.0``) rather than guessed — see
Section 6/17 of the design spec ("never invent information missing from
the resume"). A future LLM-backed extractor can populate them with a
``source="llm"`` provenance without changing this schema.
"""

from __future__ import annotations

import re

from app.profile.models import ExtractedField, ResumeExtraction, SkillSet

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")
_PHONE_RE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
_EXPERIENCE_RE = re.compile(r"(\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\b", re.IGNORECASE)

_SECTION_HEADERS = {
    "education": "education",
    "certifications": "certifications",
    "certification": "certifications",
    "languages": "languages",
    "achievements": "achievements",
    "accomplishments": "achievements",
}

# Built-in skill vocabulary used to detect skills in free text, independent
# of whatever the candidate has configured in config/candidate.yaml. Skill
# aliases (e.g. "AWS" / "Amazon Web Services") intentionally map to the same
# canonical name — full alias normalization lands in Phase 2 (app/matching).
DEFAULT_SKILL_VOCAB: dict[str, list[str]] = {
    "cloud": ["AWS", "Amazon Web Services", "Azure", "Google Cloud", "GCP"],
    "ai": ["Machine Learning", "Artificial Intelligence", "Agentic AI", "LLM", "NLP"],
    "platforms": ["Kubernetes", "Docker", "Linux"],
    "technical": ["Python", "Java", "Microservices", "REST API", "SQL", "TypeScript"],
    "leadership": [
        "Engineering Leadership",
        "Team Leadership",
        "People Management",
        "Stakeholder Management",
    ],
}


def _find_email(text: str) -> ExtractedField[str]:
    match = _EMAIL_RE.search(text)
    if not match:
        return ExtractedField[str].unextracted()
    return ExtractedField[str](value=match.group(0), source="resume", confidence=0.95)


def _find_phone(text: str) -> ExtractedField[str]:
    for candidate in _PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", candidate)
        if 7 <= len(digits) <= 15:
            return ExtractedField[str](value=candidate.strip(), source="resume", confidence=0.75)
    return ExtractedField[str].unextracted()


def _find_name(text: str) -> ExtractedField[str]:
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        words = stripped.split()
        if (
            2 <= len(words) <= 4
            and all(w[:1].isupper() for w in words if w[:1].isalpha())
            and "@" not in stripped
            and not any(ch.isdigit() for ch in stripped)
        ):
            return ExtractedField[str](value=stripped, source="resume", confidence=0.6)
        break  # only the very first non-blank line is considered
    return ExtractedField[str].unextracted()


def _find_experience_years(text: str) -> ExtractedField[float]:
    matches = [float(m) for m in _EXPERIENCE_RE.findall(text)]
    if not matches:
        return ExtractedField[float].unextracted()
    return ExtractedField[float](value=max(matches), source="resume", confidence=0.7)


def _extract_sections(text: str) -> dict[str, list[str]]:
    """Scan for known section headers and collect the lines under each."""
    sections: dict[str, list[str]] = {v: [] for v in _SECTION_HEADERS.values()}
    current: str | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        header_key = _SECTION_HEADERS.get(stripped.lower().rstrip(":"))
        if header_key is not None:
            current = header_key
            continue

        # A new ALL-CAPS line not in our known headers ends the current section.
        if stripped.isupper() and len(stripped.split()) <= 4:
            current = None
            continue

        if current is not None:
            item = stripped.lstrip("-•*").strip()
            if item:
                sections[current].append(item)

    return sections


def _section_field(sections: dict[str, list[str]], key: str) -> ExtractedField[list[str]]:
    values = sections.get(key, [])
    if not values:
        return ExtractedField[list[str]].unextracted()
    return ExtractedField[list[str]](value=values, source="resume", confidence=0.6)


def _match_skills(
    text: str,
    primary_skills: list[str] | None,
    secondary_skills: list[str] | None,
) -> SkillSet:
    lower_text = text.lower()

    def matches(vocab: list[str]) -> list[str]:
        found = []
        for skill in vocab:
            pattern = r"\b" + re.escape(skill.lower()) + r"\b"
            if re.search(pattern, lower_text):
                found.append(skill)
        return found

    return SkillSet(
        primary=matches(primary_skills or []),
        secondary=matches(secondary_skills or []),
        leadership=matches(DEFAULT_SKILL_VOCAB["leadership"]),
        technical=matches(DEFAULT_SKILL_VOCAB["technical"]),
        platforms=matches(DEFAULT_SKILL_VOCAB["platforms"]),
        cloud=matches(DEFAULT_SKILL_VOCAB["cloud"]),
        ai=matches(DEFAULT_SKILL_VOCAB["ai"]),
    )


def parse_resume_text(
    text: str,
    *,
    source_file: str,
    primary_skills: list[str] | None = None,
    secondary_skills: list[str] | None = None,
) -> ResumeExtraction:
    sections = _extract_sections(text)

    return ResumeExtraction(
        source_file=source_file,
        raw_text=text,
        name=_find_name(text),
        email=_find_email(text),
        phone=_find_phone(text),
        location=ExtractedField[str].unextracted(),
        current_title=ExtractedField[str].unextracted(),
        experience_years=_find_experience_years(text),
        previous_titles=ExtractedField[list[str]].unextracted(),
        companies=ExtractedField[list[str]].unextracted(),
        industries=ExtractedField[list[str]].unextracted(),
        certifications=_section_field(sections, "certifications"),
        education=_section_field(sections, "education"),
        languages=_section_field(sections, "languages"),
        achievements=_section_field(sections, "achievements"),
        skills=_match_skills(text, primary_skills, secondary_skills),
    )
