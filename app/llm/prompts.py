"""Versioned prompt loader (Section 39: "do not scatter prompts
throughout Python files").

Each `prompts/<name>.md` file is a template with a small YAML
frontmatter block (``version``, ``description``) followed by the actual
prompt text. Loading is uncached and reads the file fresh every call —
these are small local files edited directly, not a hot path, so there's
no caching complexity to get wrong here (contrast `YamlConfigLoader`,
which caches because `config/*.yaml` is read constantly).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

_DEFAULT_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    description: str
    content: str


def _split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end == -1:
        return {}, text
    frontmatter_text = text[4:end]
    body = text[end + 5 :].lstrip("\n")
    parsed = yaml.safe_load(frontmatter_text) or {}
    return parsed, body


def load_prompt(name: str, *, prompts_dir: Path | None = None) -> Prompt:
    directory = prompts_dir or _DEFAULT_PROMPTS_DIR
    path = directory / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"prompt not found: {path}")

    frontmatter, body = _split_frontmatter(path.read_text(encoding="utf-8"))
    return Prompt(
        name=name,
        version=str(frontmatter.get("version", "0.0.0")),
        description=str(frontmatter.get("description", "")),
        content=body.strip(),
    )
