"""Immutable quarterly constituent bundles and their fail-closed validator."""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from core import universe_manager
from core.paths import quarterly_universe_artifact_path, quarterly_universe_dir
from core.stage_a_asof_contract import sha256_payload


SCHEMA = "paper_quarterly_universe_bundle.v1"
SLICE_NAMES = ("sp500", "nasdaq100", "sp500_ex_ndx100")
PROFILE_TO_SLICE = {
    "nasdaq100": "nasdaq100",
    "sp500_ex_ndx100": "sp500_ex_ndx100",
}
SOURCE_NAMES = ("sp500", "nasdaq100")
ARTIFACT_NAME = "universe_membership.json"
_SYMBOL_PATTERN = re.compile(r"[A-Z0-9][A-Z0-9.^-]*")
_VERSION_PATTERN = re.compile(r"[0-9]{4}q[1-4]")
_SHA256_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")


class QuarterlyUniverseError(ValueError):
    def __init__(self, reason: str, detail: str):
        self.reason = reason
        super().__init__(detail)


def _require(condition: bool, reason: str, detail: str) -> None:
    if not condition:
        raise QuarterlyUniverseError(reason, detail)


def validate_version(version: Any) -> str:
    _require(isinstance(version, str) and bool(_VERSION_PATTERN.fullmatch(version)),
             "invalid_version", f"Invalid quarterly universe version: {version!r}")
    return version


def _date(value: Any, field: str) -> date:
    _require(isinstance(value, str), "artifact_invalid", f"{field} must be YYYY-MM-DD")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise QuarterlyUniverseError("artifact_invalid", f"{field} must be YYYY-MM-DD") from exc


def _datetime(value: Any, field: str) -> datetime:
    _require(isinstance(value, str), "artifact_invalid", f"{field} must be ISO-8601")
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise QuarterlyUniverseError("artifact_invalid", f"{field} must be ISO-8601") from exc
    _require(parsed.tzinfo is not None, "artifact_invalid", f"{field} must include a timezone")
    return parsed


def _quarter(value: date) -> str:
    return f"{value.year}q{((value.month - 1) // 3) + 1}"


def _normalize_symbol(value: Any) -> str:
    text = str(value).strip().upper().replace(".", "-")
    _require(bool(_SYMBOL_PATTERN.fullmatch(text)), "symbol_invalid", f"Invalid symbol: {value!r}")
    return text


def canonical_symbols(values: Iterable[str], *, reject_duplicates: bool = True) -> list[str]:
    _require(not isinstance(values, (str, bytes)), "symbol_invalid", "Symbols must be an iterable")
    normalized = [_normalize_symbol(value) for value in values]
    _require(bool(normalized), "symbol_invalid", "Universe slice must not be empty")
    if reject_duplicates:
        _require(len(normalized) == len(set(normalized)), "duplicate_symbol",
                 "Duplicate normalized symbols are forbidden")
    return sorted(set(normalized))


def symbol_hash(symbols: Iterable[str]) -> str:
    return sha256_payload(canonical_symbols(symbols))


def _canonical_sources(value: Any) -> dict[str, dict[str, Any]]:
    _require(isinstance(value, Mapping) and set(value) == set(SOURCE_NAMES),
             "source_metadata_missing", "Both source metadata records are required")
    result: dict[str, dict[str, Any]] = {}
    for name in SOURCE_NAMES:
        row = value[name]
        required = {"provider", "url", "capture_mode", "source_revision"}
        _require(isinstance(row, Mapping) and set(row) >= required,
                 "source_metadata_missing", f"Incomplete source metadata: {name}")
        _require(all(isinstance(row[key], str) and bool(row[key].strip())
                     for key in required),
                 "source_metadata_missing", f"Empty source metadata: {name}")
        _require(bool(_SHA256_PATTERN.fullmatch(row["source_revision"])),
                 "source_revision_invalid", f"Invalid source revision: {name}")
        try:
            encoded = json.dumps(dict(row), ensure_ascii=False, sort_keys=True, allow_nan=False)
            canonical = json.loads(encoded)
        except (TypeError, ValueError) as exc:
            raise QuarterlyUniverseError("source_metadata_invalid", str(exc)) from exc
        _require(isinstance(canonical, dict), "source_metadata_invalid", "Source metadata must be an object")
        result[name] = canonical
    return result


def _artifact_payload_without_hash(bundle: Mapping[str, Any]) -> dict[str, Any]:
    return {key: bundle[key] for key in (
        "schema_version", "version", "observed_at", "effective_as_of", "capture_id",
        "sources", "universes",
    )}


def _capture_id(sources: Mapping[str, Mapping[str, Any]]) -> str:
    revisions = {name: sources[name]["source_revision"] for name in sorted(SOURCE_NAMES)}
    return sha256_payload(revisions)


def _raw_source_revision(raw_bytes: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw_bytes).hexdigest()


def build_quarterly_universe_bundle(
    *,
    version: str,
    observed_at: str,
    effective_as_of: str,
    sp500_symbols: Iterable[str],
    nasdaq100_symbols: Iterable[str],
    sources: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Build one canonical bundle from source sets captured in one operation."""
    version = validate_version(version)
    observed = _datetime(observed_at, "observed_at")
    effective = _date(effective_as_of, "effective_as_of")
    _require(_quarter(effective) == version, "version_mismatch",
             "effective_as_of quarter does not match the artifact version")
    sp500 = canonical_symbols(sp500_symbols)
    nasdaq100 = canonical_symbols(nasdaq100_symbols)
    excluded = sorted(set(sp500) - set(nasdaq100))
    _require(bool(excluded), "symbol_invalid", "S&P 500 ex NASDAQ 100 slice must not be empty")
    universes = {
        "sp500": {"symbols": sp500, "symbol_hash": sha256_payload(sp500)},
        "nasdaq100": {"symbols": nasdaq100, "symbol_hash": sha256_payload(nasdaq100)},
        "sp500_ex_ndx100": {"symbols": excluded, "symbol_hash": sha256_payload(excluded)},
    }
    canonical_sources = _canonical_sources(sources)
    bundle: dict[str, Any] = {
        "schema_version": SCHEMA,
        "version": version,
        "observed_at": observed.isoformat(),
        "effective_as_of": effective.isoformat(),
        "capture_id": _capture_id(canonical_sources),
        "sources": canonical_sources,
        "universes": universes,
    }
    bundle["artifact_hash"] = sha256_payload(_artifact_payload_without_hash(bundle))
    validate_quarterly_universe_bundle(bundle, expected_version=version)
    return bundle


def capture_quarterly_universe_bundle(
    *,
    version: str,
    effective_as_of: str,
    observed_at: str | None = None,
) -> dict[str, Any]:
    """Capture both live sources once; never label current membership as historical."""
    observed = _datetime(observed_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                         "observed_at")
    effective = _date(effective_as_of, "effective_as_of")
    _require(observed.date() == effective, "historical_backdate_forbidden",
             "Current live constituent sources cannot be backdated")
    sp500_symbols, sp500_raw = universe_manager.fetch_sp500_source_capture()
    nasdaq100_symbols, nasdaq100_raw = universe_manager.fetch_nasdaq100_source_capture()
    sources = {
        "sp500": {"provider": "wikipedia", "url": universe_manager.SP500_WIKI_URL,
                  "capture_mode": "current_live_membership",
                  "source_revision": _raw_source_revision(sp500_raw)},
        "nasdaq100": {"provider": "wikipedia", "url": universe_manager.NASDAQ100_WIKI_URL,
                      "capture_mode": "current_live_membership",
                      "source_revision": _raw_source_revision(nasdaq100_raw)},
    }
    return build_quarterly_universe_bundle(
        version=version,
        observed_at=observed.isoformat(),
        effective_as_of=effective.isoformat(),
        sp500_symbols=sp500_symbols,
        nasdaq100_symbols=nasdaq100_symbols,
        sources=sources,
    )


def validate_quarterly_universe_bundle(
    value: Any,
    *,
    expected_version: str | None = None,
) -> dict[str, Any]:
    _require(isinstance(value, Mapping), "artifact_invalid", "Quarterly universe artifact must be an object")
    expected_keys = {"schema_version", "version", "observed_at", "effective_as_of",
                     "capture_id", "sources", "universes", "artifact_hash"}
    _require(set(value) == expected_keys, "artifact_invalid", "Unexpected quarterly artifact fields")
    _require(value["schema_version"] == SCHEMA, "wrong_schema", "Unsupported quarterly artifact schema")
    version = validate_version(value["version"])
    if expected_version is not None:
        _require(version == validate_version(expected_version), "version_mismatch",
                 "Quarterly artifact version differs from the requested version")
    observed = _datetime(value["observed_at"], "observed_at")
    effective = _date(value["effective_as_of"], "effective_as_of")
    _require(_quarter(effective) == version, "version_mismatch",
             "effective_as_of quarter does not match the artifact version")
    sources = _canonical_sources(value["sources"])
    _require(sources == value["sources"], "source_metadata_invalid", "Source metadata is noncanonical")
    _require(isinstance(value["capture_id"], str)
             and bool(_SHA256_PATTERN.fullmatch(value["capture_id"])),
             "capture_id_invalid", "Invalid quarterly capture identity")
    _require(value["capture_id"] == _capture_id(sources),
             "capture_id_mismatch", "Quarterly capture identity mismatch")
    universes = value["universes"]
    _require(isinstance(universes, Mapping) and set(universes) == set(SLICE_NAMES),
             "slice_mismatch", "Required universe slices are missing or unknown")
    normalized: dict[str, list[str]] = {}
    for name in SLICE_NAMES:
        row = universes[name]
        _require(isinstance(row, Mapping) and set(row) == {"symbols", "symbol_hash"},
                 "slice_mismatch", f"Malformed universe slice: {name}")
        symbols = row["symbols"]
        _require(isinstance(symbols, list), "slice_mismatch", f"Symbols must be a list: {name}")
        canonical = canonical_symbols(symbols)
        _require(symbols == canonical, "noncanonical_symbols", f"Unsorted/noncanonical symbols: {name}")
        _require(row["symbol_hash"] == sha256_payload(canonical), "slice_hash_mismatch",
                 f"Universe slice hash mismatch: {name}")
        normalized[name] = canonical
    expected_excluded = sorted(set(normalized["sp500"]) - set(normalized["nasdaq100"]))
    _require(normalized["sp500_ex_ndx100"] == expected_excluded, "set_difference_mismatch",
             "S&P 500 ex NASDAQ 100 is not the exact set difference")
    _require(not set(normalized["nasdaq100"]) & set(normalized["sp500_ex_ndx100"]),
             "intersection_not_empty", "NASDAQ 100 and exclusion slice must be disjoint")
    expected_hash = sha256_payload(_artifact_payload_without_hash(value))
    _require(value["artifact_hash"] == expected_hash, "artifact_hash_mismatch",
             "Quarterly artifact semantic hash mismatch")
    return dict(value)


def _assert_safe_path(path: Path, *, directory: bool = False) -> bool:
    _require(".." not in path.parts, "unsafe_artifact", "Parent traversal in quarterly artifact path")
    absolute = path.absolute()
    target_exists = False
    for part in (absolute, *absolute.parents):
        try:
            info = part.lstat()
        except (FileNotFoundError, NotADirectoryError):
            continue
        if part == absolute:
            target_exists = True
        _require(not stat.S_ISLNK(info.st_mode),
                 "unsafe_artifact", f"Linked quarterly artifact path: {part}")
        _require(not (getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
                 "unsafe_artifact", f"Reparse quarterly artifact path: {part}")
        expected_type = stat.S_ISDIR if part != absolute or directory else stat.S_ISREG
        _require(expected_type(info.st_mode), "unsafe_artifact", f"Wrong quarterly artifact path type: {part}")
    return target_exists


def _json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def publish_quarterly_universe_bundle(
    bundle: Mapping[str, Any],
    *,
    outputs_root: Path | None = None,
) -> Path:
    """Publish once with exclusive version claim and artifact-ready-last rename."""
    validated = validate_quarterly_universe_bundle(bundle)
    target = quarterly_universe_artifact_path(validated["version"], outputs_root=outputs_root)
    root = quarterly_universe_dir(outputs_root=outputs_root)
    package = target.parent
    temporary = package / (ARTIFACT_NAME + ".tmp")
    _require(target.absolute().is_relative_to(root.absolute()), "unsafe_artifact",
             "Quarterly artifact escaped its namespace")
    _assert_safe_path(root, directory=True)
    _assert_safe_path(package, directory=True)
    _assert_safe_path(target)
    _assert_safe_path(temporary)
    _require(not package.exists(), "overwrite_forbidden", "Quarterly version is already claimed")
    root.mkdir(parents=True, exist_ok=True)
    _assert_safe_path(root, directory=True)
    try:
        package.mkdir()
    except FileExistsError as exc:
        raise QuarterlyUniverseError("overwrite_forbidden", "Quarterly version is already claimed") from exc
    try:
        with temporary.open("xb") as handle:
            handle.write(_json_bytes(validated))
            handle.flush()
            os.fsync(handle.fileno())
        _require(not target.exists(), "overwrite_forbidden", "Quarterly artifact already exists")
        temporary.rename(target)
    except Exception:
        # Preserve the claimed directory/partial evidence. A retry must not repair it.
        raise
    return target


def load_quarterly_universe_bundle(
    version: str,
    *,
    outputs_root: Path | None = None,
) -> dict[str, Any]:
    target = quarterly_universe_artifact_path(validate_version(version), outputs_root=outputs_root)
    package = target.parent
    _require(_assert_safe_path(package, directory=True), "artifact_missing", "Quarterly version is missing")
    _require({item.name for item in package.iterdir()} == {ARTIFACT_NAME}
             and _assert_safe_path(target) and target.is_file() and not target.is_symlink(),
             "partial_publication", "Quarterly version is partial or contains unknown files")
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuarterlyUniverseError("artifact_invalid", str(exc)) from exc
    return validate_quarterly_universe_bundle(payload, expected_version=version)
