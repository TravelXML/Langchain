"""Application configuration.

Two layers, deliberately kept separate:

- ``Settings`` (this module): environment-driven, read once from ``.env`` /
  the process environment. Covers secrets, deployment mode, and anything
  that differs between machines.
- ``YamlConfigLoader``: domain configuration under ``config/*.yaml``
  (candidate preferences, scoring weights, portal registry, ...). Editable
  by the user / future UI without touching Python or restarting with new
  env vars.
"""

from __future__ import annotations

import functools
import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class Settings(BaseSettings):
    """Process-level settings, sourced from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    log_format: str = Field(default="json", alias="LOG_FORMAT")

    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/job_automation.db", alias="DATABASE_URL"
    )

    llm_provider: str = Field(default="ollama", alias="LLM_PROVIDER")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="", alias="OLLAMA_MODEL")
    llm_temperature: float = Field(default=0.0, alias="LLM_TEMPERATURE")
    llm_timeout_seconds: int = Field(default=120, alias="LLM_TIMEOUT_SECONDS")

    fallback_llm_enabled: bool = Field(default=False, alias="FALLBACK_LLM_ENABLED")
    fallback_llm_base_url: str = Field(default="", alias="FALLBACK_LLM_BASE_URL")
    fallback_llm_api_key: SecretStr = Field(default=SecretStr(""), alias="FALLBACK_LLM_API_KEY")
    fallback_llm_model: str = Field(default="", alias="FALLBACK_LLM_MODEL")

    automation_dry_run: bool = Field(default=True, alias="AUTOMATION_DRY_RUN")
    approval_mode: str = Field(default="manual", alias="APPROVAL_MODE")

    config_dir: Path = Field(default=Path("./config"), alias="CONFIG_DIR")


@functools.lru_cache
def get_settings() -> Settings:
    return Settings()


def _interpolate_env(value: Any) -> Any:
    """Recursively replace ``${VAR}`` placeholders with environment values.

    Unset variables resolve to an empty string rather than raising, since
    YAML config files are allowed to reference optional env vars (e.g. the
    fallback LLM settings).
    """
    if isinstance(value, str):
        return _ENV_VAR_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate_env(v) for v in value]
    return value


class YamlConfigLoader:
    """Loads and caches YAML files from the configured config directory."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._config_dir = config_dir or get_settings().config_dir
        self._cache: dict[str, dict[str, Any]] = {}

    def load(self, name: str) -> dict[str, Any]:
        """Load ``config/<name>.yaml`` (without extension), cached after first read."""
        if name in self._cache:
            return self._cache[name]

        path = self._config_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")

        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        resolved = _interpolate_env(raw)
        self._cache[name] = resolved
        return resolved

    def reload(self, name: str) -> dict[str, Any]:
        self._cache.pop(name, None)
        return self.load(name)


@functools.lru_cache
def get_yaml_config_loader() -> YamlConfigLoader:
    return YamlConfigLoader()
