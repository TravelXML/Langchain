"""Field detection, filling, and validation (Section 20/42).

Detection runs a single ``page.evaluate`` (one DOM walk in JS) rather than
many round-trips per element — cheap and avoids the flakiness of
re-querying the DOM per field.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from playwright.async_api import Locator, Page

from app.browser.errors import FileUploadError, SelectorNotFoundError
from app.browser.models import DetectedField, FieldMapping, FieldType, FormFillResult
from app.browser.selectors import build_selector

_DETECT_FIELDS_JS = """
() => {
    const isVisible = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    const results = [];
    document.querySelectorAll('input, select, textarea').forEach((el) => {
        let defaultType = 'text';
        if (el.tagName === 'SELECT') defaultType = 'select';
        if (el.tagName === 'TEXTAREA') defaultType = 'textarea';
        const rawType = (el.getAttribute('type') || defaultType).toLowerCase();
        if (['hidden', 'submit', 'button', 'reset', 'image'].includes(rawType)) return;
        if (!isVisible(el)) return;

        let label = null;
        if (el.id) {
            const labelEl = document.querySelector(`label[for="${el.id}"]`);
            if (labelEl) label = labelEl.textContent.trim();
        }
        if (!label) {
            const parentLabel = el.closest('label');
            if (parentLabel) label = parentLabel.textContent.trim();
        }
        if (!label && el.getAttribute('aria-label')) {
            label = el.getAttribute('aria-label');
        }

        let options = [];
        if (el.tagName === 'SELECT') {
            options = Array.from(el.options).map((o) => o.textContent.trim()).filter(Boolean);
        }

        results.push({
            tag: el.tagName.toLowerCase(),
            type: rawType,
            name: el.getAttribute('name'),
            id: el.getAttribute('id'),
            testid: el.getAttribute('data-testid'),
            ariaLabel: el.getAttribute('aria-label'),
            placeholder: el.getAttribute('placeholder'),
            required: !!el.required,
            label,
            options,
        });
    });
    return results;
}
"""

_VALIDATE_FORM_JS = """
() => {
    const invalid = [];
    document.querySelectorAll('input, select, textarea').forEach((el) => {
        if (el.willValidate && !el.checkValidity()) {
            invalid.push(el.name || el.id || el.type);
        }
    });
    return invalid;
}
"""

_TYPE_MAP: dict[str, FieldType] = {
    "select": "select",
    "textarea": "textarea",
    "checkbox": "checkbox",
    "radio": "radio",
    "file": "file",
    "email": "email",
    "tel": "tel",
    "number": "number",
}


def _normalize_type(tag: str, raw_type: str) -> FieldType:
    if tag == "select":
        return "select"
    if tag == "textarea":
        return "textarea"
    return _TYPE_MAP.get(raw_type, "text" if raw_type in ("text", "search", "url") else "unknown")


async def detect_fields(page: Page) -> list[DetectedField]:
    raw_fields: list[dict[str, Any]] = await page.evaluate(_DETECT_FIELDS_JS)

    detected: list[DetectedField] = []
    for i, item in enumerate(raw_fields):
        try:
            selector = build_selector(
                testid=item.get("testid"),
                aria_label=item.get("ariaLabel"),
                name=item.get("name"),
                elem_id=item.get("id"),
            )
        except SelectorNotFoundError:
            fallback_text = item.get("label") or item.get("placeholder")
            selector = (
                build_selector(text=fallback_text)
                if fallback_text
                else f":nth-match(input, {i + 1})"
            )

        detected.append(
            DetectedField(
                name=item.get("name") or item.get("id") or f"field_{i}",
                label=item.get("label"),
                placeholder=item.get("placeholder"),
                field_type=_normalize_type(item["tag"], item["type"]),
                options=item.get("options") or [],
                required=item.get("required", False),
                selector=selector,
            )
        )
    return detected


async def _select_option_case_insensitive(locator: Locator, value: str) -> None:
    """Exact label match first; real portals sometimes differ only in
    casing from our stored value (e.g. config stores "remote", the page
    shows "Remote") — falls back to a case-insensitive option lookup
    rather than failing a mapping the engine was otherwise confident about.
    """
    try:
        await locator.select_option(label=value)
        return
    except Exception:
        pass

    matched_value = await locator.evaluate(
        """(el, target) => {
            const opt = Array.from(el.options).find(
                (o) => o.textContent.trim().toLowerCase() === target.toLowerCase()
            );
            return opt ? opt.value : null;
        }""",
        value,
    )
    if matched_value is None:
        raise SelectorNotFoundError(f"no option matching '{value}' found")
    await locator.select_option(value=matched_value)


async def fill_form(
    page: Page, fields: list[DetectedField], mappings: list[FieldMapping]
) -> FormFillResult:
    filled: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for field, mapping in zip(fields, mappings, strict=True):
        if mapping.requires_human or mapping.candidate_value is None:
            skipped.append(field.name)
            continue

        try:
            locator = page.locator(field.selector).first
            if field.field_type == "select":
                await _select_option_case_insensitive(locator, mapping.candidate_value)
            elif field.field_type == "checkbox":
                if mapping.candidate_value.strip().lower() in ("true", "yes", "1"):
                    await locator.check()
                else:
                    await locator.uncheck()
            elif field.field_type == "file":
                raise FileUploadError(
                    "file fields must be filled via upload_file(), not fill_form()"
                )
            else:
                await locator.fill(mapping.candidate_value)
            filled.append(field.name)
        except FileUploadError:
            raise
        except Exception as exc:  # a single field failure shouldn't abort the whole form
            errors.append(f"{field.name}: {exc}")

    return FormFillResult(
        mappings=mappings, filled=filled, skipped_for_human=skipped, errors=errors
    )


async def upload_file(page: Page, field: DetectedField, file_path: Path) -> None:
    if not file_path.exists():
        raise FileUploadError(f"file not found: {file_path}")
    try:
        await page.locator(field.selector).first.set_input_files(str(file_path))
    except Exception as exc:
        raise FileUploadError(f"failed to upload {file_path} to {field.name}: {exc}") from exc


async def validate_form(page: Page) -> list[str]:
    """Returns the names of fields currently failing HTML5 validation."""
    return await page.evaluate(_VALIDATE_FORM_JS)
