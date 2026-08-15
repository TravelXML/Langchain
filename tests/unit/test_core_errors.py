"""Tests for the central error hierarchy (Section 40, app/core/errors.py)."""

from __future__ import annotations

from app.core.errors import (
    ApplicationValidationError,
    DuplicateApplicationError,
    HumanActionRequired,
    JobAutomationError,
    SubmissionVerificationError,
)


def test_base_error_captures_all_context_fields():
    exc = JobAutomationError(
        "something failed",
        url="https://example.com/jobs/1",
        portal="greenhouse:acme",
        job_id="job-1",
        run_id="run-1",
        screenshot_path="/tmp/shot.png",
        step="fill_form",
    )
    body = exc.to_dict()
    assert body["error_type"] == "JobAutomationError"
    assert body["message"] == "something failed"
    assert body["url"] == "https://example.com/jobs/1"
    assert body["portal"] == "greenhouse:acme"
    assert body["job_id"] == "job-1"
    assert body["run_id"] == "run-1"
    assert body["screenshot"] == "/tmp/shot.png"
    assert body["step"] == "fill_form"
    assert body["timestamp"]  # ISO string, non-empty


def test_all_context_fields_are_optional():
    exc = JobAutomationError("bare message")
    body = exc.to_dict()
    assert body["message"] == "bare message"
    assert body["url"] is None
    assert body["portal"] is None
    assert body["job_id"] is None
    assert body["run_id"] is None
    assert body["screenshot"] is None
    assert body["step"] is None


def test_to_dict_strips_query_string_from_url():
    exc = JobAutomationError("leaked?", url="https://example.com/jobs?api_key=super-secret&page=2")
    assert exc.to_dict()["url"] == "https://example.com/jobs"
    assert "super-secret" not in str(exc.to_dict())


def test_to_dict_error_type_reflects_the_actual_subclass():
    exc = DuplicateApplicationError("dup", job_id="job-1")
    assert exc.to_dict()["error_type"] == "DuplicateApplicationError"


def test_str_message_is_the_original_message_not_the_full_dict():
    exc = JobAutomationError("plain message", portal="lever:acme")
    assert str(exc) == "plain message"


def test_every_documented_subclass_is_a_job_automation_error():
    for cls in (
        ApplicationValidationError,
        DuplicateApplicationError,
        SubmissionVerificationError,
        HumanActionRequired,
    ):
        assert issubclass(cls, JobAutomationError)
        instance = cls("test")
        assert isinstance(instance, JobAutomationError)
        assert instance.to_dict()["error_type"] == cls.__name__
