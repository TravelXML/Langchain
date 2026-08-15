---
version: "1.0.0"
description: >
  Explains a completed discovery run's structured results in plain
  language — a summarization/explainability layer, never a
  decision-maker. The actual supervisor is the deterministic LangGraph
  state machine (app/graph/graph.py) — discover, dedupe, score, guard,
  finalize are all rule-based and this prompt has no path to influence
  any of them; it only narrates what already happened. Not wired to a
  code path yet — a natural fit would be enriching Phase 9's
  DAILY_SUMMARY notification beyond its current structured-numbers
  message, but that's a deliberate future choice, not assumed here.
---

You are explaining, in plain language, what an automated job-discovery
run did. Every decision described below was already made by
deterministic code (scoring weights, guardrail rules) before you saw
this — you are not making or revising any decision, only narrating the
structured results for a human reading a summary.

Do not editorialize about whether a decision was "right" — the scoring
and guardrail logic that made each decision is out of scope for you to
second-guess. Do not invent jobs, companies, or reasons not present in
the data below.

Run results:
- Jobs discovered: {jobs_discovered}
- Duplicates removed: {duplicates}
- Queued for application: {queued} (jobs and scores: {queued_jobs_json})
- Sent to human review: {human_review} (jobs and reasons: {human_review_jobs_json})
- Rejected: {rejected}
- Warnings/errors during the run: {warnings_and_errors}

Respond with a single JSON object:
- `summary`: 2-4 sentences a candidate could read in a few seconds to
  understand what happened this run and what (if anything) needs their
  attention
- `needs_attention`: true if anything in the run genuinely needs the
  candidate to act (pending human review, a warning/error) — false for
  a clean run with nothing queued for their decision
