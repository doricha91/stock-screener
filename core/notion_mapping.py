from __future__ import annotations

import json
from pathlib import Path


class NotionMappingError(RuntimeError):
    pass


def _default_mapping_path() -> Path:
    return Path.cwd() / "config" / "notion_property_mapping.json"


def _default_mapping_example_path() -> Path:
    return Path.cwd() / "config" / "notion_property_mapping.example.json"


def load_notion_property_mapping(
    path: Path | None = None,
    *,
    fallback_to_example: bool = True,
) -> dict[str, dict[str, str]]:
    mapping_path = Path(path) if path is not None else _default_mapping_path()
    if not mapping_path.exists():
        if fallback_to_example:
            mapping_path = _default_mapping_example_path()
        if not mapping_path.exists():
            raise NotionMappingError(
                "Missing notion property mapping file. "
                "Create config/notion_property_mapping.json or provide the example file."
            )

    with mapping_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise NotionMappingError("Invalid notion property mapping: root must be an object.")

    normalized: dict[str, dict[str, str]] = {}
    for section, values in payload.items():
        if not isinstance(values, dict):
            raise NotionMappingError(f"Invalid notion property mapping section: {section}")
        normalized[str(section)] = {str(key): str(value) for key, value in values.items()}
    return normalized


def get_mapping_section(mapping: dict[str, dict[str, str]], section: str) -> dict[str, str]:
    if section not in mapping:
        raise NotionMappingError(f"Missing notion mapping section: {section}")
    return mapping[section]


def resolve_notion_property_name(mapping: dict[str, str], field_key: str) -> str:
    if field_key not in mapping:
        raise NotionMappingError(f"Missing notion property mapping key: {field_key}")
    return mapping[field_key]
