from __future__ import annotations

import pytest

from app.jobs.parser import normalize_job


def test_normalize_job_maps_known_fields():
    job = normalize_job(
        {
            "url": "https://example.com/jobs/42",
            "title": "VP Engineering",
            "company": "Acme",
            "location": "Remote",
            "required_skills": ["Python"],
        },
        source="greenhouse",
    )
    assert job.source == "greenhouse"
    assert job.title == "VP Engineering"
    assert job.required_skills == ["Python"]


def test_normalize_job_puts_unknown_fields_in_metadata():
    job = normalize_job(
        {
            "url": "https://example.com/jobs/42",
            "title": "VP Engineering",
            "company": "Acme",
            "greenhouse_board_token": "acme-eng",
        },
        source="greenhouse",
    )
    assert job.metadata == {"greenhouse_board_token": "acme-eng"}


def test_normalize_job_raises_on_missing_required_field():
    with pytest.raises(ValueError, match="title"):
        normalize_job({"url": "https://example.com/jobs/42", "company": "Acme"}, source="test")


def test_normalize_job_id_is_stable_for_same_external_id():
    raw = {
        "url": "https://example.com/jobs/42",
        "title": "VP Engineering",
        "company": "Acme",
        "external_job_id": "42",
    }
    job1 = normalize_job(raw, source="greenhouse")
    job2 = normalize_job(raw, source="greenhouse")
    assert job1.id == job2.id


def test_normalize_job_id_differs_across_sources():
    raw = {
        "url": "https://example.com/jobs/42",
        "title": "VP Engineering",
        "company": "Acme",
        "external_job_id": "42",
    }
    job_a = normalize_job(raw, source="greenhouse")
    job_b = normalize_job(raw, source="lever")
    assert job_a.id != job_b.id
