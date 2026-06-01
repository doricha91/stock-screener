from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.notion_manual_review_importer import FAIL, PASS, WARNING
from core.notion_account_keys import (
    build_legacy_manual_review_canonical_key,
    build_manual_review_canonical_key,
    normalize_notion_account_id,
)
from core.paper_account_guard import assert_non_default_writer_target
from core.paper_account_paths import PaperAccountPaths
from core.paper_manual_review_log_append import (
    append_paper_manual_review_log,
    load_existing_paper_manual_review_log_rows,
    write_paper_manual_review_log,
)
from core.paper_manual_review_log_template import (
    PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS,
    load_csv_rows,
)
from core.paths import dev_backups_dir, paper_reports_dir, paper_reviews_dir


class ManualReviewAppendCommitError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManualReviewAppendCommitResult:
    account_id: str
    review_date: str
    preview_json_path: str
    commit_json_path: str
    commit_markdown_path: str
    appended_count: int
    skipped_count: int
    failed_count: int
    backups: dict[str, str | None]


def commit_manual_review_preview(
    *,
    review_date: str,
    preview_json_path: Path,
    allow_warnings: bool = False,
    review_log_path: Path | None = None,
    template_path: Path | None = None,
    reports_dir: Path | None = None,
    account_paths: PaperAccountPaths | None = None,
) -> ManualReviewAppendCommitResult:
    payload = _load_preview_payload(preview_json_path)
    resolved_account_id = _resolve_preview_account_id(payload, account_paths=account_paths)
    _validate_preview_payload(payload, review_date=review_date, allow_warnings=allow_warnings)

    writer_paths = _resolve_review_writer_paths(account_paths=account_paths)
    target_log_path = review_log_path or writer_paths["review_log_path"]
    template_csv_path = template_path or writer_paths["template_path"]
    output_reports_dir = reports_dir or writer_paths["reports_dir"]

    allowed_root = account_paths.root if account_paths is not None and account_paths.account_id != "paper_default" else None
    existing_rows = load_existing_paper_manual_review_log_rows(target_log_path, allowed_root=allowed_root)
    template_by_key = _load_template_index(template_csv_path, allowed_root=allowed_root)
    candidate_payloads = _select_committable_candidates(payload)
    _normalize_append_candidate_payloads(candidate_payloads, account_id=resolved_account_id)
    preview_rows = [_candidate_to_review_log_row(candidate, template_by_key) for candidate in candidate_payloads]

    final_rows, append_issues, summary = append_paper_manual_review_log(preview_rows, existing_rows)
    duplicate_blockers = [issue for issue in append_issues if issue.get("issue_code") == "skipped_duplicate"]
    invalid_blockers = [issue for issue in append_issues if issue.get("severity") == "error"]
    if invalid_blockers:
        raise ManualReviewAppendCommitError(
            "Commit blocked because append validation returned errors: "
            + "; ".join(str(item.get("message") or "").strip() for item in invalid_blockers)
        )
    if duplicate_blockers:
        raise ManualReviewAppendCommitError(
            "Commit blocked because duplicate review key already exists in paper_manual_review_log.csv."
        )
    if summary["rows_appended"] != len(candidate_payloads):
        raise ManualReviewAppendCommitError(
            "Commit blocked because append row count did not match preview candidate count."
        )

    backups = _create_dev_backups(
        review_date=review_date,
        targets={"paper_manual_review_log": target_log_path},
        backup_dir=writer_paths["backup_dir"],
    )
    compact_date = review_date.replace("-", "")
    commit_json_path = output_reports_dir / f"manual_review_import_commit_{compact_date}.json"
    commit_markdown_path = output_reports_dir / f"manual_review_import_commit_{compact_date}.md"
    output_reports_dir.mkdir(parents=True, exist_ok=True)

    try:
        write_paper_manual_review_log(final_rows, target_log_path, allowed_root=allowed_root)
        if _count_data_rows(target_log_path) != len(final_rows):
            raise ManualReviewAppendCommitError("Review log row count mismatch after append write.")
        _write_commit_sidecar(
            account_id=resolved_account_id,
            review_date=review_date,
            preview_json_path=preview_json_path,
            commit_json_path=commit_json_path,
            commit_markdown_path=commit_markdown_path,
            allow_warnings=allow_warnings,
            candidate_payloads=candidate_payloads,
            append_issues=append_issues,
            summary=summary,
            backups=backups,
        )
    except Exception as exc:
        _restore_from_backups(targets={"paper_manual_review_log": target_log_path}, backup_paths=backups)
        if commit_json_path.exists():
            commit_json_path.unlink()
        if commit_markdown_path.exists():
            commit_markdown_path.unlink()
        if isinstance(exc, ManualReviewAppendCommitError):
            raise
        raise ManualReviewAppendCommitError(f"Manual review commit failed and was rolled back: {exc}") from exc

    return ManualReviewAppendCommitResult(
        account_id=resolved_account_id,
        review_date=review_date,
        preview_json_path=str(preview_json_path),
        commit_json_path=str(commit_json_path),
        commit_markdown_path=str(commit_markdown_path),
        appended_count=summary["rows_appended"],
        skipped_count=summary["rows_skipped_pending"] + summary["rows_skipped_duplicate"] + summary["rows_skipped_invalid"],
        failed_count=int(payload.get("fail_count") or 0),
        backups={key: (None if path is None else str(path)) for key, path in backups.items()},
    )


def _load_preview_payload(preview_json_path: Path) -> dict[str, Any]:
    if not preview_json_path.exists():
        raise ManualReviewAppendCommitError(f"Preview JSON not found: {preview_json_path}")
    with preview_json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ManualReviewAppendCommitError("Preview JSON root must be an object.")
    return payload


def _validate_preview_payload(
    payload: dict[str, Any],
    *,
    review_date: str,
    allow_warnings: bool,
) -> None:
    preview_date = str(payload.get("review_date") or "").strip()
    if preview_date != review_date:
        raise ManualReviewAppendCommitError(
            f"Preview date mismatch: preview={preview_date or 'blank'} expected={review_date}."
        )
    fail_count = int(payload.get("fail_count") or 0)
    append_allowed = str(payload.get("append_allowed") or "").strip().lower()
    if fail_count > 0 or append_allowed == "false":
        raise ManualReviewAppendCommitError("Preview contains FAIL rows; append commit is blocked.")
    if append_allowed == "true_with_warnings" and not allow_warnings:
        raise ManualReviewAppendCommitError(
            "Preview contains WARNING rows; rerun commit with --allow-warnings to proceed."
        )
    if append_allowed not in {"true", "true_with_warnings"}:
        raise ManualReviewAppendCommitError(
            f"Unsupported append_allowed value: {append_allowed or 'blank'}."
        )


def _select_committable_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        candidate
        for candidate in payload.get("candidates", [])
        if str(candidate.get("validation_status") or "").strip() in {PASS, WARNING}
    ]
    if not candidates:
        raise ManualReviewAppendCommitError("Preview JSON contains no committable review candidates.")

    seen_keys: set[str] = set()
    for candidate in candidates:
        canonical_key = str(candidate.get("canonical_key") or "").strip()
        review_date = str(candidate.get("review_date") or "").strip()
        symbol = str(candidate.get("symbol") or "").strip()
        question_id = str(candidate.get("question_id") or "").strip()
        manual_answer = str(candidate.get("manual_answer") or "").strip()
        review_status = str(candidate.get("review_status") or "").strip()
        if not canonical_key:
            raise ManualReviewAppendCommitError("Preview candidate is missing canonical_key.")
        if canonical_key in seen_keys:
            raise ManualReviewAppendCommitError(f"Preview contains duplicate canonical_key: {canonical_key}.")
        seen_keys.add(canonical_key)
        if not review_date or not symbol or not question_id:
            raise ManualReviewAppendCommitError(
                "Preview candidate is missing review_date, symbol, or question_id."
            )
        if not manual_answer or not review_status:
            raise ManualReviewAppendCommitError(
                "Preview candidate is missing manual_answer or review_status."
            )
    return candidates


def _resolve_preview_account_id(
    payload: dict[str, Any],
    *,
    account_paths: PaperAccountPaths | None = None,
) -> str:
    root_account_id = payload.get("account_id")
    if root_account_id is not None and str(root_account_id).strip():
        resolved_account_id = normalize_notion_account_id(str(root_account_id).strip())
    else:
        resolved_account_id = "paper_default"

    candidate_account_ids = {
        normalize_notion_account_id(str(candidate.get("account_id") or "").strip())
        for candidate in payload.get("candidates", [])
        if str(candidate.get("account_id") or "").strip()
    }
    if len(candidate_account_ids) > 1:
        raise ManualReviewAppendCommitError("Preview JSON contains mixed account_id values.")
    if candidate_account_ids:
        candidate_account_id = next(iter(candidate_account_ids))
        if candidate_account_id != resolved_account_id:
            raise ManualReviewAppendCommitError(
                "Preview JSON account_id does not match candidate account_id values."
            )
        resolved_account_id = candidate_account_id
    if account_paths is not None and account_paths.account_id != resolved_account_id:
        raise ManualReviewAppendCommitError("Provided account_paths.account_id does not match preview account_id.")
    if resolved_account_id != "paper_default" and account_paths is None:
        raise ManualReviewAppendCommitError(
            "Non-default manual review append requires account-aware writer paths."
        )
    return resolved_account_id


def _normalize_append_candidate_payloads(
    candidate_payloads: list[dict[str, Any]],
    *,
    account_id: str,
) -> None:
    for candidate in candidate_payloads:
        candidate["account_id"] = account_id
        raw_canonical_key = str(candidate.get("canonical_key") or "").strip()
        if not raw_canonical_key:
            raise ManualReviewAppendCommitError("Preview candidate is missing canonical_key.")
        normalized = _normalize_review_canonical_key(
            account_id=account_id,
            canonical_key=raw_canonical_key,
        )
        candidate["canonical_key"] = normalized["canonical_key"]
        candidate["legacy_canonical_key"] = normalized["legacy_canonical_key"]
        candidate["legacy_key_compatible"] = normalized["legacy_key_compatible"]


def _normalize_review_canonical_key(
    *,
    account_id: str,
    canonical_key: str,
) -> dict[str, Any]:
    parts = canonical_key.split(":")
    if len(parts) == 5 and parts[0] == "manual_review":
        key_account_id = normalize_notion_account_id(parts[1])
        if key_account_id != account_id:
            raise ManualReviewAppendCommitError(
                f"Preview canonical_key account_id mismatch: {canonical_key} vs {account_id}."
            )
        return {
            "canonical_key": canonical_key,
            "legacy_canonical_key": build_legacy_manual_review_canonical_key(
                parts[2],
                parts[3],
                parts[4],
            ) if account_id == "paper_default" else None,
            "legacy_key_compatible": account_id == "paper_default",
        }
    if len(parts) == 4 and parts[0] == "manual_review":
        if account_id != "paper_default":
            raise ManualReviewAppendCommitError(
                "Legacy canonical_key is not allowed for non-default manual review append."
            )
        normalized_key = build_manual_review_canonical_key(
            account_id,
            parts[1],
            parts[2],
            parts[3],
        )
        return {
            "canonical_key": normalized_key,
            "legacy_canonical_key": canonical_key,
            "legacy_key_compatible": True,
        }
    raise ManualReviewAppendCommitError(f"Unsupported manual review canonical_key format: {canonical_key}.")


def _load_template_index(
    template_path: Path,
    *,
    allowed_root: Path | None = None,
) -> dict[tuple[str, str, str], dict[str, str]]:
    if not template_path.exists():
        return {}
    rows = load_csv_rows(
        template_path,
        required_columns=PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS,
        label="paper manual review template",
        allowed_root=allowed_root,
    )
    return {
        (
            str(row.get("review_date") or "").strip(),
            str(row.get("symbol") or "").strip().upper(),
            str(row.get("question_id") or "").strip(),
        ): {column: str(row.get(column, "")) for column in PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS}
        for row in rows
    }


def _candidate_to_review_log_row(
    candidate: dict[str, Any],
    template_by_key: dict[tuple[str, str, str], dict[str, str]],
) -> dict[str, str]:
    review_date = str(candidate.get("review_date") or "").strip()
    symbol = str(candidate.get("symbol") or "").strip().upper()
    question_id = str(candidate.get("question_id") or "").strip()
    key = (review_date, symbol, question_id)
    row = dict(template_by_key.get(key, {}))
    if not row:
        row = {column: "" for column in PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS}

    row.update(
        {
            "review_date": review_date,
            "symbol": symbol,
            "question_id": question_id,
            "question_text": str(candidate.get("question_text") or "").strip(),
            "is_actionable": "false",
            "manual_answer": str(candidate.get("manual_answer") or "").strip(),
            "review_status": str(candidate.get("review_status") or "").strip(),
            "follow_up_needed": str(candidate.get("follow_up_needed") or "false").strip() or "false",
            "review_tag": str(candidate.get("review_tag") or "").strip(),
            "reviewer_note": str(candidate.get("reviewer_note") or "").strip(),
            "source_worksheet_path": str(
                candidate.get("source_template_key")
                or row.get("source_worksheet_path")
                or ""
            ).strip(),
            "created_at": str(candidate.get("created_at") or row.get("created_at") or "").strip(),
        }
    )
    return {column: str(row.get(column, "")) for column in PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS}


def _create_dev_backups(
    *,
    review_date: str,
    targets: dict[str, Path],
    backup_dir: Path,
) -> dict[str, Path | None]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    compact_date = review_date.replace("-", "")
    backups: dict[str, Path | None] = {}
    for label, source_path in targets.items():
        if not source_path.exists():
            backups[label] = None
            continue
        backup_path = backup_dir / f"{source_path.stem}_before_manual_review_commit_{compact_date}_{timestamp}{source_path.suffix}"
        shutil.copy2(source_path, backup_path)
        backups[label] = backup_path
    return backups


def _restore_from_backups(
    *,
    targets: dict[str, Path],
    backup_paths: dict[str, Path | None],
) -> None:
    for label, target_path in targets.items():
        backup_path = backup_paths.get(label)
        if backup_path is None:
            if target_path.exists():
                target_path.unlink()
            continue
        shutil.copy2(backup_path, target_path)


def _count_data_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return sum(1 for _ in handle) - 1


def _write_commit_sidecar(
    *,
    account_id: str,
    review_date: str,
    preview_json_path: Path,
    commit_json_path: Path,
    commit_markdown_path: Path,
    allow_warnings: bool,
    candidate_payloads: list[dict[str, Any]],
    append_issues: list[dict[str, str]],
    summary: dict[str, Any],
    backups: dict[str, Path | None],
) -> None:
    rows_payload = []
    for candidate in candidate_payloads:
        warnings = [
            issue
            for issue in candidate.get("validation_issues", [])
            if str(issue.get("severity") or "").strip().upper() == WARNING
        ]
        rows_payload.append(
            {
                "account_id": candidate.get("account_id"),
                "canonical_key": candidate.get("canonical_key"),
                "legacy_canonical_key": candidate.get("legacy_canonical_key"),
                "legacy_key_compatible": bool(candidate.get("legacy_key_compatible")),
                "page_id": candidate.get("page_id"),
                "review_date": candidate.get("review_date"),
                "symbol": candidate.get("symbol"),
                "question_id": candidate.get("question_id"),
                "validation_status": candidate.get("validation_status"),
                "validation_warnings": warnings,
                "append_status": "APPENDED",
            }
        )

    payload = {
        "account_id": account_id,
        "review_date": review_date,
        "preview_json_path": str(preview_json_path),
        "candidate_count": len(candidate_payloads),
        "appended_count": summary.get("rows_appended", 0),
        "skipped_count": summary.get("rows_skipped_pending", 0)
        + summary.get("rows_skipped_duplicate", 0)
        + summary.get("rows_skipped_invalid", 0),
        "failed_count": 0,
        "append_allowed": "true_with_warnings" if allow_warnings and any(row["validation_warnings"] for row in rows_payload) else "true",
        "allow_warnings": allow_warnings,
        "backups": {key: (None if path is None else str(path)) for key, path in backups.items()},
        "append_issues": append_issues,
        "rows": rows_payload,
    }
    commit_json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# Manual Review Commit [{review_date}]",
        "",
        f"- Preview JSON: {preview_json_path}",
        f"- Candidate Count: {payload['candidate_count']}",
        f"- Appended Count: {payload['appended_count']}",
        f"- Skipped Count: {payload['skipped_count']}",
        f"- Allow Warnings: {payload['allow_warnings']}",
        "",
        "## Rows",
    ]
    for row in rows_payload:
        lines.extend(
            [
                f"- {row['symbol']} {row['question_id']}",
                f"  - account_id: {row['account_id']}",
                f"  - canonical_key: {row['canonical_key']}",
                f"  - legacy_canonical_key: {row['legacy_canonical_key'] or '-'}",
                f"  - page_id: {row['page_id']}",
                f"  - validation_status: {row['validation_status']}",
                f"  - append_status: {row['append_status']}",
            ]
        )
        if row["validation_warnings"]:
            lines.append("  - validation_warnings:")
            for issue in row["validation_warnings"]:
                lines.append(f"    - {issue.get('message')}")
    commit_markdown_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _resolve_review_writer_paths(
    *,
    account_paths: PaperAccountPaths | None,
) -> dict[str, Path]:
    if account_paths is None or account_paths.account_id == "paper_default":
        reviews_dir = paper_reviews_dir()
        return {
            "review_log_path": reviews_dir / "paper_manual_review_log.csv",
            "template_path": reviews_dir / "paper_manual_review_log_template.csv",
            "reports_dir": paper_reports_dir(),
            "backup_dir": dev_backups_dir(),
        }

    targets = {
        "review_log_path": account_paths.reviews_dir / "paper_manual_review_log.csv",
        "template_path": account_paths.reviews_dir / "paper_manual_review_log_template.csv",
        "reports_dir": account_paths.reports_dir,
        "backup_dir": account_paths.root / "archive" / "dev_backups",
    }
    for path in targets.values():
        assert_non_default_writer_target(
            path,
            account_id=account_paths.account_id,
            account_root=account_paths.root,
        )
    return targets
