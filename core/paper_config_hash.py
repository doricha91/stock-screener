from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


PAPER_CONFIG_HASH_POLICY = "paper_config_hash.v1"

_VOLATILE_KEYS = {
    "generated_at",
    "created_at",
    "updated_at",
    "run_id",
    "report_id",
    "archive_path",
    "env",
    "env_value",
}

_VOLATILE_KEY_FRAGMENTS = (
    "absolute_path",
    "local_path",
    "report_path",
    "log_path",
    "temporary_path",
    "temp_path",
    "machine",
    "username",
    "user_name",
    "secret",
    "token",
    "password",
    "api_key",
    "env_",
)

_PATH_KEY_SUFFIXES = ("_path", "_dir", "_directory")


def normalize_paper_config_for_hash(config: dict[str, Any]) -> dict[str, Any]:
    """Return a deterministic semantic projection for paper config hashing."""
    if not isinstance(config, dict):
        raise TypeError("config must be a dict")
    normalized = _normalize_value(config)
    return normalized if isinstance(normalized, dict) else {}


def compute_paper_config_hash(config: dict[str, Any]) -> str:
    """Compute a stable PAPER19 config hash in sha256:<hex> format."""
    normalized = normalize_paper_config_for_hash(config)
    payload = json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def compute_paper_config_hash_from_file(path: str | Path) -> str | None:
    """Read a config snapshot and compute its hash, returning None on invalid input."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    return compute_paper_config_hash(payload)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key)
            if _should_exclude_key(normalized_key):
                continue
            result[normalized_key] = _normalize_value(item)
        return result
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, set):
        return [_normalize_value(item) for item in sorted(value, key=str)]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _should_exclude_key(key: str) -> bool:
    lowered = key.lower()
    if lowered in _VOLATILE_KEYS:
        return True
    if lowered.endswith(_PATH_KEY_SUFFIXES):
        return True
    return any(fragment in lowered for fragment in _VOLATILE_KEY_FRAGMENTS)
