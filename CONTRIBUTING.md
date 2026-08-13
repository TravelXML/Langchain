# Contributing

## Workflow

This project is built in explicit, sequential phases (see
`ARCHITECTURE.md` and the master design spec under `prompt/`). Each phase:

1. Inspects the current repository and reads `ARCHITECTURE.md` and existing
   tests before changing anything.
2. Implements the smallest coherent increment for that phase.
3. Runs formatting, type checking, and tests.
4. Updates documentation.
5. Stops for review before the next phase begins.

Do not implement multiple phases in one pass, and do not build portal or
browser automation ahead of its designated phase.

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

## Before submitting changes

```bash
make lint
make format
make typecheck
make test
```

## Code style

- Async/await for I/O-bound code (FastAPI routes, DB access, HTTP calls).
- Small, typed functions; prefer composition over god classes.
- No hardcoded portal credentials, selectors as magic strings scattered
  through code, or candidate-specific data in Python — those belong in
  `config/*.yaml` or the database.
- Never use an LLM where a deterministic rule can safely produce the
  result (see Section 2 of the master design spec).

## Tests

- `tests/unit` — pure logic, no I/O.
- `tests/integration` — database, API, multi-component behavior.
- `tests/e2e` — full flows against local fixtures only.
- `tests/fixtures` / `tests/mocks` — HTML fixtures and mock adapters.

Never run real job applications from automated tests. Portal tests must use
mocked pages or local fixtures, never production job sites.
