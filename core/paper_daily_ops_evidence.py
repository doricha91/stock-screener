from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


EVIDENCE_SCHEMA_VERSION = "paper_notion_evidence.v1"

EVIDENCE_DAILY_PLAN_NOTION_EXPORT = "DAILY_PLAN_NOTION_EXPORT"
EVIDENCE_MANUAL_EXECUTION_TEMPLATE = "MANUAL_EXECUTION_TEMPLATE"
EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC = "MANUAL_EXECUTION_STATUS_SYNC"
EVIDENCE_MANUAL_REVIEW_TEMPLATE = "MANUAL_REVIEW_TEMPLATE"
EVIDENCE_MANUAL_REVIEW_STATUS_SYNC = "MANUAL_REVIEW_STATUS_SYNC"

STATUS_PASS = "PASS"
STATUS_WARNING = "WARNING"
STATUS_FAILED = "FAILED"
STATUS_UNKNOWN = "UNKNOWN"

DONE = "DONE"
BLOCKED = "BLOCKED"
WARNING = "WARNING"
UNKNOWN = "UNKNOWN"

EVIDENCE_FILE_STEMS = {
    EVIDENCE_DAILY_PLAN_NOTION_EXPORT: "daily_plan_notion_export",
    EVIDENCE_MANUAL_EXECUTION_TEMPLATE: "manual_execution_template_export",
    EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC: "manual_execution_status_sync",
    EVIDENCE_MANUAL_REVIEW_TEMPLATE: "manual_review_template_export",
    EVIDENCE_MANUAL_REVIEW_STATUS_SYNC: "manual_review_status_sync",
}


@dataclass(frozen=True)
class EvidenceEvaluation:
    path: Path
    checked: bool
    stage_status: str | None
    evidence_status: str | None
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


def notion_evidence_path(account_root: Path, evidence_type: str, trade_date: str) -> Path:
    stem = EVIDENCE_FILE_STEMS[evidence_type]
    compact_date = str(trade_date).replace("-", "")
    return Path(account_root) / "reports" / f"{stem}_{compact_date}.json"


def evaluate_notion_evidence(
    *,
    account_root: Path,
    legacy_root: Path,
    account_id: str,
    trade_date: str,
    data_date: str | None,
    evidence_type: str,
) -> EvidenceEvaluation:
    path = notion_evidence_path(account_root, evidence_type, trade_date)
    if not path.exists():
        legacy_path = notion_evidence_path(legacy_root, evidence_type, trade_date)
        if account_id != "paper_default" and legacy_path.exists():
            return EvidenceEvaluation(
                path=path,
                checked=True,
                stage_status=BLOCKED,
                evidence_status=None,
                blockers=(
                    f"Legacy paper_test evidence exists but cannot be used for non-default account {account_id}.",
                ),
            )
        return EvidenceEvaluation(path=path, checked=False, stage_status=None, evidence_status=None)

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception as exc:
        return EvidenceEvaluation(
            path=path,
            checked=True,
            stage_status=WARNING,
            evidence_status=None,
            warnings=(f"Evidence JSON could not be parsed: {exc}",),
        )

    if not isinstance(payload, dict):
        return EvidenceEvaluation(
            path=path,
            checked=True,
            stage_status=WARNING,
            evidence_status=None,
            warnings=("Evidence JSON root must be an object.",),
        )

    if evidence_type in {EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC, EVIDENCE_MANUAL_REVIEW_STATUS_SYNC}:
        legacy_evaluation = _evaluate_existing_sync_report(
            path=path,
            payload=payload,
            account_id=account_id,
            trade_date=trade_date,
            evidence_type=evidence_type,
        )
        if legacy_evaluation is not None:
            return legacy_evaluation

    blockers = _validation_blockers(
        payload,
        account_id=account_id,
        trade_date=trade_date,
        data_date=data_date,
        evidence_type=evidence_type,
    )
    status = str(payload.get("status") or "").strip().upper()
    failed_count = _safe_int(payload.get("failed_count"))
    warnings = tuple(str(item) for item in payload.get("warnings") or [] if str(item).strip())

    if blockers:
        return EvidenceEvaluation(
            path=path,
            checked=True,
            stage_status=BLOCKED,
            evidence_status=status or None,
            blockers=tuple(blockers),
            warnings=warnings,
        )
    if status == STATUS_FAILED or failed_count > 0:
        errors = [str(item) for item in payload.get("errors") or [] if str(item).strip()]
        reason = "Evidence status is FAILED or failed_count is greater than 0."
        return EvidenceEvaluation(
            path=path,
            checked=True,
            stage_status=BLOCKED,
            evidence_status=status,
            blockers=tuple([reason, *errors]),
            warnings=warnings,
        )
    if status == STATUS_WARNING:
        return EvidenceEvaluation(
            path=path,
            checked=True,
            stage_status=WARNING,
            evidence_status=status,
            warnings=warnings or ("Evidence status is WARNING.",),
        )
    if status == STATUS_PASS:
        return EvidenceEvaluation(
            path=path,
            checked=True,
            stage_status=DONE,
            evidence_status=status,
            warnings=warnings,
        )
    return EvidenceEvaluation(
        path=path,
        checked=True,
        stage_status=UNKNOWN,
        evidence_status=status or None,
        warnings=warnings or (f"Evidence status is UNKNOWN or unsupported: {status or '-'}",),
    )


def _evaluate_existing_sync_report(
    *,
    path: Path,
    payload: dict[str, Any],
    account_id: str,
    trade_date: str,
    evidence_type: str,
) -> EvidenceEvaluation | None:
    if evidence_type == EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC:
        date_key = "execution_date"
    elif evidence_type == EVIDENCE_MANUAL_REVIEW_STATUS_SYNC:
        date_key = "review_date"
    else:
        return None

    required_markers = {
        date_key,
        "overall_status",
        "candidate_count",
        "updated_count",
        "failed_count",
        "commit_report_path",
        "rows",
    }
    if not required_markers.issubset(payload):
        return None

    blockers: list[str] = []
    if str(payload.get("account_id") or "").strip() != account_id:
        blockers.append("Sync report account_id mismatch.")
    if str(payload.get(date_key) or "").strip() != trade_date:
        blockers.append(f"Sync report {date_key} mismatch.")
    if str(payload.get("overall_status") or "").strip().upper() != "SUCCESS":
        blockers.append("Sync report overall_status must be SUCCESS.")
    candidate_count = _safe_int(payload.get("candidate_count"))
    updated_count = _safe_int(payload.get("updated_count"))
    failed_count = _safe_int(payload.get("failed_count"))
    if candidate_count <= 0:
        blockers.append("Sync report candidate_count must be greater than 0.")
    if updated_count != candidate_count:
        blockers.append("Sync report updated_count must equal candidate_count.")
    if failed_count != 0:
        blockers.append("Sync report failed_count must be 0.")
    commit_report_path = str(payload.get("commit_report_path") or "").strip()
    if not commit_report_path:
        blockers.append("Sync report commit_report_path is required.")
    elif not Path(commit_report_path).exists():
        blockers.append("Sync report commit_report_path does not exist.")
    rows = payload.get("rows")
    if not isinstance(rows, list):
        blockers.append("Sync report rows must be a list.")
    else:
        bad_statuses = [
            str(row.get("status") or "").strip().upper()
            for row in rows
            if isinstance(row, dict) and str(row.get("status") or "").strip().upper() != "UPDATED"
        ]
        malformed_count = sum(1 for row in rows if not isinstance(row, dict))
        if bad_statuses or malformed_count:
            blockers.append("Sync report rows[].status must all be UPDATED.")

    if blockers:
        return EvidenceEvaluation(
            path=path,
            checked=True,
            stage_status=BLOCKED,
            evidence_status=str(payload.get("overall_status") or "").strip().upper() or None,
            blockers=tuple(blockers),
        )
    return EvidenceEvaluation(
        path=path,
        checked=True,
        stage_status=DONE,
        evidence_status="SUCCESS",
    )


def _validation_blockers(
    payload: dict[str, Any],
    *,
    account_id: str,
    trade_date: str,
    data_date: str | None,
    evidence_type: str,
) -> list[str]:
    blockers: list[str] = []
    if str(payload.get("schema_version") or "").strip() != EVIDENCE_SCHEMA_VERSION:
        blockers.append("Evidence schema_version mismatch.")
    if str(payload.get("evidence_type") or "").strip() != evidence_type:
        blockers.append("Evidence evidence_type mismatch.")
    if str(payload.get("account_id") or "").strip() != account_id:
        blockers.append("Evidence account_id mismatch.")
    if str(payload.get("trade_date") or "").strip() != trade_date:
        blockers.append("Evidence trade_date mismatch.")
    payload_data_date = payload.get("data_date")
    if data_date is not None and payload_data_date not in {None, "", data_date}:
        blockers.append("Evidence data_date mismatch.")
    if str(payload.get("target_system") or "").strip().lower() != "notion":
        blockers.append("Evidence target_system must be notion.")
    if str(payload.get("status") or "").strip().upper() not in {
        STATUS_PASS,
        STATUS_WARNING,
        STATUS_FAILED,
        STATUS_UNKNOWN,
    }:
        blockers.append("Evidence status is missing or unsupported.")
    return blockers


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
