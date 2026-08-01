from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

from core.paper_account_profile import validate_account_id


class PaperSnapshotIdentityError(ValueError):
    """Raised when a snapshot cannot be proven to belong to one account."""


def assert_snapshot_path_in_account_root(
    path: Path,
    *,
    account_root: Path,
    expected_account_id: str,
) -> None:
    expected = validate_account_id(expected_account_id)
    resolved_path = Path(path).resolve(strict=False)
    resolved_root = Path(account_root).resolve(strict=False)
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise PaperSnapshotIdentityError(
            "Snapshot path is outside the expected account root: "
            f"expected_account_id={expected} path={resolved_path} "
            f"expected_root={resolved_root} reason=path_mismatch"
        ) from exc


def validate_snapshot_account_identity(
    rows: Iterable[Mapping[str, Any]],
    *,
    fieldnames: Iterable[str | None] | None,
    allowed_fieldnames: Iterable[str],
    expected_account_id: str,
    source_path: Path,
    account_root: Path,
    allow_legacy_backfill: bool = False,
) -> tuple[list[dict[str, Any]], bool]:
    """Validate uniform account identity and optionally migrate a legacy schema."""

    expected = validate_account_id(expected_account_id)
    assert_snapshot_path_in_account_root(
        source_path,
        account_root=account_root,
        expected_account_id=expected,
    )
    if fieldnames is None:
        raise PaperSnapshotIdentityError(
            "Unsafe snapshot CSV header: "
            f"expected_account_id={expected} path={source_path} reason=missing_header"
        )
    normalized_fields = [str(name).replace("\ufeff", "").strip() for name in fieldnames]
    if any(not name for name in normalized_fields):
        raise PaperSnapshotIdentityError(
            "Unsafe snapshot CSV header: "
            f"expected_account_id={expected} path={source_path} reason=blank_header"
        )
    if len(normalized_fields) != len(set(normalized_fields)):
        raise PaperSnapshotIdentityError(
            "Unsafe snapshot CSV header: "
            f"expected_account_id={expected} path={source_path} reason=duplicate_header"
        )

    allowed_columns = {
        str(name).replace("\ufeff", "").strip()
        for name in allowed_fieldnames
    }
    actual_columns = set(normalized_fields)
    unknown_columns = sorted(actual_columns - allowed_columns)
    if unknown_columns:
        raise PaperSnapshotIdentityError(
            "Snapshot CSV contains unknown columns: "
            f"expected_account_id={expected} path={source_path} "
            f"unknown_columns={unknown_columns} reason=unknown_columns"
        )

    missing_columns = sorted(allowed_columns - actual_columns)
    legacy_account_id_only = (
        missing_columns == ["account_id"] and allow_legacy_backfill
    )
    if missing_columns and not legacy_account_id_only:
        raise PaperSnapshotIdentityError(
            "Snapshot CSV is missing required columns: "
            f"expected_account_id={expected} path={source_path} "
            f"missing_columns={missing_columns} reason=missing_columns"
        )

    copied_rows: list[dict[str, Any]] = []
    for row in rows:
        if None in row:
            raise PaperSnapshotIdentityError(
                "Unsafe snapshot CSV row: "
                f"expected_account_id={expected} path={source_path} reason=extra_columns"
            )
        copied_rows.append(
            {
                str(key).replace("\ufeff", "").strip(): value
                for key, value in row.items()
            }
        )

    if legacy_account_id_only:
        for row in copied_rows:
            row["account_id"] = expected
        return copied_rows, True

    if not copied_rows:
        return copied_rows, False

    actual_ids = [str(row.get("account_id") or "").strip() for row in copied_rows]
    if any(not actual for actual in actual_ids):
        raise PaperSnapshotIdentityError(
            "Snapshot account_id is blank: "
            f"expected_account_id={expected} actual_account_ids={actual_ids} "
            f"path={source_path} reason=blank_account_id"
        )
    unique_ids = sorted(set(actual_ids))
    if unique_ids != [expected]:
        reason = "mixed_account_ids" if len(unique_ids) > 1 else "account_id_mismatch"
        raise PaperSnapshotIdentityError(
            "Snapshot account identity mismatch: "
            f"expected_account_id={expected} actual_account_ids={unique_ids} "
            f"path={source_path} reason={reason}"
        )
    return copied_rows, False
