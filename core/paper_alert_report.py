from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from core.paper_account_guard import assert_path_under_account_root
from core.paper_account_paths import build_paper_account_paths
from core.paper_account_profile import validate_account_id


ALERT_REPORT_SCHEMA_VERSION = "paper_alert_report.v1"
SUPPORTED_PHASES = {"closeout"}

SEVERITY_BLOCKING = "BLOCKING"
SEVERITY_NEEDS_REVIEW = "NEEDS_REVIEW"
SEVERITY_SYNC_FAILED = "SYNC_FAILED"
SEVERITY_INFO = "INFO"
SEVERITY_ORDER = (
    SEVERITY_BLOCKING,
    SEVERITY_NEEDS_REVIEW,
    SEVERITY_SYNC_FAILED,
    SEVERITY_INFO,
)

CATEGORY_DAILY_OPS_STATUS = "DAILY_OPS_STATUS"
CATEGORY_DAILY_OPS_PREFLIGHT = "DAILY_OPS_PREFLIGHT"


def normalize_alert_report_date(date_str: str) -> str:
    value = str(date_str).strip()
    if re.fullmatch(r"\d{8}", value):
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    raise ValueError("date must be YYYY-MM-DD or YYYYMMDD")


def compact_alert_report_date(date_str: str) -> str:
    return normalize_alert_report_date(date_str).replace("-", "")


def default_alert_output_dir(account_id: str) -> Path:
    account_paths = build_paper_account_paths(validate_account_id(account_id), create=False)
    return account_paths.root / "alerts"


@dataclass(frozen=True)
class AlertItem:
    severity: str
    category: str
    account_id: str
    status_date: str
    title: str
    message: str
    recommended_action: str
    evidence: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    source_path: str = ""
    external_safe: bool = True
    sendable: bool = False
    redacted: bool = True
    suppressed_in_markdown: bool = False
    suppression_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ALERT_REPORT_SCHEMA_VERSION,
            "severity": self.severity,
            "category": self.category,
            "account_id": self.account_id,
            "status_date": self.status_date,
            "title": self.title,
            "message": self.message,
            "recommended_action": self.recommended_action,
            "evidence": redact_payload(self.evidence),
            "source": self.source,
            "source_path": redact_path(self.source_path),
            "external_safe": self.external_safe,
            "sendable": self.sendable,
            "redacted": self.redacted,
            "suppressed_in_markdown": self.suppressed_in_markdown,
            "suppression_reason": self.suppression_reason,
        }


def build_paper_alert_report(
    *,
    account_id: str,
    report_date: str,
    phase: str = "closeout",
    actual_intent: bool = False,
    daily_ops_status: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
    daily_ops_source_path: str = "",
    preflight_source_path: str = "",
) -> dict[str, Any]:
    resolved_account_id = validate_account_id(account_id)
    resolved_date = normalize_alert_report_date(report_date)
    if phase not in SUPPORTED_PHASES:
        raise ValueError("phase must be closeout")

    items: list[AlertItem] = []
    if daily_ops_status:
        items.extend(
            _items_from_daily_ops_status(
                daily_ops_status,
                account_id=resolved_account_id,
                status_date=resolved_date,
                source_path=daily_ops_source_path,
            )
        )
    if preflight:
        items.extend(
            _items_from_preflight(
                preflight,
                account_id=resolved_account_id,
                status_date=resolved_date,
                actual_intent=actual_intent,
                source_path=preflight_source_path,
            )
        )

    item_dicts = [item.to_dict() for item in items]
    return {
        "schema_version": ALERT_REPORT_SCHEMA_VERSION,
        "account_id": resolved_account_id,
        "report_date": resolved_date,
        "phase": phase,
        "actual_intent": bool(actual_intent),
        "summary": _summarize_items(item_dicts),
        "items": item_dicts,
        "delivery": {
            "delivery_executed": False,
            "delivery_adapter": None,
        },
    }


def write_paper_alert_report(report: dict[str, Any], output_dir: str | Path | None = None) -> dict[str, str]:
    account_id = validate_account_id(str(report["account_id"]))
    report_date = normalize_alert_report_date(str(report["report_date"]))
    target_dir = Path(output_dir) if output_dir is not None else default_alert_output_dir(account_id)
    if output_dir is None:
        account_root = build_paper_account_paths(account_id, create=False).root
        assert_path_under_account_root(target_dir, account_root)
    target_dir.mkdir(parents=True, exist_ok=True)

    date_key = compact_alert_report_date(report_date)
    json_path = target_dir / f"paper_alert_report_{date_key}.json"
    markdown_path = target_dir / f"paper_alert_report_{date_key}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_paper_alert_report_markdown(report), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path)}


def render_paper_alert_report_markdown(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        f"# Paper Ops Exception Report - {report.get('account_id')} - {report.get('report_date')}",
        "",
        "## Summary",
        f"- BLOCKING: {summary.get('blocking_count', 0)}",
        f"- NEEDS_REVIEW: {summary.get('needs_review_count', 0)}",
        f"- SYNC_FAILED: {summary.get('sync_failed_count', 0)}",
        f"- INFO: {summary.get('info_count', 0)}",
        f"- Suppressed INFO: {summary.get('suppressed_info_count', 0)}",
        "",
    ]
    for severity, title in (
        (SEVERITY_BLOCKING, "Blocking"),
        (SEVERITY_NEEDS_REVIEW, "Needs Review"),
        (SEVERITY_SYNC_FAILED, "Sync Failed"),
    ):
        lines.extend([f"## {title}", ""])
        matching = [item for item in report.get("items", []) if item.get("severity") == severity]
        if not matching:
            lines.extend(["- None", ""])
            continue
        for item in matching:
            lines.extend(
                [
                    f"- {item.get('title')}",
                    f"  - Message: {item.get('message')}",
                    f"  - Recommended action: {item.get('recommended_action')}",
                ]
            )
        lines.append("")
    info_items = [item for item in report.get("items", []) if item.get("severity") == SEVERITY_INFO]
    suppressed_reasons: dict[str, int] = {}
    for item in info_items:
        reason = str(item.get("suppression_reason") or "not_suppressed")
        if item.get("suppressed_in_markdown"):
            suppressed_reasons[reason] = suppressed_reasons.get(reason, 0) + 1
    lines.extend(
        [
            "## Info / Suppressed Summary",
            "",
            f"- INFO: {len(info_items)}",
            f"- Suppressed INFO: {sum(suppressed_reasons.values())}",
            "- INFO details are preserved in JSON.",
        ]
    )
    for reason, count in sorted(suppressed_reasons.items()):
        lines.append(f"- Suppression reason `{reason}`: {count}")
    lines.append("")
    lines.extend(
        [
            "## Source Inputs",
            f"- phase: {report.get('phase')}",
            f"- actual_intent: {str(report.get('actual_intent')).lower()}",
            "",
            "## Redaction Notes",
            "- Notion token, data source id, full page_id, absolute paths, and secret/env values are redacted.",
            "- Delivery adapters are not executed by this report generator.",
            "",
        ]
    )
    return "\n".join(lines)


def redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _redact_by_key(str(key), child) for key, child in value.items()}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_path(_redact_secret_like_string(value))
    return value


def redact_path(value: str) -> str:
    if not value:
        return ""
    raw = str(value)
    if re.match(r"^[A-Za-z]:[\\/]", raw) or raw.startswith("\\\\") or raw.startswith("/"):
        return "<redacted_path>"
    return raw


def _redact_by_key(key: str, value: Any) -> Any:
    lowered = key.lower()
    if any(token in lowered for token in ("token", "secret", "data_source_id")):
        return _mask_identifier(str(value))
    if lowered in {"page_id", "page_ids", "expected_page_id"} or lowered.endswith("_page_id"):
        if isinstance(value, list):
            return [_mask_identifier(str(item)) for item in value]
        return _mask_identifier(str(value))
    return redact_payload(value)


def _mask_identifier(value: str) -> str:
    stripped = str(value).strip()
    if not stripped:
        return ""
    return f"****{stripped[-4:]}" if len(stripped) > 4 else "****"


def _redact_secret_like_string(value: str) -> str:
    if "secret_" in value.lower() or "token" in value.lower():
        return "<redacted_secret>"
    return value


def _items_from_daily_ops_status(
    payload: dict[str, Any],
    *,
    account_id: str,
    status_date: str,
    source_path: str,
) -> list[AlertItem]:
    items: list[AlertItem] = []
    payload_account = str(payload.get("account_id") or payload.get("Account ID") or account_id)
    if payload_account != account_id:
        items.append(
            AlertItem(
                severity=SEVERITY_BLOCKING,
                category=CATEGORY_DAILY_OPS_STATUS,
                account_id=account_id,
                status_date=status_date,
                title="Daily Ops Status account mismatch",
                message=f"payload account_id={payload_account} does not match requested account_id={account_id}.",
                recommended_action="Stop actual operations and inspect the source Daily Ops Status payload.",
                evidence={"payload_account_id": payload_account},
                source="daily_ops_status",
                source_path=source_path,
            )
        )

    sync_status = str(payload.get("sync_status") or payload.get("Sync Status") or "").upper()
    if sync_status in {"FAILED", "SYNC_FAILED"}:
        items.append(
            AlertItem(
                severity=SEVERITY_SYNC_FAILED,
                category=CATEGORY_DAILY_OPS_STATUS,
                account_id=account_id,
                status_date=status_date,
                title="Daily Ops Status sync failed",
                message="Local source-of-truth may be valid, but Notion presentation sync/export failed.",
                recommended_action="Do not rollback local source-of-truth; rerun only the documented sync/export path after preflight.",
                evidence={"sync_status": sync_status},
                source="daily_ops_status",
                source_path=source_path,
            )
        )

    workflow_status = str(payload.get("workflow_status") or payload.get("Workflow Status") or "").upper()
    if workflow_status in {"UNKNOWN_OR_INCOMPLETE", "NO_PLAN"}:
        items.append(
            AlertItem(
                severity=SEVERITY_BLOCKING,
                category=CATEGORY_DAILY_OPS_STATUS,
                account_id=account_id,
                status_date=status_date,
                title=f"Daily Ops workflow status is {workflow_status}",
                message="Daily Ops Status indicates a missing or incomplete local workflow state.",
                recommended_action="Inspect local paper.py status before any actual export/sync.",
                evidence={"workflow_status": workflow_status},
                source="daily_ops_status",
                source_path=source_path,
            )
        )
    return items


def _items_from_preflight(
    payload: dict[str, Any],
    *,
    account_id: str,
    status_date: str,
    actual_intent: bool,
    source_path: str,
) -> list[AlertItem]:
    payload_account = str(payload.get("account_id") or account_id)
    if payload_account != account_id:
        return [
            AlertItem(
                severity=SEVERITY_BLOCKING,
                category=CATEGORY_DAILY_OPS_PREFLIGHT,
                account_id=account_id,
                status_date=status_date,
                title="Daily Ops actual preflight account mismatch",
                message=f"preflight account_id={payload_account} does not match requested account_id={account_id}.",
                recommended_action="Stop actual operations and regenerate preflight with the intended account_id.",
                evidence={"payload_account_id": payload_account},
                source="daily_ops_actual_preflight",
                source_path=source_path,
            )
        ]

    overall = str(payload.get("overall_status") or "").upper()
    schema_result = str(payload.get("schema_validation_result") or "").upper()
    duplicate = payload.get("duplicate_audit") if isinstance(payload.get("duplicate_audit"), dict) else {}
    duplicate_classification = str(duplicate.get("classification") or "").lower()
    expected_page_missing = _has_expected_page_missing_warning(payload)

    if overall == "FAIL" or schema_result == "FAIL" or duplicate_classification == "duplicate_blocker":
        return [
            AlertItem(
                severity=SEVERITY_BLOCKING,
                category=CATEGORY_DAILY_OPS_PREFLIGHT,
                account_id=account_id,
                status_date=status_date,
                title="Daily Ops actual preflight returned blocking result",
                message=_preflight_blocking_message(overall, schema_result, duplicate_classification),
                recommended_action="Do not run actual export. Resolve the blocking preflight result first.",
                evidence=_preflight_evidence(payload),
                source="daily_ops_actual_preflight",
                source_path=source_path,
            )
        ]

    if overall == "WARNING" and actual_intent:
        return [
            AlertItem(
                severity=SEVERITY_NEEDS_REVIEW,
                category=CATEGORY_DAILY_OPS_PREFLIGHT,
                account_id=account_id,
                status_date=status_date,
                title="Daily Ops actual preflight returned WARNING",
                message="Operator confirmation is required before any actual export.",
                recommended_action="Confirm expected_page_id and preflight evidence before requesting actual export approval.",
                evidence=_preflight_evidence(payload),
                source="daily_ops_actual_preflight",
                source_path=source_path,
            )
        ]

    if overall == "WARNING" and not actual_intent:
        message = (
            "Preflight warning is informational because actual_intent=false."
            if expected_page_missing
            else "Preflight warning recorded without actual export intent."
        )
        return [
            AlertItem(
                severity=SEVERITY_INFO,
                category=CATEGORY_DAILY_OPS_PREFLIGHT,
                account_id=account_id,
                status_date=status_date,
                title="Daily Ops actual preflight warning suppressed for non-actual run",
                message=message,
                recommended_action="No actual action unless an operator intends to run guarded actual export.",
                evidence=_preflight_evidence(payload),
                source="daily_ops_actual_preflight",
                source_path=source_path,
                suppressed_in_markdown=True,
                suppression_reason="actual_intent=false" if expected_page_missing else "non_actual_warning",
            )
        ]

    if duplicate_classification == "update_candidate" and not actual_intent:
        return [
            AlertItem(
                severity=SEVERITY_INFO,
                category=CATEGORY_DAILY_OPS_PREFLIGHT,
                account_id=account_id,
                status_date=status_date,
                title="Daily Ops duplicate audit found update candidate",
                message="One matching External Key row exists; this is informational without actual export intent.",
                recommended_action="If actual export is intended later, rerun preflight with expected_page_id.",
                evidence=_preflight_evidence(payload),
                source="daily_ops_actual_preflight",
                source_path=source_path,
                suppressed_in_markdown=True,
                suppression_reason="actual_intent=false",
            )
        ]

    if overall == "PASS":
        return [
            AlertItem(
                severity=SEVERITY_INFO,
                category=CATEGORY_DAILY_OPS_PREFLIGHT,
                account_id=account_id,
                status_date=status_date,
                title="Daily Ops actual preflight passed",
                message="Preflight prerequisites appear satisfied, but this is not actual export approval.",
                recommended_action="Proceed only if a separate explicit actual export approval exists.",
                evidence=_preflight_evidence(payload),
                source="daily_ops_actual_preflight",
                source_path=source_path,
                suppressed_in_markdown=True,
                suppression_reason="preflight_pass_info",
            )
        ]
    return []


def _has_expected_page_missing_warning(payload: dict[str, Any]) -> bool:
    for check in payload.get("checks", []) or []:
        if not isinstance(check, dict):
            continue
        if "expected_page_id" in str(check.get("message", "")).lower():
            return True
    return False


def _preflight_blocking_message(overall: str, schema_result: str, duplicate_classification: str) -> str:
    if duplicate_classification == "duplicate_blocker":
        return "Duplicate audit found multiple matching External Key rows."
    if schema_result == "FAIL":
        return "Daily Ops Status schema validation failed."
    return f"Daily Ops actual preflight overall_status={overall}."


def _preflight_evidence(payload: dict[str, Any]) -> dict[str, Any]:
    duplicate = payload.get("duplicate_audit") if isinstance(payload.get("duplicate_audit"), dict) else {}
    return {
        "overall_status": payload.get("overall_status"),
        "schema_validation_result": payload.get("schema_validation_result"),
        "recommended_action": payload.get("recommended_action"),
        "external_key": payload.get("external_key"),
        "duplicate_audit": duplicate,
        "checks": payload.get("checks", []),
        "write_executed": payload.get("write_executed", False),
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
    }


def _summarize_items(items: list[dict[str, Any]]) -> dict[str, int]:
    counts = {severity: 0 for severity in SEVERITY_ORDER}
    for item in items:
        severity = str(item.get("severity", ""))
        if severity in counts:
            counts[severity] += 1
    return {
        "blocking_count": counts[SEVERITY_BLOCKING],
        "needs_review_count": counts[SEVERITY_NEEDS_REVIEW],
        "sync_failed_count": counts[SEVERITY_SYNC_FAILED],
        "info_count": counts[SEVERITY_INFO],
        "suppressed_info_count": sum(
            1
            for item in items
            if item.get("severity") == SEVERITY_INFO and item.get("suppressed_in_markdown")
        ),
    }
