"""Real Playwright, real (local) HTML fixtures — no production portals
(Section 42: "run automation against local fixtures first").
"""

from __future__ import annotations

from pathlib import Path

from app.browser.forms import detect_fields, fill_form, upload_file, validate_form
from app.browser.mapping import map_fields
from app.browser.screenshots import attach_console_logger, capture_failure_artifacts
from tests.e2e.conftest import fixture_url
from tests.fixtures.job_builder import make_profile
from tests.fixtures.pdf_builder import build_pdf_bytes


async def test_detect_fields_on_simple_form(page):
    await page.goto(fixture_url("simple_application_form.html"))
    fields = await detect_fields(page)

    names = {f.name for f in fields}
    assert names == {"full_name", "email", "phone", "experience_years"}
    email_field = next(f for f in fields if f.name == "email")
    assert email_field.field_type == "email"
    assert email_field.label == "Email"
    assert email_field.selector == '[data-testid="email-input"]'  # testid wins per Section 11


async def test_map_and_fill_simple_form(page):
    await page.goto(fixture_url("simple_application_form.html"))
    fields = await detect_fields(page)
    mappings = map_fields(fields, make_profile())
    result = await fill_form(page, fields, mappings)

    assert set(result.filled) == {"email", "experience_years"}
    # phone/full_name aren't on the default test profile's resume — see
    # tests/fixtures/job_builder.make_resume, which only sets email +
    # experience_years — so they're correctly skipped, not guessed.
    assert set(result.skipped_for_human) == {"full_name", "phone"}
    assert await page.input_value('[data-testid="email-input"]') == "jordan@example.com"
    assert await page.input_value('[data-testid="experience-input"]') == "15"

    await page.click('[data-testid="submit-button"]')
    assert await page.is_visible("#result")


async def test_required_fields_validation_catches_missing_values(page):
    await page.goto(fixture_url("required_fields_form.html"))
    invalid = await validate_form(page)
    assert set(invalid) >= {"email", "phone"}

    await page.fill('[data-testid="email-input"]', "jordan@example.com")
    await page.fill('[data-testid="phone-input"]', "+1 415 555 0134")
    invalid_after = await validate_form(page)
    assert invalid_after == []


async def test_dropdown_form_select_is_case_insensitive(page):
    """config/candidate.yaml stores work_mode lowercase ("remote"); this
    fixture's option label is "Remote" — proves the case-insensitive
    fallback in forms.py actually fires against a real <select>."""
    await page.goto(fixture_url("dropdown_form.html"))
    fields = await detect_fields(page)
    profile = make_profile()
    profile.preferences.work_mode = ["remote"]
    mappings = map_fields(fields, profile)

    result = await fill_form(page, fields, mappings)
    assert "work_mode" in result.filled
    assert result.errors == []
    selected_label = await page.eval_on_selector(
        '[data-testid="work-mode-select"]', "el => el.options[el.selectedIndex].textContent"
    )
    assert selected_label == "Remote"


async def test_file_upload(page, tmp_path: Path):
    await page.goto(fixture_url("resume_upload_form.html"))
    fields = await detect_fields(page)
    resume_field = next(f for f in fields if f.name == "resume")

    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(build_pdf_bytes(["Jordan Casey Smith", "jordan@example.com"]))

    await upload_file(page, resume_field, pdf_path)
    await page.fill('[data-testid="email-input"]', "jordan@example.com")
    await page.click('[data-testid="submit-button"]')

    result_text = await page.text_content('[data-testid="result"]')
    assert "resume.pdf" in result_text


async def test_multi_step_form_navigation(page):
    await page.goto(fixture_url("multi_step_form.html"))

    step1_fields = await detect_fields(page)
    step1_names = {f.name for f in step1_fields}
    assert step1_names == {"full_name", "email"}  # step 2's fields are hidden, correctly excluded

    await page.fill('[data-testid="full-name-input"]', "Jordan Casey Smith")
    await page.fill('[data-testid="email-input"]', "jordan@example.com")
    await page.click('[data-testid="next-button"]')

    step2_fields = await detect_fields(page)
    step2_names = {f.name for f in step2_fields}
    assert step2_names == {"current_title", "experience_years"}

    await page.fill('[data-testid="current-title-input"]', "VP Engineering")
    await page.fill('[data-testid="experience-input"]', "12")
    await page.click('[data-testid="submit-button"]')

    assert await page.is_visible('[data-testid="result"]')


async def test_unknown_field_is_flagged_for_human_not_guessed(page):
    await page.goto(fixture_url("unknown_field_form.html"))
    fields = await detect_fields(page)
    mappings = map_fields(fields, make_profile())
    result = await fill_form(page, fields, mappings)

    assert "email" in result.filled
    assert "fav_language" in result.skipped_for_human
    assert await page.input_value('[data-testid="fav-language-input"]') == ""


async def test_screenshot_and_html_snapshot_captured_on_failure(page, tmp_path, monkeypatch):
    from app.core import config as config_module

    monkeypatch.setattr(config_module.get_settings(), "browser_artifacts_dir", tmp_path)

    await page.goto(fixture_url("simple_application_form.html"))
    console_logs = attach_console_logger(page)
    await page.evaluate("console.log('simulated failure diagnostic')")

    artifacts = await capture_failure_artifacts(page, "simple_form_failure", console_logs)

    assert artifacts.screenshot_path.exists()
    assert artifacts.screenshot_path.stat().st_size > 0
    assert artifacts.html_path.exists()
    assert "Apply for Senior Engineer" in artifacts.html_path.read_text()
    assert any("simulated failure diagnostic" in line for line in artifacts.console_logs)


async def test_one_bad_field_selector_does_not_abort_the_whole_fill(page):
    """A field whose selector doesn't resolve on the page (e.g. the DOM
    changed since detection) must be reported in ``errors``, not crash the
    fill — the rest of the form should still get filled."""
    await page.goto(fixture_url("simple_application_form.html"))
    fields = await detect_fields(page)
    mappings = map_fields(fields, make_profile())

    email_index = next(i for i, f in enumerate(fields) if f.name == "email")
    broken_field = fields[email_index].model_copy(update={"selector": "#does-not-exist"})
    fields[email_index] = broken_field

    result = await fill_form(page, fields, mappings)

    assert any("email" in e for e in result.errors)
    assert "experience_years" in result.filled  # unaffected by the broken email selector
    assert await page.input_value('[data-testid="experience-input"]') == "15"


async def test_otp_and_captcha_fixtures_load_correctly(page):
    await page.goto(fixture_url("otp_screen.html"))
    assert await page.is_visible('[data-testid="otp-input"]')

    await page.goto(fixture_url("captcha_screen.html"))
    assert await page.is_visible('[data-testid="captcha-widget"]')
    assert await page.is_disabled('[data-testid="continue-button"]')


async def test_success_and_failure_page_fixtures_load_correctly(page):
    await page.goto(fixture_url("success_page.html"))
    assert await page.text_content('[data-testid="confirmation-reference"]') == "APP-2026-00042"

    await page.goto(fixture_url("failure_page.html"))
    assert await page.is_visible('[data-testid="error-message"]')
