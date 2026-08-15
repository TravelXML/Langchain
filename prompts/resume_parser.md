---
version: "1.0.0"
description: >
  Extracts structured candidate fields from raw resume text, for fields
  app/profile/parser.py's deterministic extractor can't derive with a
  defensible rule (previous titles, companies, industries). Not wired
  to a code path yet — app/profile/parser.py remains the sole extractor.
---

You are extracting structured information from a candidate's resume.
Return ONLY fields you can support with text actually present in the
resume below. If a field isn't stated or can't be reasonably inferred,
set its value to null and confidence to 0.0 — never guess, never invent
a plausible-sounding value.

Every field you return must include:
- `value`: the extracted value, or null
- `confidence`: 0.0-1.0, your honest confidence this value is correct
- `source`: always "llm" (the caller sets this)

Do not extract or infer, under any circumstance: gender, ethnicity,
race, religion, disability status, age, marital status, national
origin, or any other demographic/protected-class attribute, even if the
resume's name, photo, or other details might suggest one. These fields
have no place in this system's candidate model.

Fields to extract (skip any not present in the resume):
- `previous_titles`: list of job titles held, most recent first
- `previous_companies`: list of company names worked at, most recent first
- `industries`: list of industries/sectors the candidate has worked in
- `seniority_level`: one of "junior", "mid", "senior", "staff",
  "principal", "executive" — only if the resume's own language supports
  it (explicit titles, years of experience stated), not a guess from
  company prestige or resume length

Resume text:
{resume_text}

Respond with a single JSON object only, no prose before or after it.
