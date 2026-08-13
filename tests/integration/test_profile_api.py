from __future__ import annotations

from tests.fixtures.pdf_builder import build_pdf_bytes

RESUME_LINES = [
    "Taylor Morgan Reed",
    "taylor.reed@example.com",
    "+1 212-555-0199",
    "",
    "SUMMARY",
    "Product engineering leader with 9 years experience.",
    "",
    "SKILLS",
    "Python, AWS, Docker",
    "",
    "EDUCATION",
    "B.S. Computer Science",
]

COVER_LETTER_LINES = [
    "Dear Hiring Manager,",
    "I am excited to apply for this role.",
]


async def test_import_profile_via_api(client):
    resume_bytes = build_pdf_bytes(RESUME_LINES)
    cover_letter_bytes = build_pdf_bytes(COVER_LETTER_LINES)

    response = await client.post(
        "/api/profile/import",
        files={
            "resume": ("resume.pdf", resume_bytes, "application/pdf"),
            "cover_letter": ("cover_letter.pdf", cover_letter_bytes, "application/pdf"),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["resume"]["email"]["value"] == "taylor.reed@example.com"
    assert body["resume"]["experience_years"]["value"] == 9.0
    assert body["cover_letter_text"] is not None
    assert "Dear Hiring Manager" in body["cover_letter_text"]


async def test_get_profile_after_import(client):
    resume_bytes = build_pdf_bytes(RESUME_LINES)
    await client.post(
        "/api/profile/import",
        files={"resume": ("resume.pdf", resume_bytes, "application/pdf")},
    )

    response = await client.get("/api/profile")
    assert response.status_code == 200
    assert response.json()["resume"]["email"]["value"] == "taylor.reed@example.com"


async def test_get_profile_404_before_import(client):
    response = await client.get("/api/profile")
    assert response.status_code == 404


async def test_update_preferences(client):
    resume_bytes = build_pdf_bytes(RESUME_LINES)
    await client.post(
        "/api/profile/import",
        files={"resume": ("resume.pdf", resume_bytes, "application/pdf")},
    )

    payload = {
        "target_positions": ["CTO", "VP Engineering"],
        "minimum_match_score": 80,
        "maximum_applications_per_day": 10,
    }
    response = await client.put("/api/profile", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["preferences"]["target_positions"] == ["CTO", "VP Engineering"]
    assert body["preferences"]["minimum_match_score"] == 80


async def test_import_rejects_non_pdf(client):
    response = await client.post(
        "/api/profile/import",
        files={"resume": ("resume.txt", b"not a pdf", "text/plain")},
    )
    assert response.status_code == 400
