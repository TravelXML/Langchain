"""Mock portals for Phase 3 (Section 51: "initially use mocked portals").

Each mock returns raw job dicts in the shape ``app.jobs.parser.normalize_job``
expects. This is deliberately *not* a real ``JobPortalAdapter`` (that
interface lands in Phase 7) — it's a stand-in just complete enough to
exercise discover → normalize → dedupe → score → reject/queue end to end.

The two portals share one job (same company/title-family/location) on
purpose, to exercise cross-portal duplicate detection.
"""

from __future__ import annotations

from typing import Any


def discover_mock_greenhouse(search_policy: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "external_job_id": "gh-101",
            "url": "https://boards.greenhouse.io/acme/jobs/101",
            "title": "CTO",
            "company": "Acme SaaS",
            "location": "Bengaluru, India",
            "work_mode": "remote",
            "salary_min": 45,
            "salary_max": 65,
            "salary_currency": "INR",
            "description": "Own the technology roadmap for our SaaS platform.",
            "required_skills": ["Cloud Architecture", "Engineering Leadership", "AWS"],
            "preferred_skills": ["Agentic AI", "Kubernetes"],
            "minimum_experience": 15,
            "industry": "SaaS",
            "employment_type": "full_time",
        },
        {
            "external_job_id": "gh-102",
            "url": "https://boards.greenhouse.io/acme/jobs/102",
            "title": "Sales Associate",
            "company": "Retail Co",
            "location": "Mumbai, India",
            "work_mode": "onsite",
            "salary_min": 4,
            "salary_max": 6,
            "salary_currency": "INR",
            "description": "Drive in-store sales for our retail chain.",
            "required_skills": ["Retail Sales", "POS Systems"],
            "preferred_skills": [],
            "minimum_experience": 1,
            "industry": "Retail",
            "employment_type": "full_time",
        },
        {
            "external_job_id": "gh-103",
            "url": "https://boards.greenhouse.io/beta/jobs/103",
            "title": "VP Engineering",
            "company": "Beta Cloud",
            "location": "Berlin, Germany",
            "work_mode": "onsite",
            "salary_min": 35,
            "salary_max": 50,
            "salary_currency": "EUR",
            "description": "Lead the engineering org for our cloud platform.",
            "required_skills": ["Engineering Leadership", "Microservices"],
            "preferred_skills": ["AWS"],
            "minimum_experience": 8,
            "industry": "Enterprise Software",
            "employment_type": "full_time",
        },
    ]


def discover_mock_lever(search_policy: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            # Same company + title family + location as gh-101 above —
            # exercises cross-portal duplicate detection.
            "external_job_id": "lever-201",
            "url": "https://jobs.lever.co/acme/201",
            "title": "Chief Technology Officer",
            "company": "Acme SaaS",
            "location": "Bengaluru, India",
            "work_mode": "remote",
            "salary_min": 45,
            "salary_max": 65,
            "salary_currency": "INR",
            "description": "Own the technology roadmap for our SaaS platform.",
            "required_skills": ["Cloud Architecture", "Engineering Leadership", "AWS"],
            "preferred_skills": ["Agentic AI", "Kubernetes"],
            "minimum_experience": 15,
            "industry": "SaaS",
            "employment_type": "full_time",
        },
        {
            "external_job_id": "lever-202",
            "url": "https://jobs.lever.co/gamma/202",
            "title": "Head of Engineering",
            "company": "Gamma Systems",
            "location": "Remote",
            "work_mode": "remote",
            "salary_min": 30,
            "salary_max": 45,
            "salary_currency": "INR",
            "description": "Lead a distributed engineering team.",
            "required_skills": ["Engineering Leadership", "Python"],
            "preferred_skills": ["AWS"],
            "minimum_experience": 10,
            "industry": "Enterprise Software",
            "employment_type": "full_time",
        },
        {
            "external_job_id": "lever-203",
            "url": "https://jobs.lever.co/delta/203",
            "title": "IT Director",
            "company": "Delta Corp",
            "location": "Mumbai, India",
            "work_mode": "onsite",
            "salary_min": 20,
            "salary_max": 28,
            "salary_currency": "INR",
            "description": "Run internal IT operations.",
            "required_skills": ["IT Operations", "Network Administration"],
            "preferred_skills": [],
            "minimum_experience": 6,
            "industry": "Manufacturing",
            "employment_type": "full_time",
        },
    ]


MOCK_PORTALS = {
    "mock_greenhouse": discover_mock_greenhouse,
    "mock_lever": discover_mock_lever,
}
