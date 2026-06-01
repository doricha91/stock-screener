from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.notion_client import NotionAPIError, NotionClient, notion_rich_text, notion_select
from core.notion_account_keys import (
    build_legacy_manual_review_canonical_key,
    build_manual_review_canonical_key,
    normalize_notion_account_id,
)
from core.notion_mapping import get_mapping_section, resolve_notion_property_name


class ManualReviewStatusSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManualReviewStatusRowResult:
    account_id: str
    page_id: str | None
    canonical_key: str | None
    legacy_canonical_key: str | None
    legacy_key_compatible: bool
    review_date: str | None
    symbol: str | None
    question_id: str | None
    status: str
    message: str
    updated_properties: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "page_id": self.page_id,
            "canonical_key": self.canonical_key,
            "legacy_canonical_key": self.legacy_canonical_key,
            "legacy_key_compatible": self.legacy_key_compatible,
            "review_date": self.review_date,
            "symbol": self.symbol,
            "question_id": self.question_id,
            "status": self.status,
            "message": self.message,
            "updated_properties": self.updated_properties,
        }


@dataclass(frozen=True)
class ManualReviewStatusSyncResult:
    account_id: str
    review_date: str
    commit_report_path: str
    dry_run: bool
    overall_status: str
    candidate_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    data_source_check: str
    rows: list[ManualReviewStatusRowResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "review_date": self.review_date,
            "commit_report_path": self.commit_report_path,
            "dry_run": self.dry_run,
            "overall_status": self.overall_status,
            "candidate_count": self.candidate_count,
            "updated_count": self.updated_count,
            "skipped_count": self.skipped_count,
            "failed_count": self.failed_count,
            "data_source_check": self.data_source_check,
            "rows": [row.to_dict() for row in self.rows],
        }


def sync_manual_review_status(
    *,
    client: NotionClient | None,
    mapping_root: dict[str, dict[str, str]],
    review_date: str,
    commit_report_path: Path,
    dry_run: bool,
    account_id: str | None = None,
    data_source_check: str = "not_checked",
    now: datetime | None = None,
) -> ManualReviewStatusSyncResult:
    payload = _load_commit_report(commit_report_path)
    resolved_account_id = normalize_notion_account_id(account_id)
    report_date = str(payload.get("review_date") or "").strip()
    if report_date != review_date:
        raise ManualReviewStatusSyncError(
            f"Commit report date mismatch: report={report_date or 'blank'} expected={review_date}."
        )

    mapping = get_mapping_section(mapping_root, "manual_reviews")
    report_rows = payload.get("rows", [])
    if not isinstance(report_rows, list):
        raise ManualReviewStatusSyncError("Commit report rows must be a list.")

    sync_timestamp = (now or datetime.now()).isoformat(timespec="seconds")
    row_results: list[ManualReviewStatusRowResult] = []
    for row in report_rows:
        row_results.append(
            _sync_one_row(
                client=client,
                mapping=mapping,
                row=row,
                dry_run=dry_run,
                account_id=resolved_account_id,
                sync_timestamp=sync_timestamp,
            )
        )

    updated_count = sum(1 for row in row_results if row.status in {"DRY_RUN", "UPDATED"})
    skipped_count = sum(1 for row in row_results if row.status == "SKIPPED")
    failed_count = sum(1 for row in row_results if row.status == "FAILED")

    return ManualReviewStatusSyncResult(
        account_id=resolved_account_id,
        review_date=review_date,
        commit_report_path=str(commit_report_path),
        dry_run=dry_run,
        overall_status=_overall_status(row_results),
        candidate_count=len(report_rows),
        updated_count=updated_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        data_source_check=data_source_check,
        rows=row_results,
    )


def build_manual_review_status_properties(
    *,
    mapping: dict[str, str],
    account_id: str,
    canonical_key: str,
    validation_status: str,
    validation_warnings: list[dict[str, Any]] | None,
    sync_timestamp: str,
) -> dict[str, Any]:
    status_name = (validation_status or "PASS").strip().upper()
    validation_message = summarize_validation_warnings(validation_warnings or [])
    return {
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(canonical_key),
        resolve_notion_property_name(mapping, "account_id"): notion_select(account_id),
        resolve_notion_property_name(mapping, "validation_status"): notion_select(status_name),
        resolve_notion_property_name(mapping, "validation_message"): notion_rich_text(validation_message),
        resolve_notion_property_name(mapping, "import_status"): notion_select("COMMITTED"),
        resolve_notion_property_name(mapping, "imported_at"): notion_rich_text(sync_timestamp),
        resolve_notion_property_name(mapping, "synced_at"): notion_rich_text(sync_timestamp),
    }


def summarize_validation_warnings(validation_warnings: list[dict[str, Any]]) -> str:
    messages: list[str] = []
    for issue in validation_warnings:
        code = _clean_text(issue.get("code"))
        message = _clean_text(issue.get("message"))
        if code and message:
            messages.append(f"{code}: {message}")
        elif message:
            messages.append(message)
        elif code:
            messages.append(code)
    return "OK" if not messages else "\n".join(messages)


def _load_commit_report(commit_report_path: Path) -> dict[str, Any]:
    if not commit_report_path.exists():
        raise ManualReviewStatusSyncError(f"Commit report not found: {commit_report_path}")
    with commit_report_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ManualReviewStatusSyncError("Commit report root must be an object.")
    return payload


def _sync_one_row(
    *,
    client: NotionClient | None,
    mapping: dict[str, str],
    row: dict[str, Any],
    dry_run: bool,
    account_id: str,
    sync_timestamp: str,
) -> ManualReviewStatusRowResult:
    page_id = _clean_text(row.get("page_id"))
    raw_canonical_key = _clean_text(row.get("canonical_key"))
    review_date = _clean_text(row.get("review_date"))
    symbol = _clean_text(row.get("symbol"))
    question_id = _clean_text(row.get("question_id"))
    append_status = _clean_text(row.get("append_status"))
    normalized = _normalize_review_canonical_key(
        account_id=account_id,
        canonical_key=raw_canonical_key,
        review_date=review_date,
        symbol=symbol,
        question_id=question_id,
    )
    canonical_key = normalized["canonical_key"]
    legacy_canonical_key = normalized["legacy_canonical_key"]
    legacy_key_compatible = normalized["legacy_key_compatible"]
    canonical_error = normalized["error"]

    property_keys = [
        "external_key",
        "account_id",
        "validation_status",
        "validation_message",
        "import_status",
        "imported_at",
        "synced_at",
    ]
    updated_properties = [resolve_notion_property_name(mapping, key) for key in property_keys]

    if append_status not in {"APPENDED", "COMMITTED"}:
        return ManualReviewStatusRowResult(
            account_id=account_id,
            page_id=page_id,
            canonical_key=canonical_key,
            legacy_canonical_key=legacy_canonical_key,
            legacy_key_compatible=legacy_key_compatible,
            review_date=review_date,
            symbol=symbol,
            question_id=question_id,
            status="SKIPPED",
            message=f"Row append_status is not syncable: {append_status or 'blank'}.",
            updated_properties=updated_properties,
        )

    missing: list[str] = []
    if not page_id:
        missing.append("page_id")
    if not canonical_key:
        missing.append("canonical_key")
    if not review_date:
        missing.append("review_date")
    if not symbol:
        missing.append("symbol")
    if not question_id:
        missing.append("question_id")
    if missing:
        return ManualReviewStatusRowResult(
            account_id=account_id,
            page_id=page_id,
            canonical_key=canonical_key,
            legacy_canonical_key=legacy_canonical_key,
            legacy_key_compatible=legacy_key_compatible,
            review_date=review_date,
            symbol=symbol,
            question_id=question_id,
            status="SKIPPED",
            message=f"Missing required commit report field(s): {', '.join(missing)}.",
            updated_properties=updated_properties,
        )

    if canonical_error:
        return ManualReviewStatusRowResult(
            account_id=account_id,
            page_id=page_id,
            canonical_key=canonical_key,
            legacy_canonical_key=legacy_canonical_key,
            legacy_key_compatible=legacy_key_compatible,
            review_date=review_date,
            symbol=symbol,
            question_id=question_id,
            status="FAILED",
            message=canonical_error,
            updated_properties=updated_properties,
        )

    properties = build_manual_review_status_properties(
        mapping=mapping,
        account_id=account_id,
        canonical_key=canonical_key,
        validation_status=_clean_text(row.get("validation_status")) or "PASS",
        validation_warnings=row.get("validation_warnings", []),
        sync_timestamp=sync_timestamp,
    )

    if dry_run:
        return ManualReviewStatusRowResult(
            account_id=account_id,
            page_id=page_id,
            canonical_key=canonical_key,
            legacy_canonical_key=legacy_canonical_key,
            legacy_key_compatible=legacy_key_compatible,
            review_date=review_date,
            symbol=symbol,
            question_id=question_id,
            status="DRY_RUN",
            message="Dry-run only. No Notion page update performed.",
            updated_properties=list(properties.keys()),
        )

    if client is None:
        raise ManualReviewStatusSyncError("Notion client is required for non-dry-run status sync.")

    try:
        client.update_page(page_id, properties)
    except NotionAPIError as exc:
        return ManualReviewStatusRowResult(
            account_id=account_id,
            page_id=page_id,
            canonical_key=canonical_key,
            legacy_canonical_key=legacy_canonical_key,
            legacy_key_compatible=legacy_key_compatible,
            review_date=review_date,
            symbol=symbol,
            question_id=question_id,
            status="FAILED",
            message=str(exc),
            updated_properties=list(properties.keys()),
        )

    return ManualReviewStatusRowResult(
        account_id=account_id,
        page_id=page_id,
        canonical_key=canonical_key,
        legacy_canonical_key=legacy_canonical_key,
        legacy_key_compatible=legacy_key_compatible,
        review_date=review_date,
        symbol=symbol,
        question_id=question_id,
        status="UPDATED",
        message="Notion Manual Review status synced.",
        updated_properties=list(properties.keys()),
    )


def _overall_status(rows: list[ManualReviewStatusRowResult]) -> str:
    if not rows:
        return "SUCCESS"
    has_failed = any(row.status == "FAILED" for row in rows)
    has_skipped = any(row.status == "SKIPPED" for row in rows)
    has_updated = any(row.status in {"UPDATED", "DRY_RUN"} for row in rows)
    if has_failed and not has_updated:
        return "FAILED"
    if has_failed or has_skipped:
        return "PARTIAL_SUCCESS"
    return "SUCCESS"


def _clean_text(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_review_canonical_key(
    *,
    account_id: str,
    canonical_key: str | None,
    review_date: str | None,
    symbol: str | None,
    question_id: str | None,
) -> dict[str, Any]:
    if not canonical_key:
        return {
            "canonical_key": None,
            "legacy_canonical_key": None,
            "legacy_key_compatible": False,
            "error": None,
        }
    parts = canonical_key.split(":")
    if len(parts) == 5 and parts[0] == "manual_review":
        return {
            "canonical_key": canonical_key,
            "legacy_canonical_key": None,
            "legacy_key_compatible": False,
            "error": None,
        }
    if len(parts) == 4 and parts[0] == "manual_review":
        if account_id != "paper_default":
            return {
                "canonical_key": canonical_key,
                "legacy_canonical_key": canonical_key,
                "legacy_key_compatible": False,
                "error": "Legacy canonical_key is not allowed for non-default account status sync.",
            }
        resolved_review_date = review_date or parts[1]
        resolved_symbol = (symbol or parts[2] or "").upper()
        resolved_question_id = question_id or parts[3]
        return {
            "canonical_key": build_manual_review_canonical_key(
                account_id,
                resolved_review_date,
                resolved_symbol,
                resolved_question_id,
            ),
            "legacy_canonical_key": build_legacy_manual_review_canonical_key(
                resolved_review_date,
                resolved_symbol,
                resolved_question_id,
            ),
            "legacy_key_compatible": True,
            "error": None,
        }
    return {
        "canonical_key": canonical_key,
        "legacy_canonical_key": canonical_key,
        "legacy_key_compatible": False,
        "error": None,
    }
