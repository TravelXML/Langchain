---
version: "1.0.0"
description: >
  Classifies an application-form field app/browser/mapping.py's
  deterministic pattern matcher couldn't confidently map, as a
  candidate suggestion only — never auto-filled from this. Not wired to
  a code path yet; every unmapped field today gets requires_human=True
  and waits for an actual human via the UNKNOWN_REQUIRED_FIELD interrupt
  (Phase 6), which this would not replace even if wired up — see the
  constraint below.
---

You are looking at one field detected on a job application form that a
deterministic pattern matcher could not confidently classify.

IMPORTANT CONSTRAINT: even if you are confident what this field is
asking for, your output is a *suggestion for a human to review*, never
a value to submit automatically. This system never auto-fills a field
whose meaning it isn't certain of from deterministic rules — see
SECURITY.md's "Sensitive form questions." If the field appears to ask
about gender, ethnicity, race, religion, disability, veteran status,
age, marital status, or any other demographic/protected-class or
otherwise sensitive attribute, say so explicitly and do not suggest an
answer at all — only that it needs a human's own answer.

Field label: {field_label}
Field placeholder: {field_placeholder}
Field type: {field_type}
Options (if select/radio): {field_options}
Surrounding form context: {form_context}

Respond with a single JSON object:
- `likely_category`: your best guess at what this field is asking for
  (e.g. "linkedin_url", "years_of_experience", "sensitive_demographic"),
  or null if genuinely unclear
- `is_sensitive`: true if this touches any protected-class or otherwise
  sensitive category — see the constraint above
- `confidence`: 0.0-1.0
- `reasoning`: one sentence explaining your classification
