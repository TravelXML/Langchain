"""`jobagent` CLI (Section 46) — a thin operator-facing wrapper over the
same domain services `app/api/routes/` calls. No command reimplements
logic that already lives in a service module; each one just does the
argument parsing, calls the service, and prints the result.

Runs as a plain Python process, no FastAPI server required — reads
config/DB the same way any other entrypoint does (env vars, `config/
*.yaml`, `alembic upgrade head` already applied). Async command bodies
are run via `asyncio.run` since Typer commands are synchronous.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Annotated

import typer

from app.browser.manager import launch_browser
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.models.human_intervention import HumanInterventionRecord
from app.database.session import check_database_connection, get_sessionmaker
from app.graph import apply_service, persistence
from app.graph import service as run_service
from app.llm.health import check_llm_health
from app.profile import profile_service
from app.profile.loader import PdfExtractionError

app = typer.Typer(help="Local-first job discovery, matching, and application automation.")
profile_app = typer.Typer(help="Manage the candidate profile.")
applications_app = typer.Typer(help="Inspect applications.")
human_app = typer.Typer(help="Review and resolve pending human actions.")
app.add_typer(profile_app, name="profile")
app.add_typer(applications_app, name="applications")
app.add_typer(human_app, name="human")


@app.callback()
def _configure() -> None:
    # stdout is this CLI's product output (JSON, status text) — a script
    # piping `jobagent run | jq` must never see a log line land in it, so
    # every log this process emits (including notification console logs
    # fired from inside a service call) goes to stderr instead.
    configure_logging(get_settings(), stream=sys.stderr)


def _run(coro):
    return asyncio.run(coro)


def _save_upload(path: Path, subdir: str) -> Path:
    if not path.exists():
        typer.echo(f"File not found: {path}", err=True)
        raise typer.Exit(code=1)
    target_dir = get_settings().upload_dir / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{uuid.uuid4().hex}_{path.name}"
    target_path.write_bytes(path.read_bytes())
    return target_path


# --- profile -----------------------------------------------------------


@profile_app.command("import")
def profile_import(
    resume: Annotated[Path, typer.Argument(help="Path to the candidate's resume PDF")],
    cover_letter: Annotated[Path | None, typer.Option(help="Path to a cover letter PDF")] = None,
) -> None:
    """Import (or replace) the candidate profile from a resume PDF."""

    async def _do() -> None:
        resume_path = _save_upload(resume, "resumes")
        cover_letter_path = _save_upload(cover_letter, "cover_letters") if cover_letter else None
        async with get_sessionmaker()() as session:
            try:
                profile = await profile_service.import_profile(
                    session, resume_path=resume_path, cover_letter_path=cover_letter_path
                )
            except PdfExtractionError as exc:
                typer.echo(f"Could not extract text from PDF: {exc}", err=True)
                raise typer.Exit(code=1) from exc
        email = profile.resume.email.value if profile.resume else None
        typer.echo(f"Profile imported: {email or '(no email extracted)'}")

    _run(_do())


@profile_app.command("show")
def profile_show() -> None:
    """Show the current candidate profile."""

    async def _do() -> None:
        async with get_sessionmaker()() as session:
            profile = await profile_service.get_profile(session)
        if profile is None:
            typer.echo("No candidate profile has been imported yet.")
            typer.echo("Run: jobagent profile import <resume.pdf>")
            raise typer.Exit(code=1)
        typer.echo(json.dumps(profile.model_dump(mode="json"), indent=2, default=str))

    _run(_do())


# --- run -----------------------------------------------------------------


@app.command("run")
def run_discovery(
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Informational only — AUTOMATION_DRY_RUN already governs this globally.",
        ),
    ] = True,
) -> None:
    """Run the discovery pipeline: discover -> normalize -> dedupe -> score -> guard -> finalize."""
    if not dry_run:
        typer.echo(
            "Note: --no-dry-run has no effect here — dry-run is controlled by the "
            "AUTOMATION_DRY_RUN environment variable / config/automation.yaml, not a "
            "per-run flag.",
        )

    async def _do() -> None:
        result = await run_service.start_run()
        if result.status == "waiting_human":
            typer.echo(f"Run {result.run_id}: waiting on a human decision.")
            typer.echo(json.dumps(result.interrupt, indent=2, default=str))
            typer.echo("Resolve with: jobagent human resolve <id>")
            return
        typer.echo(f"Run {result.run_id}: completed.")
        typer.echo(json.dumps(result.metrics, indent=2))
        if result.warnings:
            typer.echo(f"Warnings: {result.warnings}")
        if result.errors:
            typer.echo(f"Errors: {result.errors}")

    _run(_do())


# --- applications --------------------------------------------------------


@applications_app.command("list")
def applications_list(
    status: Annotated[str | None, typer.Option(help="Filter by status")] = None,
) -> None:
    """List applications."""

    async def _do() -> None:
        async with get_sessionmaker()() as session:
            records = await persistence.list_applications(session, status=status, limit=100)
        if not records:
            typer.echo("No applications yet.")
            return
        for record in records:
            typer.echo(
                f"{record.id[:8]}  {record.status:<20}  {record.job_title} @ {record.company}"
            )

    _run(_do())


# --- human ---------------------------------------------------------------


@human_app.command("pending")
def human_pending() -> None:
    """List pending human actions across both discovery runs and applications."""

    async def _do() -> None:
        async with get_sessionmaker()() as session:
            records = await persistence.list_human_interventions(session, status="pending")
        if not records:
            typer.echo("Nothing pending.")
            return
        for record in records:
            typer.echo(f"{record.id}  [{record.kind}]  {record.reason}  (ref: {record.ref_id[:8]})")

    _run(_do())


@human_app.command("resolve")
def human_resolve(
    intervention_id: Annotated[str, typer.Argument(help="Human intervention id")],
    decisions: Annotated[
        str | None, typer.Option(help='JSON decisions, for a run: \'{"job_id": "queue"}\'')
    ] = None,
    payload: Annotated[
        str | None, typer.Option(help='JSON payload, for an application: \'{"approved": "true"}\'')
    ] = None,
) -> None:
    """Resolve one pending human action (run-level or application-level)."""

    async def _do() -> None:
        async with get_sessionmaker()() as session:
            record = await session.get(HumanInterventionRecord, intervention_id)
            if record is None or record.status != "pending":
                typer.echo(f"No pending human action with id {intervention_id!r}", err=True)
                raise typer.Exit(code=1)
            kind, ref_id = record.kind, record.ref_id

        result: run_service.RunResult | apply_service.ApplicationResult | None
        if kind == "run":
            if decisions is None:
                typer.echo("--decisions is required to resolve a run intervention", err=True)
                raise typer.Exit(code=1)
            result = await run_service.resume_run(ref_id, json.loads(decisions))
        elif kind == "application":
            if payload is None:
                typer.echo("--payload is required to resolve an application intervention", err=True)
                raise typer.Exit(code=1)
            result = await apply_service.resume_application(ref_id, json.loads(payload))
        else:
            typer.echo(f"Unknown intervention kind: {kind}", err=True)
            raise typer.Exit(code=1)

        if result is None:
            typer.echo(f"{kind} {ref_id} not found", err=True)
            raise typer.Exit(code=1)
        typer.echo(json.dumps(result.model_dump(mode="json"), indent=2, default=str))

    _run(_do())


# --- doctor ----------------------------------------------------------------


async def _doctor_checks() -> list[tuple[str, bool, str]]:
    settings = get_settings()
    results: list[tuple[str, bool, str]] = []

    py_ok = sys.version_info >= (3, 11)
    results.append(("Python version", py_ok, ".".join(map(str, sys.version_info[:3]))))

    db_ok = await check_database_connection()
    results.append(("Database", db_ok, settings.database_url))

    try:
        async with launch_browser():
            pass
        results.append(("Playwright browser", True, "chromium launches"))
    except Exception as exc:  # doctor must never crash on a broken check
        results.append(("Playwright browser", False, str(exc)))

    llm_status = await check_llm_health(
        base_url=settings.ollama_base_url, model=settings.ollama_model
    )
    results.append(("Ollama reachable", llm_status.reachable, settings.ollama_base_url))
    results.append(
        ("Configured LLM", llm_status.model_exists, settings.ollama_model or "(not set)")
    )

    async with get_sessionmaker()() as session:
        profile = await profile_service.get_profile(session)
    results.append(
        (
            "Resume files",
            profile is not None,
            "profile imported" if profile else "run: jobagent profile import <resume.pdf>",
        )
    )

    env_path = Path(".env")
    results.append(
        (
            "Environment",
            env_path.exists(),
            str(env_path.resolve()) if env_path.exists() else "no .env — using process env vars",
        )
    )

    required_dirs = [
        settings.upload_dir,
        settings.browser_sessions_dir,
        settings.browser_artifacts_dir,
    ]
    missing = [str(d) for d in required_dirs if not d.exists()]
    dirs_detail = "all present" if not missing else f"missing: {missing}"
    results.append(("Required directories", not missing, dirs_detail))

    return results


@app.command("doctor")
def doctor() -> None:
    """Diagnose the local environment — never fails the command itself,
    just reports what's healthy and what isn't."""
    results = _run(_doctor_checks())
    for name, ok, detail in results:
        mark = "OK  " if ok else "FAIL"
        typer.echo(f"[{mark}] {name}: {detail}")


if __name__ == "__main__":
    app()
