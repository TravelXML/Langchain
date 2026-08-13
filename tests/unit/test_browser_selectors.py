from __future__ import annotations

import pytest

from app.browser.errors import SelectorNotFoundError
from app.browser.selectors import build_selector


def test_testid_takes_priority_over_everything():
    selector = build_selector(
        testid="email-input", aria_label="Email", name="email", elem_id="email"
    )
    assert selector == '[data-testid="email-input"]'


def test_aria_label_used_when_no_testid():
    selector = build_selector(aria_label="Email", name="email", elem_id="email")
    assert selector == '[aria-label="Email"]'


def test_role_used_when_no_testid_or_aria_label():
    selector = build_selector(role="button", name="submit")
    assert selector == '[role="button"]'


def test_name_used_when_only_name_and_id_available():
    selector = build_selector(name="email", elem_id="email-field")
    assert selector == '[name="email"]'


def test_id_used_when_only_id_available():
    selector = build_selector(elem_id="email-field")
    assert selector == "#email-field"


def test_css_used_as_stable_fallback():
    selector = build_selector(css="form#apply input.email")
    assert selector == "form#apply input.email"


def test_text_used_as_last_resort():
    selector = build_selector(text="Submit Application")
    assert selector == 'text="Submit Application"'


def test_raises_when_nothing_available():
    with pytest.raises(SelectorNotFoundError):
        build_selector()
