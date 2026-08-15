---
version: "1.0.0"
description: >
  Drafts a cover letter strictly from facts in the candidate's profile
  and the target job posting — a draft for the candidate to review and
  edit, never auto-submitted. Not wired to a code path yet — Phase 1's
  cover_letter_service only stores/parses an existing uploaded cover
  letter, it doesn't generate one.
---

You are drafting a cover letter for a specific job application. This
draft will be shown to the candidate for review and editing before
anything is submitted — it is never submitted directly.

Use ONLY facts present in the candidate profile below — experience,
skills, achievements exactly as stated. Do not invent, embellish, or
round up any detail (years of experience, company names, quantified
achievements) beyond what the profile actually states — see
SECURITY.md's "the system will never fabricate candidate information."

Tie the candidate's actual, stated experience to the job posting's
actual, stated requirements — don't write generic enthusiasm that could
apply to any job. If the profile is thin on relevant detail for this
specific role, keep the letter honest and appropriately brief rather
than padding it with generic claims.

Target length: 3-4 short paragraphs.

Company: {company}
Job title: {job_title}
Job description: {job_description}

Candidate profile (facts only — do not go beyond this):
{candidate_profile_summary}

Respond with a single JSON object:
- `draft_cover_letter`: the drafted letter text
- `used_profile_facts`: list of the specific profile facts you drew on,
  so the candidate can quickly verify nothing was invented
- `confidence`: 0.0-1.0, how well-supported this draft is by the profile
