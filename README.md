# Job Automation Platform

A local-first, multi-agent job discovery, matching, application-preparation,
and application-automation platform. See [`ARCHITECTURE.md`](ARCHITECTURE.md)
for system design and [`SECURITY.md`](SECURITY.md) for the safety model.

Runs primarily on your machine, uses a local LLM (Ollama) by default, and
requires no paid API key for the basic install.

## Status

- **Phase 0 — Project Bootstrap**: repository skeleton, FastAPI app,
  structured logging, configuration system, async database foundation +
  Alembic, `/health`.
- **Phase 1 — Candidate Profile**: resume/cover-letter PDF ingestion,
  deterministic (non-LLM) structured extraction, `candidate_profiles` table,
  `/api/profile` (`GET`, `POST /import`, `PUT`).
- **Phase 2 — Job Model + Matching Engine**: `NormalizedJob` + portal-agnostic
  `normalize_job()`, and a fully rule-based weighted scorer
  (`app/matching/`) covering title/seniority, skills (with alias
  normalization), experience, salary, location, and industry — configurable
  via `config/scoring.yaml`, no LLM or API involved.

Everything else described in the architecture doc (LangGraph orchestration,
portal adapters, browser automation, dashboard, scheduler) lands in later
phases.

## Quickstart

```bash
git clone <repo-url>
cd job-automation

python3 -m venv .venv
source .venv/bin/activate

pip install -e ".[dev]"
playwright install chromium   # only needed once browser automation phases land

cp .env.example .env
alembic upgrade head          # creates ./data/job_automation.db with the current schema

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

### Importing your resume

```bash
curl -X POST http://localhost:8000/api/profile/import \
  -F "resume=@/path/to/resume.pdf;type=application/pdf" \
  -F "cover_letter=@/path/to/cover_letter.pdf;type=application/pdf"   # optional

curl http://localhost:8000/api/profile
```

Extraction in Phase 1 is deliberately **rule-based, not LLM-based** — resume
"understanding" is an LLM task per the design spec, and the LLM isn't wired
up until Phase 6. So today's extractor pulls what regex/section-scanning can
get honestly (email, phone, a name guess, years of experience, skills
matched against a vocabulary, and labeled sections like education/
certifications) and leaves everything else — previous titles, companies,
industries — as `{"value": null, "confidence": 0.0, "source": "unextracted"}`
rather than guessing. See `app/profile/parser.py` and Section 6/17 of the
architecture spec ("never invent information missing from the resume").

### Scoring a job against the candidate

There's no discovery pipeline yet (that's Phase 3+), so for now scoring is
a library call, not an endpoint — `app.jobs.parser.normalize_job()` turns a
raw job dict into a `NormalizedJob`, and `app.matching.scorer.score_job()`
scores it against `CandidatePreferences` + resume skills/experience:

```python
from app.jobs.parser import normalize_job
from app.matching.scorer import score_job
from app.profile.models import CandidatePreferences

job = normalize_job(
    {
        "url": "https://boards.greenhouse.io/acme/jobs/4821",
        "title": "Chief Technology Officer",
        "company": "Acme TravelTech",
        "location": "Bengaluru, India",
        "work_mode": "hybrid",
        "salary_min": 45, "salary_max": 65, "salary_currency": "INR",
        "required_skills": ["Cloud Architecture", "Engineering Leadership", "AWS"],
        "preferred_skills": ["Agentic AI", "Kubernetes"],
        "minimum_experience": 15,
        "industry": "TravelTech",
    },
    source="greenhouse",
)

result = score_job(
    job,
    preferences=CandidatePreferences(
        target_positions=["CTO", "VP Technology"],
        preferred_industries=["TravelTech", "SaaS"],
        locations_preferred=["Bengaluru", "Remote"],
        relocation_allowed=True,
        work_mode=["remote", "hybrid"],
        compensation_currency="INR", compensation_minimum=30, compensation_preferred=50,
    ),
    candidate_skills=["Cloud Architecture", "Engineering Leadership", "Amazon Web Services", "Agentic AI"],
    candidate_experience_years=20,
)
# result.overall_score == 95.5, result.recommendation == "priority_apply"
# "Amazon Web Services" was recognized as "AWS" via alias normalization.
```

Scoring is entirely deterministic — no LLM, no embeddings (Section 16/38
add those as an *additional* signal in a later phase; the rule-based score
is never replaced by them). Weights and thresholds come from
`config/scoring.yaml`.

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
  api/              FastAPI routes (health, profile)
  database/         async SQLAlchemy session/models
  agents/ graph/     LangGraph orchestration (Phase 3+)
  profile/           candidate profile parsing — loader/parser/services (Phase 1)
  jobs/              NormalizedJob + portal-agnostic normalize_job() (Phase 2)
  matching/          job-candidate scoring engine — title/skills/experience/
                      salary/location/industry, all rule-based (Phase 2)
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

## Notes for contributors

- **`get_engine()`/`get_sessionmaker()` take no arguments.** They resolve
  settings via the `get_settings()` singleton internally. Don't add an
  optional `settings` parameter back in: `functools.lru_cache` keys strictly
  on what a call site passes, so `get_engine()` vs. `get_engine(None)` (or
  `get_engine(some_settings)`) hash to *different* cache entries and quietly
  produce two unrelated engines. Harmless for file-based SQLite/Postgres
  (both point at the same backing store); fatal for in-memory SQLite, where
  each engine is a wholly separate database. This bit Phase 1's profile API
  tests — the fix is in `app/database/session.py`.
- **A fresh `./data/job_automation.db` needs `alembic upgrade head`** before
  the API can serve anything beyond `/health` — tests don't need this (an
  autouse fixture creates tables against the in-memory test DB directly) but
  real local runs do.

## Development workflow

This project is built in explicit phases (see the architecture doc's
implementation plan). Each phase stops for review before the next begins —
the repository will not contain portal automation, browser automation, or
LLM integration until those phases are explicitly implemented.
