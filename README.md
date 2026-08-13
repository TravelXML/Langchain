# Job Automation Platform

A local-first, multi-agent job discovery, matching, application-preparation,
and application-automation platform. See [`ARCHITECTURE.md`](ARCHITECTURE.md)
for system design and [`SECURITY.md`](SECURITY.md) for the safety model.

Runs primarily on your machine, uses a local LLM (Ollama) by default, and
requires no paid API key for the basic install.

## Status

**Phase 0 — Project Bootstrap** is complete: repository skeleton, FastAPI
app, structured logging, configuration system, async database foundation,
and the `/health` endpoint. Everything else described in the architecture
doc (candidate profiles, matching, LangGraph orchestration, portal
adapters, browser automation, dashboard, scheduler) lands in later phases.

## Quickstart

```bash
git clone <repo-url>
cd job-automation

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
playwright install chromium   # only needed once browser automation phases land

cp .env.example .env

# run the API
uvicorn app.main:app --reload
# in another shell:
curl http://localhost:8000/health
```

Or via the Makefile:

```bash
make install
make dev     # runs the API with reload
make test    # runs the test suite
```

## Local LLM setup (Ollama)

The platform defaults to a local Ollama instance and never requires a paid
API key. This is wired in starting Phase 6; for now `config/llm.yaml` and
`.env.example` document the expected configuration:

```bash
# install Ollama separately: https://ollama.com
ollama pull <your-chosen-model>
export OLLAMA_MODEL=<your-chosen-model>
```

No specific model is hardcoded anywhere in the codebase — set `OLLAMA_MODEL`
to whatever you have pulled locally.

## Configuration

- `.env` — machine-specific settings and secrets (never committed; see
  `.env.example`).
- `config/*.yaml` — domain configuration (candidate preferences, scoring
  weights, search policy, automation limits, portal registry). Intended to
  be editable from the future dashboard without code changes.

## Safety defaults

Two defaults are intentionally conservative and must be changed explicitly:

- `automation.dry_run: true` — no application is ever submitted until you
  turn this off.
- `approval.mode: manual` — every application requires human approval until
  you opt into `hybrid` or `automatic`.

See [`SECURITY.md`](SECURITY.md) for the full safety model.

## Repository layout

```text
app/
  core/            configuration, logging
  api/              FastAPI routes
  database/         async SQLAlchemy session/models
  agents/ graph/     LangGraph orchestration (Phase 3+)
  profile/           candidate profile parsing (Phase 1)
  matching/          job-candidate scoring engine (Phase 2)
  guardrails/        deterministic policy engine (Phase 4)
  browser/           Playwright automation (Phase 5)
  portals/           portal adapters (Phase 7+)
  llm/               local LLM provider abstraction (Phase 6)
  observability/ notifications/ scheduler/ security/
config/              YAML domain configuration
prompts/             versioned LLM prompts (Phase 6+)
tests/               unit / integration / e2e / fixtures / mocks
migrations/           Alembic migrations
```

## Development

```bash
make lint       # ruff
make format     # black
make typecheck  # mypy
make test       # pytest
```

## Development workflow

This project is built in explicit phases (see the architecture doc's
implementation plan). Each phase stops for review before the next begins —
the repository will not contain portal automation, browser automation, or
LLM integration until those phases are explicitly implemented.
