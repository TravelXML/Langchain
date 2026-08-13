from __future__ import annotations

from pathlib import Path

from app.core.config import YamlConfigLoader, get_settings


def test_settings_defaults_are_safe():
    settings = get_settings()
    assert settings.automation_dry_run is True
    assert settings.approval_mode == "manual"


def test_yaml_config_loader_reads_and_caches(tmp_path: Path):
    config_dir = tmp_path
    (config_dir / "sample.yaml").write_text("foo:\n  bar: 1\n")

    loader = YamlConfigLoader(config_dir=config_dir)
    data = loader.load("sample")
    assert data == {"foo": {"bar": 1}}

    # mutate underlying file; cached value should not change until reload()
    (config_dir / "sample.yaml").write_text("foo:\n  bar: 2\n")
    assert loader.load("sample") == {"foo": {"bar": 1}}
    assert loader.reload("sample") == {"foo": {"bar": 2}}


def test_yaml_config_loader_interpolates_env_vars(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SAMPLE_VALUE", "resolved")
    (tmp_path / "with_env.yaml").write_text("key: ${SAMPLE_VALUE}\nunset: ${NOT_SET_VAR}\n")

    loader = YamlConfigLoader(config_dir=tmp_path)
    data = loader.load("with_env")
    assert data["key"] == "resolved"
    assert data["unset"] == ""


def test_candidate_yaml_loads_from_project_config_dir():
    loader = YamlConfigLoader(config_dir=Path("./config"))
    data = loader.load("candidate")
    assert "candidate" in data
    assert "minimum_match_score" in data["candidate"]
