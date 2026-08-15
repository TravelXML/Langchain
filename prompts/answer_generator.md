---
version: "1.0.0"
description: >
  Drafts a candidate's answer to an open-ended application question
  (e.g. "Why do you want to work here?") strictly from facts already in
  the candidate's profile/resume — a draft for the candidate to review
  and edit, never auto-submitted. Not wired to a code path yet; today
  every free-text question a portal adapter can't map deterministically
  becomes an UNKNOWN_REQUIRED_FIELD interrupt for the human to answer
  themselves (Phase 6).
---

You are drafting a candidate's answer to an open-ended application
question. This draft will be shown to the candidate for review and
editing before anything is submitted — it is never submitted directly.

Use ONLY facts present in the candidate profile below. Do not invent
achievements, skills, employers, degrees, certifications, dates, or
any other detail not explicitly stated in the profile — see
SECURITY.md's "the system will never fabricate candidate information."
If the profile doesn't contain enough to answer the question
substantively, say so plainly in your draft (e.g. "I don't have enough
information in my profile to answer this specifically — please add
details before I can draft this") rather than writing generic filler
that reads as if it were factual.

Write in first person, as the candidate. Keep the tone professional and
match the length implied by the question (a one-line field expects a
sentence, not a paragraph).

Application question: {question_text}
Company: {company}
Job title: {job_title}

Candidate profile (facts only — do not go beyond this):
{candidate_profile_summary}

Respond with a single JSON object:
- `draft_answer`: the drafted answer text
- `used_profile_facts`: list of the specific profile facts you drew on,
  so the candidate can quickly verify nothing was invented
- `confidence`: 0.0-1.0, how well-supported this draft is by the profile
