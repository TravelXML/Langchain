---
version: "1.0.0"
description: >
  Extracts structured fields from a raw job posting for portals whose
  postings don't cleanly separate structured fields (salary, employment
  type, required vs. preferred skills) from free-text description. Not
  wired to a code path yet — every portal adapter today
  (app/portals/greenhouse, app/portals/lever) parses structured API
  fields directly, with no LLM step.
---

You are extracting structured fields from a raw job posting's text.
Return ONLY fields you can support with text actually present in the
posting below — if the posting doesn't state something (e.g. no salary
range is given), set that field to null rather than estimating a
plausible market rate.

Fields to extract:
- `required_skills`: list of skills explicitly stated as required/must-have
- `preferred_skills`: list of skills stated as preferred/nice-to-have
  (do not merge these into required_skills)
- `minimum_experience`: minimum years of experience stated, or null
- `maximum_experience`: maximum years of experience stated, or null
- `salary_min` / `salary_max` / `salary_currency`: only if a concrete
  range is stated in the posting text
- `employment_type`: one of "full_time", "part_time", "contract",
  "internship" — only if explicitly stated or unambiguous from context
  (e.g. "40 hours/week, full benefits" implies full_time; a listing that
  never mentions this should get null, not a default)

Job posting text:
{job_text}

Respond with a single JSON object only, no prose before or after it.
