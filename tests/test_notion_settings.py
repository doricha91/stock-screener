from __future__ import annotations

from pathlib import Path

import pytest

from core.notion_settings import (
    NotionSettings,
    NotionSettingsError,
    get_notion_data_source_id,
    get_notion_database_id,
    get_notion_token,
    load_notion_settings,
)


def test_settings_loader_reads_token_env_and_data_sources(tmp_path: Path):
    path = tmp_path / "notion_settings.json"
    path.write_text(
        '{"enabled": true, "token_env": "NOTION_TOKEN", "data_sources": {"smoke_test": "abc"}}',
        encoding="utf-8",
    )
    settings = load_notion_settings(path)
    token = get_notion_token(settings, env={"NOTION_TOKEN": "secret"})
    assert settings.enabled is True
    assert settings.data_sources["smoke_test"] == "abc"
    assert settings.databases["smoke_test"] == "abc"
    assert token == "secret"


def test_settings_loader_supports_deprecated_databases_fallback(tmp_path: Path):
    path = tmp_path / "notion_settings.json"
    path.write_text(
        '{"enabled": true, "token_env": "NOTION_TOKEN", "databases": {"smoke_test": "legacy-id"}}',
        encoding="utf-8",
    )
    settings = load_notion_settings(path)
    assert settings.data_sources == {}
    assert get_notion_data_source_id(settings, "smoke_test", env={}) == "legacy-id"


def test_missing_token_raises_clear_error(tmp_path: Path):
    path = tmp_path / "notion_settings.json"
    path.write_text(
        '{"enabled": true, "token_env": "NOTION_TOKEN", "data_sources": {"smoke_test": "abc"}}',
        encoding="utf-8",
    )
    settings = load_notion_settings(path)
    with pytest.raises(NotionSettingsError):
        get_notion_token(settings, env={})


def test_missing_data_source_id_raises_clear_error(tmp_path: Path):
    path = tmp_path / "notion_settings.json"
    path.write_text(
        '{"enabled": true, "token_env": "NOTION_TOKEN", "data_sources": {"smoke_test": ""}}',
        encoding="utf-8",
    )
    settings = load_notion_settings(path)
    with pytest.raises(NotionSettingsError, match="data source id"):
        get_notion_data_source_id(settings, "smoke_test", env={})


def test_env_override_data_source_id_is_supported():
    settings = NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={"smoke_test": ""},
    )
    value = get_notion_data_source_id(
        settings,
        "smoke_test",
        env={"NOTION_SMOKE_DATA_SOURCE_ID": "override-id"},
        env_override="NOTION_SMOKE_DATA_SOURCE_ID",
    )
    assert value == "override-id"


def test_data_sources_override_deprecated_databases():
    settings = NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={"smoke_test": "official-id"},
        databases={"smoke_test": "legacy-id"},
    )
    assert get_notion_data_source_id(settings, "smoke_test", env={}) == "official-id"


def test_database_id_wrapper_uses_data_source_lookup():
    settings = NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={"smoke_test": "official-id"},
    )
    assert get_notion_database_id(settings, "smoke_test", env={}) == "official-id"
