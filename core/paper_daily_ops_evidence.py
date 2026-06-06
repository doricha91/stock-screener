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
