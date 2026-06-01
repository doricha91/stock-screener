from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.notion_client import (
    NotionAPIError,
    NotionClient,
    notion_rich_text,
    notion_select,
)
from core.notion_account_keys import (
    build_legacy_manual_execution_canonical_key,
    build_manual_execution_canonical_key,
    normalize_notion_account_id,
)
from core.notion_mapping import get_mapping_section, resolve_notion_property_name


class ManualExecutionStatusSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class ManualExecutionStatusRowResult:
    account_id: str
    page_id: str | None
    canonical_key: str | None
    legacy_canonical_key: str | None
    legacy_key_compatible: bool
    committed_trade_id: str | None
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
            "committed_trade_id": self.committed_trade_id,
            "status": self.status,
            "message": self.message,
            "updated_properties": self.updated_properties,
        }


@dataclass(frozen=True)
class ManualExecutionStatusSyncResult:
    account_id: str
    execution_date: str
    commit_report_path: str
    dry_run: bool
    overall_status: str
    candidate_count: int
    updated_count: int
    skipped_count: int
    failed_count: int
    data_source_check: str
    rows: list[ManualExecutionStatusRowResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "execution_date": self.execution_date,
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


def sync_manual_execution_status(
    *,
    client: NotionClient | None,
    mapping_root: dict[str, dict[str, str]],
    execution_date: str,
    commit_report_path: Path,
    dry_run: bool,
    account_id: str | None = None,
    data_source_check: str = "not_checked",
    now: datetime | None = None,
) -> ManualExecutionStatusSyncResult:
    payload = _load_commit_report(commit_report_path)
    resolved_account_id = normalize_notion_account_id(account_id)
    report_date = str(payload.get("execution_date") or "").strip()
    if report_date != execution_date:
        raise ManualExecutionStatusSyncError(
            f"Commit report date mismatch: report={report_date or 'blank'} expected={execution_date}."
        )

    mapping = get_mapping_section(mapping_root, "manual_executions")
    committed_rows = payload.get("committed_rows", [])
    if not isinstance(committed_rows, list):
        raise ManualExecutionStatusSyncError("Commit report committed_rows must be a list.")

    sync_timestamp = (now or datetime.now()).isoformat(timespec="seconds")
    row_results: list[ManualExecutionStatusRowResult] = []

    for row in committed_rows:
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
    overall_status = _overall_status(row_results)

    return ManualExecutionStatusSyncResult(
        account_id=resolved_account_id,
        execution_date=execution_date,
        commit_report_path=str(commit_report_path),
        dry_run=dry_run,
        overall_status=overall_status,
        candidate_count=len(committed_rows),
        updated_count=updated_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        data_source_check=data_source_check,
        rows=row_results,
    )


def _load_commit_report(commit_report_path: Path) -> dict[str, Any]:
    if not commit_report_path.exists():
        raise ManualExecutionStatusSyncError(f"Commit report not found: {commit_report_path}")
    with commit_report_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ManualExecutionStatusSyncError("Commit report root must be an object.")
    return payload


def _sync_one_row(
    *,
    client: NotionClient | None,
    mapping: dict[str, str],
    row: dict[str, Any],
    dry_run: bool,
    account_id: str,
    sync_timestamp: str,
) -> ManualExecutionStatusRowResult:
    page_id = _clean_text(row.get("page_id"))
    raw_canonical_key = _clean_text(row.get("canonical_key"))
    committed_trade_id = _clean_text(row.get("committed_trade_id"))
    normalized = _normalize_execution_canonical_key(
        account_id=account_id,
        canonical_key=raw_canonical_key,
        execution_date=_clean_text(row.get("execution_date")) or _clean_text(row.get("date")),
        symbol=_clean_text(row.get("symbol")),
        side=_clean_text(row.get("side")),
    )
    canonical_key = normalized["canonical_key"]
    legacy_canonical_key = normalized["legacy_canonical_key"]
    legacy_key_compatible = normalized["legacy_key_compatible"]
    canonical_error = normalized["error"]

    missing: list[str] = []
    if not committed_trade_id:
        missing.append("committed_trade_id")
    if not page_id:
        missing.append("page_id")
    if not canonical_key:
        missing.append("canonical_key")

    property_keys = [
        "external_key",
        "account_id",
        "validation_status",
        "validation_message",
        "import_status",
        "imported_at",
        "synced_at",
        "status",
    ]
    updated_properties = [resolve_notion_property_name(mapping, key) for key in property_keys]

    if missing:
        return ManualExecutionStatusRowResult(
            account_id=account_id,
            page_id=page_id,
            canonical_key=canonical_key,
            legacy_canonical_key=legacy_canonical_key,
            legacy_key_compatible=legacy_key_compatible,
            committed_trade_id=committed_trade_id,
            status="SKIPPED",
            message=f"Missing required commit report field(s): {', '.join(missing)}.",
            updated_properties=updated_properties,
        )

    if canonical_error:
        return ManualExecutionStatusRowResult(
            account_id=account_id,
            page_id=page_id,
            canonical_key=canonical_key,
            legacy_canonical_key=legacy_canonical_key,
            legacy_key_compatible=legacy_key_compatible,
            committed_trade_id=committed_trade_id,
            status="FAILED",
            message=canonical_error,
            updated_properties=updated_properties,
        )

    properties = build_manual_execution_status_properties(
        mapping=mapping,
        account_id=account_id,
        canonical_key=canonical_key,
        validation_status=_clean_text(row.get("validation_status")) or "PASS",
        validation_issues=row.get("validation_issues", []),
        sync_timestamp=sync_timestamp,
    )

    if dry_run:
        return ManualExecutionStatusRowResult(
            account_id=account_id,
            page_id=page_id,
            canonical_key=canonical_key,
            legacy_canonical_key=legacy_canonical_key,
            legacy_key_compatible=legacy_key_compatible,
            committed_trade_id=committed_trade_id,
            status="DRY_RUN",
            message="Dry-run only. No Notion page update performed.",
            updated_properties=list(properties.keys()),
        )

    if client is None:
        raise ManualExecutionStatusSyncError("Notion client is required for non-dry-run status sync.")

    try:
        client.update_page(page_id, properties)
    except NotionAPIError as exc:
        return ManualExecutionStatusRowResult(
            account_id=account_id,
            page_id=page_id,
            canonical_key=canonical_key,
            legacy_canonical_key=legacy_canonical_key,
            legacy_key_compatible=legacy_key_compatible,
            committed_trade_id=committed_trade_id,
            status="FAILED",
            message=str(exc),
            updated_properties=list(properties.keys()),
        )

    return ManualExecutionStatusRowResult(
        account_id=account_id,
        page_id=page_id,
        canonical_key=canonical_key,
        legacy_canonical_key=legacy_canonical_key,
        legacy_key_compatible=legacy_key_compatible,
        committed_trade_id=committed_trade_id,
        status="UPDATED",
        message="Notion Manual Execution status synced.",
        updated_properties=list(properties.keys()),
    )


def build_manual_execution_status_properties(
    *,
    mapping: dict[str, str],
    account_id: str,
    canonical_key: str,
    validation_status: str,
    validation_issues: list[dict[str, Any]] | None,
    sync_timestamp: str,
) -> dict[str, Any]:
    validation_status_name = (validation_status or "PASS").strip().upper()
    validation_message = summarize_validation_issues(validation_issues or [])

    return {
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(canonical_key),
        resolve_notion_property_name(mapping, "account_id"): notion_select(account_id),
        resolve_notion_property_name(mapping, "validation_status"): notion_select(validation_status_name),
        resolve_notion_property_name(mapping, "validation_message"): notion_rich_text(validation_message),
        resolve_notion_property_name(mapping, "import_status"): notion_select("COMMITTED"),
        resolve_notion_property_name(mapping, "imported_at"): notion_rich_text(sync_timestamp),
        resolve_notion_property_name(mapping, "synced_at"): notion_rich_text(sync_timestamp),
        resolve_notion_property_name(mapping, "status"): notion_select("IMPORTED"),
    }


def _normalize_execution_canonical_key(
    *,
    account_id: str,
    canonical_key: str | None,
    execution_date: str | None,
    symbol: str | None,
    side: str | None,
) -> dict[str, Any]:
    legacy_canonical_key = canonical_key
    if not canonical_key:
        return {
            "canonical_key": None,
            "legacy_canonical_key": None,
            "legacy_key_compatible": False,
            "error": None,
        }

    parts = canonical_key.split(":")
    if len(parts) == 6 and parts[0] == "manual_execution":
        return {
            "canonical_key": canonical_key,
            "legacy_canonical_key": None,
            "legacy_key_compatible": False,
            "error": None,
        }
    if len(parts) == 5 and parts[0] == "manual_execution":
        if account_id != "paper_default":
            return {
                "canonical_key": canonical_key,
                "legacy_canonical_key": canonical_key,
                "legacy_key_compatible": False,
                "error": "Legacy canonical_key is not allowed for non-default account status sync.",
            }
        exec_date = execution_date or parts[1]
        exec_symbol = (symbol or parts[2] or "").upper()
        exec_side = (side or parts[3] or "").upper()
        try:
            sequence = int(parts[4])
        except ValueError:
            return {
                "canonical_key": canonical_key,
                "legacy_canonical_key": canonical_key,
                "legacy_key_compatible": True,
                "error": "Legacy manual execution canonical_key sequence is invalid.",
            }
        return {
            "canonical_key": build_manual_execution_canonical_key(
                account_id,
                exec_date,
                exec_symbol,
                exec_side,
                sequence,
            ),
            "legacy_canonical_key": build_legacy_manual_execution_canonical_key(
                exec_date,
                exec_symbol,
                exec_side,
                sequence,
            ),
            "legacy_key_compatible": True,
            "error": None,
        }
    return {
        "canonical_key": canonical_key,
        "legacy_canonical_key": legacy_canonical_key,
        "legacy_key_compatible": False,
        "error": None,
    }


def summarize_validation_issues(validation_issues: list[dict[str, Any]]) -> str:
    messages: list[str] = []
    for issue in validation_issues:
        code = _clean_text(issue.get("code"))
        message = _clean_text(issue.get("message"))
        if code and message:
            messages.append(f"{code}: {message}")
        elif message:
            messages.append(message)
        elif code:
            messages.append(code)
    return "OK" if not messages else "\n".join(messages)


def _overall_status(rows: list[ManualExecutionStatusRowResult]) -> str:
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
