from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from core.notion_account_keys import (
    build_daily_plan_external_key,
    build_manual_execution_canonical_key,
    normalize_notion_account_id,
)
from core.paper_daily_plan_candidates import extract_daily_plan_execution_candidates


SCHEMA_VERSION = "execution_reconciliation_preview.v1"

MATCHED = "MATCHED"
DEVIATED = "DEVIATED"
MISSING = "MISSING"
EXTRA = "EXTRA"

NONE = "NONE"
PRICE = "PRICE"
QUANTITY = "QUANTITY"
PRICE_AND_QUANTITY = "PRICE_AND_QUANTITY"
NOTIONAL = "NOTIONAL"
IDENTITY = "IDENTITY"

INFO = "INFO"
WARNING = "WARNING"
NEEDS_REVIEW = "NEEDS_REVIEW"
BLOCKED = "BLOCKED"

PASS = "PASS"

NOT_IMPORTED = "NOT_IMPORTED"

COMMIT_ELIGIBLE_MESSAGE = "Reconciliation preview is commit-eligible."


@dataclass(frozen=True)
class ReconciliationPolicy:
    price_info_threshold_pct: Decimal = Decimal("1.0")


def build_manual_execution_key(
    account_id: str,
    trade_date: str,
    symbol: str,
    side: str,
    sequence: int,
) -> str:
    return build_manual_execution_canonical_key(account_id, trade_date, symbol, side, sequence)


def load_reconciliation_preview(path: str | Path) -> dict[str, Any]:
    preview_path = Path(path)
    with preview_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError("Reconciliation preview JSON must contain an object.")
    return payload


def get_latest_reconciliation_preview_path(workspace: str | Path, runbook_day_id: str) -> Path:
    return (
        Path(workspace)
        / "reconciliation_runs"
        / runbook_day_id
        / "latest_execution_reconciliation_preview.json"
    )


def validate_reconciliation_preview_for_commit(
    preview: dict[str, Any],
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
    require_runner_result: str = PASS,
) -> dict[str, Any]:
    normalized_account_id = normalize_notion_account_id(account_id)
    if preview.get("schema_version") != SCHEMA_VERSION:
        return _gate_result(
            False,
            preview,
            "invalid_reconciliation_schema",
            f"Expected schema_version {SCHEMA_VERSION}.",
        )
    if normalize_notion_account_id(preview.get("account_id")) != normalized_account_id:
        return _gate_result(False, preview, "reconciliation_context_mismatch", "account_id mismatch.")
    if preview.get("data_date") != data_date:
        return _gate_result(False, preview, "reconciliation_context_mismatch", "data_date mismatch.")
    if preview.get("trade_date") != trade_date:
        return _gate_result(False, preview, "reconciliation_context_mismatch", "trade_date mismatch.")
    runner_result = str(preview.get("runner_result") or "").strip().upper()
    if runner_result != require_runner_result:
        return _gate_result(
            False,
            preview,
            "reconciliation_not_pass",
            f"Reconciliation preview runner_result is {runner_result or 'blank'}; {require_runner_result} is required for commit.",
        )
    count_checks = (
        ("blocked_count", "reconciliation_blocked_count_nonzero"),
        ("needs_review_count", "reconciliation_needs_review_nonzero"),
        ("warning_count", "reconciliation_warning_nonzero"),
        ("missing_count", "reconciliation_missing_count_nonzero"),
        ("extra_count", "reconciliation_extra_count_nonzero"),
    )
    for field, reason_code in count_checks:
        if _int_value(preview.get(field)) != 0:
            return _gate_result(False, preview, reason_code, f"{field} must be 0 for commit.")
    planned_count = _int_value(preview.get("planned_count"))
    actual_count = _int_value(preview.get("actual_count", preview.get("notion_row_count")))
    matched_count = _int_value(preview.get("matched_count"))
    if planned_count != actual_count:
        return _gate_result(
            False,
            preview,
            "reconciliation_count_mismatch",
            "planned_count and actual_count must match for commit.",
        )
    if matched_count != planned_count:
        return _gate_result(
            False,
            preview,
            "reconciliation_count_mismatch",
            "matched_count must equal planned_count for commit.",
        )
    return _gate_result(True, preview, None, COMMIT_ELIGIBLE_MESSAGE)


def reconcile_plan_and_executions(
    plan_items: list[dict[str, Any]] | dict[str, Any],
    execution_rows: list[dict[str, Any]],
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
    daily_plan_path: str | None = None,
    policy: ReconciliationPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or ReconciliationPolicy()
    normalized_account_id = normalize_notion_account_id(account_id)
    plan_rows = normalize_plan_items(plan_items, normalized_account_id, trade_date)
    actual_rows = [
        normalize_execution_row(row, normalized_account_id, trade_date)
        for row in execution_rows
    ]

    rows: list[dict[str, Any]] = []
    actual_by_key: dict[str, dict[str, Any]] = {}
    duplicate_actual_rows: list[dict[str, Any]] = []
    for actual in actual_rows:
        key = actual.get("manual_execution_external_key")
        if key and key not in actual_by_key:
            actual_by_key[key] = actual
        else:
            duplicate_actual_rows.append(actual)

    plan_keys = {row["plan_external_key"] for row in plan_rows}
    for plan_row in plan_rows:
        actual = actual_by_key.get(plan_row["plan_external_key"])
        if actual is None:
            rows.append(_missing_row(plan_row))
            continue
        deltas = compute_execution_deltas(plan_row, actual)
        rows.append(classify_reconciliation(plan_row, actual, deltas, policy))

    for actual in actual_rows:
        key = actual.get("manual_execution_external_key")
        if key not in plan_keys:
            rows.append(_extra_row(actual, "Actual execution row is not present in Daily Plan."))

    for actual in duplicate_actual_rows:
        rows.append(_extra_row(actual, "Duplicate actual execution external_key."))

    summary = summarize_reconciliation(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "runner_result": summary["runner_result"],
        "account_id": normalized_account_id,
        "data_date": data_date,
        "trade_date": trade_date,
        "daily_plan_path": daily_plan_path,
        "notion_row_count": len(execution_rows),
        "actual_count": len(execution_rows),
        "planned_count": len(plan_rows),
        **summary,
        "rows": rows,
        "next_required_action": _next_required_action(summary["runner_result"]),
    }


def normalize_plan_items(
    plan_items: list[dict[str, Any]] | dict[str, Any],
    account_id: str,
    trade_date: str,
) -> list[dict[str, Any]]:
    plan_payload = {"items": plan_items} if isinstance(plan_items, list) else plan_items
    candidates = extract_daily_plan_execution_candidates(plan_payload)
    sequences: defaultdict[tuple[str, str], int] = defaultdict(int)
    rows = []
    linked_daily_plan_key = build_daily_plan_external_key(account_id, trade_date)
    for item in candidates:
        symbol = str(item.get("symbol") or "").strip().upper()
        side = str(item.get("action") or "").strip().upper()
        sequences[(symbol, side)] += 1
        sequence = sequences[(symbol, side)]
        quantity = _to_decimal(item.get("quantity"))
        price = _to_decimal(item.get("price"))
        rows.append(
            {
                "plan_external_key": build_manual_execution_key(
                    account_id,
                    trade_date,
                    symbol,
                    side,
                    sequence,
                ),
                "account_id": normalize_notion_account_id(account_id),
                "trade_date": trade_date,
                "linked_daily_plan_key": linked_daily_plan_key,
                "symbol": symbol,
                "side": side,
                "sequence": sequence,
                "planned_quantity": _json_number(quantity),
                "planned_price": _json_number(price),
                "planned_notional": _json_number(_multiply(quantity, price)),
                "reason": item.get("reason"),
                "note": item.get("note"),
            }
        )
    return rows


def normalize_execution_row(row: dict[str, Any], account_id: str, trade_date: str) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").strip().upper()
    side = str(row.get("side") or "").strip().upper()
    quantity = _to_decimal(row.get("quantity") if row.get("quantity") is not None else row.get("actual_quantity"))
    price = _to_decimal(row.get("actual_price") if row.get("actual_price") is not None else row.get("price"))
    execution_date = _none_if_blank(row.get("execution_date") or row.get("trade_date"))
    external_key = _none_if_blank(
        row.get("external_key")
        or row.get("manual_execution_external_key")
        or row.get("notion_external_key")
    )
    return {
        "manual_execution_external_key": external_key,
        "page_id": _none_if_blank(row.get("page_id") or row.get("id")),
        "account_id": _none_if_blank(row.get("account_id")),
        "trade_date": execution_date,
        "execution_date": execution_date,
        "linked_daily_plan_key": _none_if_blank(row.get("linked_daily_plan_key")),
        "symbol": symbol,
        "side": side,
        "actual_quantity": _json_number(quantity),
        "actual_price": _json_number(price),
        "actual_notional": _json_number(_multiply(quantity, price)),
        "commission": row.get("commission"),
        "status": _none_if_blank(row.get("status")),
        "import_status": str(row.get("import_status") or row.get("import_status_raw") or "").strip().upper(),
        "operator_note": row.get("operator_note") or row.get("note"),
    }


def compute_execution_deltas(plan_row: dict[str, Any], execution_row: dict[str, Any]) -> dict[str, Any]:
    planned_quantity = _to_decimal(plan_row.get("planned_quantity"))
    actual_quantity = _to_decimal(execution_row.get("actual_quantity"))
    planned_price = _to_decimal(plan_row.get("planned_price"))
    actual_price = _to_decimal(execution_row.get("actual_price"))
    planned_notional = _multiply(planned_quantity, planned_price)
    actual_notional = _multiply(actual_quantity, actual_price)
    quantity_delta = _subtract(actual_quantity, planned_quantity)
    price_delta = _subtract(actual_price, planned_price)
    notional_delta = _subtract(actual_notional, planned_notional)
    return {
        "planned_quantity": _json_number(planned_quantity),
        "actual_quantity": _json_number(actual_quantity),
        "planned_price": _json_number(planned_price),
        "actual_price": _json_number(actual_price),
        "planned_notional": _json_number(planned_notional),
        "actual_notional": _json_number(actual_notional),
        "quantity_delta": _json_number(quantity_delta),
        "quantity_delta_pct": _json_number(_pct(quantity_delta, planned_quantity)),
        "price_delta": _json_number(price_delta),
        "price_delta_pct": _json_number(_pct(price_delta, planned_price)),
        "notional_delta": _json_number(notional_delta),
        "notional_delta_pct": _json_number(_pct(notional_delta, planned_notional)),
    }


def classify_reconciliation(
    plan_row: dict[str, Any],
    execution_row: dict[str, Any],
    deltas: dict[str, Any],
    policy: ReconciliationPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or ReconciliationPolicy()
    identity_errors = _identity_errors(plan_row, execution_row)
    base = _base_row(plan_row, execution_row, deltas)
    if identity_errors:
        return {
            **base,
            "reconciliation_status": DEVIATED,
            "deviation_type": IDENTITY,
            "severity": BLOCKED,
            "message": "; ".join(identity_errors),
        }

    quantity_delta = _to_decimal(deltas.get("quantity_delta"))
    price_delta = _to_decimal(deltas.get("price_delta"))
    price_delta_pct = _to_decimal(deltas.get("price_delta_pct"))
    quantity_changed = quantity_delta is not None and quantity_delta != 0
    price_changed = price_delta is not None and price_delta != 0

    if quantity_changed and price_changed:
        return {
            **base,
            "reconciliation_status": DEVIATED,
            "deviation_type": PRICE_AND_QUANTITY,
            "severity": NEEDS_REVIEW,
            "message": "Actual quantity and price differ from Daily Plan.",
        }
    if quantity_changed:
        return {
            **base,
            "reconciliation_status": DEVIATED,
            "deviation_type": QUANTITY,
            "severity": NEEDS_REVIEW,
            "message": "Actual quantity differs from Daily Plan.",
        }
    if price_changed:
        severity = (
            INFO
            if price_delta_pct is not None
            and abs(price_delta_pct) <= policy.price_info_threshold_pct
            else WARNING
        )
        return {
            **base,
            "reconciliation_status": MATCHED if severity == INFO else DEVIATED,
            "deviation_type": NONE if severity == INFO else PRICE,
            "severity": severity,
            "message": (
                "Actual price differs within policy threshold."
                if severity == INFO
                else "Actual price differs from Daily Plan."
            ),
        }
    return {
        **base,
        "reconciliation_status": MATCHED,
        "deviation_type": NONE,
        "severity": INFO,
        "message": "Actual execution matches Daily Plan.",
    }


def summarize_reconciliation(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "matched_count": 0,
        "deviated_count": 0,
        "missing_count": 0,
        "extra_count": 0,
        "warning_count": 0,
        "needs_review_count": 0,
        "blocked_count": 0,
    }
    for row in rows:
        status = row.get("reconciliation_status")
        severity = row.get("severity")
        if status == MATCHED:
            counts["matched_count"] += 1
        elif status == DEVIATED:
            counts["deviated_count"] += 1
        elif status == MISSING:
            counts["missing_count"] += 1
        elif status == EXTRA:
            counts["extra_count"] += 1
        if severity == WARNING:
            counts["warning_count"] += 1
        elif severity == NEEDS_REVIEW:
            counts["needs_review_count"] += 1
        elif severity == BLOCKED:
            counts["blocked_count"] += 1
    return {
        **counts,
        "runner_result": _runner_result_for_counts(counts),
    }


def _base_row(plan_row: dict[str, Any], execution_row: dict[str, Any], deltas: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_external_key": plan_row.get("plan_external_key"),
        "manual_execution_external_key": execution_row.get("manual_execution_external_key"),
        "symbol": plan_row.get("symbol"),
        "side": plan_row.get("side"),
        **deltas,
        "page_id": execution_row.get("page_id"),
        "status": execution_row.get("status"),
        "import_status": execution_row.get("import_status"),
        "operator_note": execution_row.get("operator_note"),
        "commission": execution_row.get("commission"),
    }


def _missing_row(plan_row: dict[str, Any]) -> dict[str, Any]:
    return {
        "plan_external_key": plan_row.get("plan_external_key"),
        "manual_execution_external_key": None,
        "symbol": plan_row.get("symbol"),
        "side": plan_row.get("side"),
        "planned_quantity": plan_row.get("planned_quantity"),
        "actual_quantity": None,
        "planned_price": plan_row.get("planned_price"),
        "actual_price": None,
        "planned_notional": plan_row.get("planned_notional"),
        "actual_notional": None,
        "price_delta": None,
        "price_delta_pct": None,
        "quantity_delta": None,
        "quantity_delta_pct": None,
        "notional_delta": None,
        "notional_delta_pct": None,
        "reconciliation_status": MISSING,
        "deviation_type": IDENTITY,
        "severity": BLOCKED,
        "message": "Daily Plan execution candidate is missing from Notion Manual Executions.",
        "page_id": None,
        "status": None,
        "import_status": None,
        "operator_note": plan_row.get("note"),
    }


def _extra_row(execution_row: dict[str, Any], message: str) -> dict[str, Any]:
    return {
        "plan_external_key": None,
        "manual_execution_external_key": execution_row.get("manual_execution_external_key"),
        "symbol": execution_row.get("symbol"),
        "side": execution_row.get("side"),
        "planned_quantity": None,
        "actual_quantity": execution_row.get("actual_quantity"),
        "planned_price": None,
        "actual_price": execution_row.get("actual_price"),
        "planned_notional": None,
        "actual_notional": execution_row.get("actual_notional"),
        "price_delta": None,
        "price_delta_pct": None,
        "quantity_delta": None,
        "quantity_delta_pct": None,
        "notional_delta": None,
        "notional_delta_pct": None,
        "reconciliation_status": EXTRA,
        "deviation_type": IDENTITY,
        "severity": BLOCKED,
        "message": message,
        "page_id": execution_row.get("page_id"),
        "status": execution_row.get("status"),
        "import_status": execution_row.get("import_status"),
        "operator_note": execution_row.get("operator_note"),
        "commission": execution_row.get("commission"),
    }


def _identity_errors(plan_row: dict[str, Any], execution_row: dict[str, Any]) -> list[str]:
    errors = []
    if execution_row.get("manual_execution_external_key") != plan_row.get("plan_external_key"):
        errors.append("external_key mismatch")
    if _safe_normalize_account_id(execution_row.get("account_id")) != _safe_normalize_account_id(plan_row.get("account_id")):
        errors.append("account_id mismatch")
    if execution_row.get("trade_date") != plan_row.get("trade_date"):
        errors.append("trade_date mismatch")
    if execution_row.get("symbol") != plan_row.get("symbol"):
        errors.append("symbol mismatch")
    if execution_row.get("side") != plan_row.get("side"):
        errors.append("side mismatch")
    if execution_row.get("linked_daily_plan_key") != plan_row.get("linked_daily_plan_key"):
        errors.append("linked_daily_plan_key mismatch")
    if execution_row.get("import_status") != NOT_IMPORTED:
        errors.append("import_status must be NOT_IMPORTED")
    if _to_decimal(execution_row.get("actual_quantity")) is None:
        errors.append("actual quantity is missing or invalid")
    if _to_decimal(execution_row.get("actual_price")) is None:
        errors.append("actual price is missing or invalid")
    return errors


def _runner_result_for_counts(counts: dict[str, int]) -> str:
    if counts["blocked_count"]:
        return BLOCKED
    if counts["needs_review_count"]:
        return NEEDS_REVIEW
    if counts["warning_count"]:
        return WARNING
    return PASS


def _gate_result(
    ok: bool,
    preview: dict[str, Any],
    reason_code: str | None,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "runner_result": str(preview.get("runner_result") or "").strip().upper() or None,
        "reason_code": reason_code,
        "message": message,
        "planned_count": _int_value(preview.get("planned_count")),
        "actual_count": _int_value(preview.get("actual_count", preview.get("notion_row_count"))),
        "matched_count": _int_value(preview.get("matched_count")),
        "warning_count": _int_value(preview.get("warning_count")),
        "needs_review_count": _int_value(preview.get("needs_review_count")),
        "blocked_count": _int_value(preview.get("blocked_count")),
        "missing_count": _int_value(preview.get("missing_count")),
        "extra_count": _int_value(preview.get("extra_count")),
    }


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _next_required_action(runner_result: str) -> str:
    if runner_result == PASS:
        return "Stage B commit preview may proceed."
    if runner_result == WARNING:
        return "Review price warnings before proceeding."
    if runner_result == NEEDS_REVIEW:
        return "Review execution deviations before Stage B commit."
    return "Fix blocked reconciliation rows before Stage B commit."


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not decimal.is_finite():
        return None
    return decimal


def _json_number(value: Decimal | None) -> int | float | None:
    if value is None:
        return None
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return int(normalized)
    return float(normalized)


def _multiply(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None or right is None:
        return None
    return left * right


def _subtract(left: Decimal | None, right: Decimal | None) -> Decimal | None:
    if left is None or right is None:
        return None
    return left - right


def _pct(delta: Decimal | None, base: Decimal | None) -> Decimal | None:
    if delta is None or base is None or base == 0:
        return None
    return (delta / base) * Decimal("100")


def _none_if_blank(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _safe_normalize_account_id(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return normalize_notion_account_id(str(value))
    except Exception:
        return str(value)
