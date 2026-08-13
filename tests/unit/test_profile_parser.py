from __future__ import annotations

from app.profile.parser import parse_resume_text

SAMPLE_RESUME = """Jordan Casey Smith
jordan.smith@example.com
+1 415-555-0134

SUMMARY
Engineering leader with 12 years experience building cloud platforms.

SKILLS
Python, AWS, Kubernetes, Machine Learning, Team Leadership

EDUCATION
B.S. Computer Science, State University

CERTIFICATIONS
AWS Certified Solutions Architect

LANGUAGES
English
Spanish

ACHIEVEMENTS
Led migration to Kubernetes reducing costs by 30%
"""


def _parse():
    return parse_resume_text(
        SAMPLE_RESUME,
        source_file="resume.pdf",
        primary_skills=["Python", "Machine Learning"],
        secondary_skills=["Docker"],
    )


def test_extracts_email_with_high_confidence():
    result = _parse()
    assert result.email.value == "jordan.smith@example.com"
    assert result.email.source == "resume"
    assert result.email.confidence >= 0.9


def test_extracts_phone():
    result = _parse()
    assert result.phone.value is not None
    assert "415" in result.phone.value


def test_extracts_name_from_first_line():
    result = _parse()
    assert result.name.value == "Jordan Casey Smith"
    assert result.name.confidence == 0.6


def test_extracts_experience_years():
    result = _parse()
    assert result.experience_years.value == 12.0


def test_extracts_sections():
    result = _parse()
    assert result.education.value == ["B.S. Computer Science, State University"]
    assert result.certifications.value == ["AWS Certified Solutions Architect"]
    assert result.languages.value == ["English", "Spanish"]
    assert result.achievements.value == ["Led migration to Kubernetes reducing costs by 30%"]


def test_matches_configured_skills():
    result = _parse()
    assert "Python" in result.skills.primary
    assert "Machine Learning" in result.skills.primary
    assert result.skills.secondary == []  # "Docker" is not present in the resume text


def test_matches_default_skill_vocabulary():
    result = _parse()
    assert "AWS" in result.skills.cloud
    assert "Kubernetes" in result.skills.platforms
    assert "Team Leadership" in result.skills.leadership


def test_never_invents_companies_titles_or_industries():
    """Section 17: the system must never invent employment history."""
    result = _parse()
    for field in (result.companies, result.previous_titles, result.industries):
        assert field.value is None
        assert field.confidence == 0.0
        assert field.source == "unextracted"


def test_location_and_current_title_left_unextracted_without_explicit_labels():
    result = _parse()
    assert result.location.source == "unextracted"
    assert result.current_title.source == "unextracted"


def test_empty_resume_text_produces_all_unextracted_fields():
    result = parse_resume_text("", source_file="empty.pdf")
    assert result.email.source == "unextracted"
    assert result.name.source == "unextracted"
    assert result.experience_years.source == "unextracted"
    assert result.skills.all_skills() == []
