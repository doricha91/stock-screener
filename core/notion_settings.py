from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


class NotionSettingsError(RuntimeError):
    pass


def _normalize_mapping(mapping: dict[str, str] | None) -> dict[str, str]:
    if not mapping:
        return {}
    return {str(key): str(value or "").strip() for key, value in mapping.items()}


@dataclass(frozen=True, init=False)
class NotionSettings:
    enabled: bool
    token_env: str
    data_sources: dict[str, str]
    path: Path | None = None
    _deprecated_databases: dict[str, str] = field(default_factory=dict, repr=False)

    def __init__(
        self,
        *,
        enabled: bool,
        token_env: str,
        data_sources: dict[str, str] | None = None,
        path: Path | None = None,
        databases: dict[str, str] | None = None,
        deprecated_databases: dict[str, str] | None = None,
    ) -> None:
        normalized_data_sources = _normalize_mapping(
            data_sources if data_sources is not None else databases
        )
        normalized_deprecated = _normalize_mapping(
            deprecated_databases if deprecated_databases is not None else databases
        )
        object.__setattr__(self, "enabled", bool(enabled))
        object.__setattr__(self, "token_env", str(token_env).strip() or "NOTION_TOKEN")
        object.__setattr__(self, "data_sources", normalized_data_sources)
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "_deprecated_databases", normalized_deprecated)

    @property
    def databases(self) -> dict[str, str]:
        # Deprecated alias for backward compatibility.
        return self.data_sources


def _default_settings_path() -> Path:
    return Path.cwd() / "config" / "notion_settings.json"


def load_notion_settings(
    path: Path | None = None,
    *,
    allow_missing: bool = False,
) -> NotionSettings:
    settings_path = Path(path) if path is not None else _default_settings_path()
    if not settings_path.exists():
        if allow_missing:
            return NotionSettings(
                enabled=False,
                token_env="NOTION_TOKEN",
                data_sources={},
                path=settings_path,
            )
        raise NotionSettingsError(
            f"Missing Notion settings file: {settings_path}. "
            "Create config/notion_settings.json from config/notion_settings.example.json."
        )

    with settings_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    enabled = bool(payload.get("enabled", False))
    token_env = str(payload.get("token_env") or "NOTION_TOKEN").strip()
    data_sources = payload.get("data_sources") or {}
    deprecated_databases = payload.get("databases") or {}
    if not isinstance(data_sources, dict):
        raise NotionSettingsError("Invalid notion settings: data_sources must be an object.")
    if not isinstance(deprecated_databases, dict):
        raise NotionSettingsError("Invalid notion settings: databases must be an object.")

    return NotionSettings(
        enabled=enabled,
        token_env=token_env,
        data_sources=_normalize_mapping(data_sources),
        deprecated_databases=_normalize_mapping(deprecated_databases),
        path=settings_path,
    )


def get_notion_token(settings: NotionSettings, *, env: dict[str, str] | None = None) -> str:
    environ = env if env is not None else os.environ
    token = (environ.get(settings.token_env) or "").strip()
    if not token:
        raise NotionSettingsError(
            f"Missing Notion token in environment variable: {settings.token_env}."
        )
    return token


def get_notion_data_source_id(
    settings: NotionSettings,
    data_source_key: str,
    *,
    env: dict[str, str] | None = None,
    env_override: str | None = None,
) -> str:
    environ = env if env is not None else os.environ
    if env_override:
        override_value = (environ.get(env_override) or "").strip()
        if override_value:
            return override_value

    value = (settings.data_sources.get(data_source_key) or "").strip()
    if value:
        return value

    legacy_value = (settings._deprecated_databases.get(data_source_key) or "").strip()
    if legacy_value:
        return legacy_value

    raise NotionSettingsError(
        f"Missing Notion data source id for key '{data_source_key}'."
    )


def get_notion_database_id(
    settings: NotionSettings,
    database_key: str,
    *,
    env: dict[str, str] | None = None,
    env_override: str | None = None,
) -> str:
    # Deprecated wrapper kept for backward compatibility.
    return get_notion_data_source_id(
        settings,
        database_key,
        env=env,
        env_override=env_override,
    )
