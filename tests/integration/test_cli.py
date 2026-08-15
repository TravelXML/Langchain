"""CLI tests (Section 46). `jobagent`'s commands each wrap an async body
in `asyncio.run(...)`, so these tests use plain `def` (not `async def`)
— `CliRunner.invoke` must run outside any already-active event loop, or
the command's own `asyncio.run()` call raises.
"""

from __future__ import annotations

import json
import sys

import pytest
import structlog
from typer.testing import CliRunner

import app.cli.main as cli_main
from app.database.models.candidate_profile import DEFAULT_PROFILE_ID, CandidateProfileRecord
from app.database.session import get_sessionmaker
from app.profile.models import CandidatePreferences, ExtractedField, ResumeExtraction
from tests.fixtures.pdf_builder import build_pdf_bytes

app = cli_main.app
runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_structlog_after_cli_invocation():
    """`app.cli.main`'s startup callback calls `configure_logging(...,
    stream=sys.stderr)` on every invocation — correct for a real
    `jobagent` process (fresh process, configures once, exits), but
    `structlog.configure()` mutates *global*, process-wide state, and
    `CliRunner` closes the redirected stderr right after `invoke()`
    returns. `app/core/logging.py` sets `cache_logger_on_first_use=False`
    specifically so this reset is sufficient (an *cached* logger would
    keep a stale, closed-stream reference no reset could reach) — without
    that, an unrelated module-level logger elsewhere in the suite could
    permanently break after the first test file that exercises the CLI.
    """
    yield
    structlog.reset_defaults()


def test_startup_callback_configures_logging_to_stderr(monkeypatch):
    # CliRunner redirects sys.stderr/stdout only *during* invoke() — the
    # comparison must happen inside that same call, not against the
    # outer sys.stderr captured before/after (a different object once
    # the runner restores the real streams on return).
    calls = []
    monkeypatch.setattr(
        cli_main,
        "configure_logging",
        lambda settings, *, stream: calls.append(stream is sys.stderr and stream is not sys.stdout),
    )
    result = runner.invoke(app, ["human", "pending"])
    assert result.exit_code == 0
    assert calls == [True]


_PREFERENCES = CandidatePreferences(
    target_positions=["CTO"],
    preferred_industries=["SaaS"],
    skills_primary=["Cloud Architecture", "Engineering Leadership", "AWS", "Python"],
    locations_preferred=["Bengaluru", "Remote"],
    relocation_allowed=False,
    work_mode=["remote", "hybrid"],
    compensation_currency="INR",
    compensation_minimum=30,
    compensation_preferred=50,
    work_authorization="citizen",
)


async def _seed_profile() -> None:
    resume = ResumeExtraction(
        source_file="resume.pdf",
        raw_text="...",
        email=ExtractedField[str](value="jordan@example.com", source="resume", confidence=0.95),
        experience_years=ExtractedField[float](value=15.0, source="resume", confidence=0.7),
    )
    async with get_sessionmaker()() as session:
        session.add(
            CandidateProfileRecord(
                id=DEFAULT_PROFILE_ID,
                preferences=_PREFERENCES.model_dump(mode="json"),
                resume=resume.model_dump(mode="json"),
            )
        )
        await session.commit()


def test_doctor_reports_every_check_without_crashing():
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    for check in (
        "Python version",
        "Database",
        "Playwright browser",
        "Ollama reachable",
        "Configured LLM",
        "Resume files",
        "Environment",
        "Required directories",
    ):
        assert check in result.stdout


def test_profile_show_without_profile_exits_nonzero():
    result = runner.invoke(app, ["profile", "show"])
    assert result.exit_code == 1
    assert "No candidate profile" in result.stdout


def test_profile_import_and_show(tmp_path):
    resume_path = tmp_path / "resume.pdf"
    resume_path.write_bytes(
        build_pdf_bytes(
            [
                "Jordan Casey Smith",
                "jordan@example.com",
                "+1 415 555 0134",
                "15 years of experience",
            ]
        )
    )

    import_result = runner.invoke(app, ["profile", "import", str(resume_path)])
    assert import_result.exit_code == 0, import_result.stdout
    assert "Profile imported" in import_result.stdout

    show_result = runner.invoke(app, ["profile", "show"])
    assert show_result.exit_code == 0
    body = json.loads(show_result.stdout)
    assert body["id"] == DEFAULT_PROFILE_ID


def test_profile_import_missing_file_exits_nonzero(tmp_path):
    result = runner.invoke(app, ["profile", "import", str(tmp_path / "does_not_exist.pdf")])
    assert result.exit_code == 1
    assert "File not found" in result.output


def test_applications_list_empty():
    result = runner.invoke(app, ["applications", "list"])
    assert result.exit_code == 0
    assert "No applications yet" in result.stdout


def test_human_pending_empty():
    result = runner.invoke(app, ["human", "pending"])
    assert result.exit_code == 0
    assert "Nothing pending" in result.stdout


def test_human_resolve_unknown_id_exits_nonzero():
    result = runner.invoke(app, ["human", "resolve", "does-not-exist"])
    assert result.exit_code == 1
    assert "No pending human action" in result.output


def test_run_then_human_pending_then_resolve():
    import asyncio

    asyncio.run(_seed_profile())

    run_result = runner.invoke(app, ["run"])
    assert run_result.exit_code == 0, run_result.stdout
    assert "waiting on a human decision" in run_result.stdout

    pending_result = runner.invoke(app, ["human", "pending"])
    assert pending_result.exit_code == 0
    assert "[run]" in pending_result.stdout
    intervention_id = pending_result.stdout.split()[0]

    # Extract the job id waiting for a decision straight from the run
    # output rather than re-deriving it, to keep the test focused on the
    # CLI's own behavior rather than the discovery pipeline's internals.
    interrupt_json = run_result.stdout.split("waiting on a human decision.\n", 1)[1]
    interrupt_json = interrupt_json.split("\nResolve with:")[0]
    interrupt = json.loads(interrupt_json)
    job_id = interrupt["jobs"][0]["job_id"]

    resolve_result = runner.invoke(
        app,
        [
            "human",
            "resolve",
            intervention_id,
            "--decisions",
            json.dumps({job_id: "queue"}),
        ],
    )
    assert resolve_result.exit_code == 0, resolve_result.stdout
    body = json.loads(resolve_result.stdout)
    assert body["status"] == "completed"
