# Architecture

This document describes both the current (Phase 0-1) implementation and the
target architecture the project is being built toward, phase by phase. Where
a component is not yet implemented, it is marked **(planned)**.

## System context

```mermaid
flowchart LR
    Candidate[Candidate] -->|resume, cover letter, preferences| Config[config/*.yaml + .env]
    Config --> Backend[FastAPI backend]
    Backend --> DB[(SQLite / PostgreSQL)]
    Backend --> LLM[Ollama local LLM]
    Backend -->|planned Phase 5+| Browser[Playwright browser automation]
    Browser -->|planned| Portals[Job portals: Greenhouse, Lever, Workday, ...]
    Backend --> Dashboard[React dashboard - planned Phase 8]
    Candidate --> Dashboard
```

## Current implementation (Phase 0-1)

```mermaid
flowchart TB
    Client -->|HTTP| FastAPIApp[app.main:app]
    FastAPIApp --> CorrelationMW[Correlation-ID middleware]
    FastAPIApp --> HealthRoute["/health"]
    FastAPIApp --> ProfileRoutes["/api/profile (GET, POST /import, PUT)"]
    HealthRoute --> Settings[app.core.config.Settings]
    HealthRoute --> DBCheck[check_database_connection]
    ProfileRoutes --> ProfileService[app.profile.profile_service]
    ProfileService --> ResumeService[resume_service]
    ProfileService --> CoverLetterService[cover_letter_service]
    ResumeService --> Loader[loader: pypdf text extraction]
    ResumeService --> Parser[parser: deterministic regex/section heuristics]
    ProfileService --> DBCheck
    DBCheck --> Engine[async SQLAlchemy engine]
    Engine --> SQLite[(SQLite dev / PostgreSQL prod)]
    Settings --> YamlLoader[YamlConfigLoader]
    YamlLoader --> YamlFiles["config/*.yaml"]
    ProfileService --> YamlLoader
```

Configuration is layered:

- **`Settings`** (`app/core/config.py`) — environment-driven (`.env`),
  process-level: database URL, LLM connection, dry-run/approval defaults.
- **`YamlConfigLoader`** — domain configuration under `config/*.yaml`
  (candidate preferences, scoring weights, search policy, automation
  limits, portal registry), with `${ENV_VAR}` interpolation and per-file
  caching.

Logging is JSON-structured (`structlog`), with a per-request correlation ID
bound via contextvars and a redaction processor that strips sensitive keys
(passwords, tokens, cookies, OTPs, secrets) before anything is emitted.

### Candidate profile (Phase 1)

```mermaid
flowchart LR
    PDF[resume.pdf] --> Loader[loader.extract_text_from_pdf]
    Loader --> Parser[parser.parse_resume_text]
    ConfigSkills["config/candidate.yaml skills"] --> Parser
    Parser --> ResumeExtraction["ResumeExtraction\n(every field: value/source/confidence)"]
    ResumeExtraction --> ProfileRecord[(candidate_profiles table)]
    CoverLetterPdf[cover_letter.pdf] --> CLLoader[loader.extract_text_from_pdf]
    CLLoader --> ProfileRecord
```

Extraction is **deterministic, not LLM-based** — per Section 2 of the design
spec, resume "understanding" is an LLM capability, but the LLM isn't wired
up until Phase 6. So Phase 1's parser only populates fields a defensible
rule can produce (regex for email/phone/years-of-experience, section-header
scanning for education/certifications/languages/achievements, vocabulary
matching for skills). Fields that genuinely need semantic understanding
(previous titles, companies, industries) are left as
`{"value": null, "confidence": 0.0, "source": "unextracted"}` rather than
guessed — see Section 17 ("never invent information missing from the
resume"). A future LLM-backed extractor fills the same `ExtractedField`
schema with `source="llm"` without changing any downstream consumer.

The system is single-candidate/local-first: `candidate_profiles` has exactly
one row, addressed by the fixed id `"default"` (see
`app/database/models/candidate_profile.py`).

## Target LangGraph workflow (planned, Phase 3+)

```mermaid
flowchart TB
    START --> LoadProfile[Load Candidate Profile]
    LoadProfile --> LoadPolicy[Load Search Policy]
    LoadPolicy --> Supervisor[Supervisor / Planner]
    Supervisor --> PortalA[Portal Subgraph A]
    Supervisor --> PortalB[Portal Subgraph B]
    Supervisor --> PortalC[Portal Subgraph C]
    PortalA --> Aggregate[Aggregate Jobs]
    PortalB --> Aggregate
    PortalC --> Aggregate
    Aggregate --> Dedupe
    Dedupe --> Normalize
    Normalize --> Score[Score Jobs]
    Score --> Guard[Policy Guard]
    Guard --> Queue[Application Queue]
    Queue --> ResumeSel[Resume Selection]
    ResumeSel --> Answers[Answer Preparation]
    Answers --> ApplyGraph[Portal Apply Graph]
    ApplyGraph --> Validator[Pre-Submit Validator]
    Validator --> Auto{Automatic Approval?}
    Auto -->|yes| Submit
    Auto -->|no| Human[Human Review]
    Human --> Submit
    Submit --> Verify[Verify Submission]
    Verify --> Persist[Persist Results]
    Persist --> Analytics
    Analytics --> END
```

## Target portal subgraph (planned, Phase 7+)

```mermaid
flowchart TB
    START --> CheckSession[check_session]
    CheckSession --> Discover[discover_job]
    Discover --> Load[load_job]
    Load --> NormalizeJob[normalize_job]
    NormalizeJob --> Open[open_application]
    Open --> DetectForm[detect_form]
    DetectForm --> MapFields[map_fields]
    MapFields --> FillFields[fill_fields]
    FillFields --> ValidateFields[validate_fields]
    ValidateFields --> CheckVerify[check_verification]
    CheckVerify --> PreSubmitGuard[pre_submit_guard]
    PreSubmitGuard --> Submit[submit]
    Submit --> VerifySubmission[verify_submission]
    VerifySubmission --> SaveResult[save_result]
    SaveResult --> END
```

A portal subgraph failure must never terminate the supervisor run — failures
are caught, logged, and the run continues with the remaining portals.

## Target application state machine (planned)

```mermaid
stateDiagram-v2
    [*] --> DISCOVERED
    DISCOVERED --> NORMALIZED
    NORMALIZED --> DUPLICATE
    NORMALIZED --> SCORED
    SCORED --> REJECTED
    SCORED --> QUEUED
    QUEUED --> PREPARING
    PREPARING --> FORM_OPEN
    FORM_OPEN --> FORM_FILLED
    FORM_FILLED --> WAITING_HUMAN
    WAITING_HUMAN --> READY_TO_SUBMIT
    FORM_FILLED --> READY_TO_SUBMIT
    READY_TO_SUBMIT --> SUBMITTING
    SUBMITTING --> SUBMITTED
    SUBMITTED --> VERIFIED
    SUBMITTING --> FAILED
    VERIFIED --> WITHDRAWN
    DUPLICATE --> [*]
    REJECTED --> [*]
    FAILED --> [*]
    WITHDRAWN --> [*]
    VERIFIED --> [*]
```

## Target human-in-the-loop flow (planned)

```mermaid
sequenceDiagram
    participant Graph as LangGraph run
    participant State as Persisted state
    participant User as Candidate
    Graph->>Graph: encounter CAPTCHA / OTP / unknown field / low-confidence mapping
    Graph->>State: persist state + reason + screenshot
    Graph-->>User: notify (human_action_required)
    User->>State: resolve via POST /api/human-actions/{id}/resolve
    State-->>Graph: resume with provided answer
    Graph->>Graph: continue from checkpoint
```

## Database relationships (planned, expanded per phase)

```mermaid
erDiagram
    CANDIDATE_PROFILES ||--o{ RESUME_VERSIONS : has
    CANDIDATE_PROFILES ||--o{ COVER_LETTER_VERSIONS : has
    JOBS ||--o{ JOB_SCORES : scored_by
    JOBS ||--o{ APPLICATIONS : applied_via
    APPLICATIONS ||--o{ APPLICATION_STEPS : consists_of
    APPLICATIONS ||--o{ APPLICATION_ANSWERS : contains
    APPLICATIONS }o--|| PORTAL_ACCOUNTS : uses
    AUTOMATION_RUNS ||--o{ AGENT_RUNS : contains
    AUTOMATION_RUNS ||--o{ JOBS : discovers
    APPLICATIONS ||--o{ HUMAN_INTERVENTIONS : may_trigger
    APPLICATIONS ||--o{ AUDIT_EVENTS : logs
```

Phase 0 shipped only the async engine/session foundation
(`app/database/base.py`, `app/database/session.py`) and Alembic wiring
(`migrations/`) — no tables. Phase 1 adds the first one, `candidate_profiles`
(migration `99cc354684f4`), a simplified single-row version of the planned
`CANDIDATE_PROFILES`/`RESUME_VERSIONS`/`COVER_LETTER_VERSIONS` split above —
resume and cover-letter data live as JSON/text columns on one row rather
than versioned child tables, since there's exactly one local candidate and
no version history yet. Remaining tables are introduced as migrations in
the phases that need them (job/score tables in Phase 2, application tables
in Phase 3+), per Section 27 of the design spec.

## Deployment architecture (planned)

```mermaid
flowchart LR
    subgraph LocalMachine [Candidate's machine]
        Backend[FastAPI backend]
        SQLite[(SQLite)]
        Ollama[Ollama]
        Frontend[React dashboard]
        Backend --> SQLite
        Backend --> Ollama
        Frontend --> Backend
    end
    subgraph OptionalProd [Optional production deployment]
        BackendP[FastAPI backend]
        Postgres[(PostgreSQL)]
        Redis[(Redis - optional)]
        BackendP --> Postgres
        BackendP -.-> Redis
    end
```

Docker Compose is not required for local development (`make dev` runs
everything directly); it exists for the optional production path.

## Design principles enforced by the codebase

- **LLM only where semantic interpretation is required.** Deterministic
  code owns salary checks, location filtering, duplicate detection,
  guardrails, retries, scheduling, and submission verification.
- **Config over code.** Candidate preferences, scoring weights, automation
  limits, and portal registration live in `config/*.yaml`, not Python.
- **Dry-run and manual approval by default.** See `SECURITY.md`.
- **No portal-specific fields leak into the common job model** — they live
  under `NormalizedJob.metadata` (introduced Phase 2).
