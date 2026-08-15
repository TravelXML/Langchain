from __future__ import annotations

import pytest

from app.llm.prompts import load_prompt

_REAL_PROMPTS = [
    "resume_parser",
    "job_parser",
    "job_matcher",
    "form_classifier",
    "answer_generator",
    "cover_letter",
    "supervisor",
]


@pytest.mark.parametrize("name", _REAL_PROMPTS)
def test_every_real_prompt_file_loads_with_version_and_content(name):
    prompt = load_prompt(name)
    assert prompt.name == name
    assert prompt.version  # every real prompt file sets a version
    assert prompt.description
    assert prompt.content  # never just an empty/whitespace body


def test_load_prompt_missing_file_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_prompt("does_not_exist", prompts_dir=tmp_path)


def test_load_prompt_without_frontmatter_still_loads(tmp_path):
    (tmp_path / "plain.md").write_text("Just a plain prompt, no frontmatter.")
    prompt = load_prompt("plain", prompts_dir=tmp_path)
    assert prompt.version == "0.0.0"
    assert prompt.description == ""
    assert prompt.content == "Just a plain prompt, no frontmatter."


def test_load_prompt_parses_frontmatter_fields(tmp_path):
    (tmp_path / "custom.md").write_text(
        '---\nversion: "2.1.0"\ndescription: "does a thing"\n---\n\nThe actual prompt body.\n'
    )
    prompt = load_prompt("custom", prompts_dir=tmp_path)
    assert prompt.version == "2.1.0"
    assert prompt.description == "does a thing"
    assert prompt.content == "The actual prompt body."
