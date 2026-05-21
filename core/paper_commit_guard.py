from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from core.paths import (
    paper_account_snapshot_path,
    paper_current_state_snapshot_path,
    paper_position_snapshot_path,
)


@dataclass(frozen=True)
class PaperCommitGuardPaths:
    account_snapshot: Path
    position_snapshot: Path
    current_state_snapshot: Path


def build_paper_commit_guard_paths(date_str: str) -> PaperCommitGuardPaths:
    return PaperCommitGuardPaths(
        account_snapshot=paper_account_snapshot_path(),
        position_snapshot=paper_position_snapshot_path(),
        current_state_snapshot=paper_current_state_snapshot_path(date_str),
    )


def _normalize_date(date_str: str) -> tuple[str, str]:
    clean = str(date_str).replace("-", "").strip()
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    normalized = f"{clean[:4]}-{clean[4:6]}-{clean[6:]}"
    return clean, normalized


def _csv_has_snapshot_date(path: Path, target_date: str) -> tuple[bool, str | None]:
    if not path.exists():
        return False, None
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            if "snapshot_date" not in fieldnames:
                return False, f"snapshot_date column missing in {path.name}"
            for row in reader:
                if (row.get("snapshot_date") or "").strip() == target_date:
                    return True, None
    except (OSError, csv.Error, UnicodeDecodeError) as exc:
        return False, f"failed to parse {path.name}: {exc}"
    return False, None


def check_same_date_commit_guard(
    date_str: str,
    *,
    paths: PaperCommitGuardPaths | None = None,
) -> dict:
    clean_date, normalized_date = _normalize_date(date_str)
    resolved_paths = paths or build_paper_commit_guard_paths(clean_date)

    account_exists, account_error = _csv_has_snapshot_date(resolved_paths.account_snapshot, normalized_date)
    if account_error:
        return {
            "allowed": False,
            "error": account_error,
            "normalized_date": normalized_date,
            "existing_sources": [],
            "paths": resolved_paths,
        }

    position_exists, position_error = _csv_has_snapshot_date(resolved_paths.position_snapshot, normalized_date)
    if position_error:
        return {
            "allowed": False,
            "error": position_error,
            "normalized_date": normalized_date,
            "existing_sources": [],
            "paths": resolved_paths,
        }

    current_state_exists = resolved_paths.current_state_snapshot.exists()

    existing_sources: list[str] = []
    if account_exists:
        existing_sources.append("paper_account_snapshot.csv")
    if position_exists:
        existing_sources.append("paper_position_snapshot.csv")
    if current_state_exists:
        existing_sources.append(resolved_paths.current_state_snapshot.name)

    return {
        "allowed": len(existing_sources) == 0,
        "error": None,
        "normalized_date": normalized_date,
        "existing_sources": existing_sources,
        "paths": resolved_paths,
    }
