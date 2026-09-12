from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from core.execution_reconciliation import (
    BLOCKED,
    EXECUTED,
    NOT_EXECUTED,
    PARTIAL,
    PASS,
    WAIT,
    derive_execution_outcomes,
    normalize_execution_row,
    normalize_plan_items,
    reconcile_plan_and_executions,
)


RECONCILIATION_CONTRACT_V1 = "execution_reconciliation_preview.v1"
RECONCILIATION_CONTRACT_V2 = "execution_reconciliation_preview.v2"
RECONCILIATION_CONTRACT_V3 = "execution_reconciliation_preview.v3"
OUTCOME_CONTRACT_V2 = "execution_outcome.v2"
OUTCOME_CONTRACT_V3 = "execution_outcome.v3"
SUPPORTED_RECONCILIATION_CONTRACTS = {
    RECONCILIATION_CONTRACT_V1,
    RECONCILIATION_CONTRACT_V2,
    RECONCILIATION_CONTRACT_V3,
}
TRADE_BEARING_OUTCOMES = {EXECUTED, PARTIAL}


def derive_execution_preview(
    daily_plan: dict[str, Any],
    execution_rows: list[dict[str, Any]],
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
    contract_version: str,
    input_finalized: bool,
    daily_plan_path: str | None = None,
) -> dict[str, Any]:
    """Dispatch completed v1 unchanged and new runbooks to the v2 outcome path."""
    if contract_version == RECONCILIATION_CONTRACT_V1:
        return reconcile_plan_and_executions(
            daily_plan,
            execution_rows,
            account_id=account_id,
            data_date=data_date,
            trade_date=trade_date,
            daily_plan_path=daily_plan_path,
        )
    if contract_version not in {RECONCILIATION_CONTRACT_V2, RECONCILIATION_CONTRACT_V3}:
        return _unsupported_version_result(contract_version)

    plan_rows = normalize_plan_items(daily_plan, account_id, trade_date)
    normalized_execution_rows = [
        normalize_execution_row(row, account_id, trade_date) for row in execution_rows
    ]
    context = {
        "account_id": account_id,
        "data_date": data_date,
        "trade_date": trade_date,
        "contract_version": OUTCOME_CONTRACT_V3 if contract_version == RECONCILIATION_CONTRACT_V3 else OUTCOME_CONTRACT_V2,
    }
    result = derive_execution_outcomes(
        plan_rows,
        normalized_execution_rows,
        input_finalized=input_finalized,
        plan_context=context,
        execution_context=context,
    )
    result["schema_version"] = contract_version
    result["reconciliation_contract_version"] = contract_version
    result["account_id"] = account_id
    result["data_date"] = data_date
    result["trade_date"] = trade_date

    plan_by_key = {row["plan_external_key"]: row for row in plan_rows}
    execution_by_key = {
        row["manual_execution_external_key"]: row
        for row in normalized_execution_rows
        if row.get("manual_execution_external_key")
    }
    price_errors: list[dict[str, Any]] = []
    for row in result.get("rows", []):
        key = row["candidate_key"]
        plan_row = plan_by_key[key]
        execution_row = execution_by_key[key]
        row.update(
            account_id=account_id,
            data_date=data_date,
            trade_date=trade_date,
            symbol=plan_row.get("symbol"),
            side=plan_row.get("side"),
            planned_price=plan_row.get("planned_price"),
            actual_price=execution_row.get("actual_price"),
            page_id=execution_row.get("page_id"),
            linked_daily_plan_key=execution_row.get("linked_daily_plan_key"),
            execution_sequence=execution_row.get("execution_sequence"),
        )
        reason = _price_reason(row)
        if reason is not None:
            row.update(status=BLOCKED, outcome=None, reason_code=reason)
            price_errors.append(
                {
                    "candidate_key": key,
                    "reason_code": reason,
                    "message": "Quantity and price must both be blank, or both be finite and positive.",
                }
            )

    sequence_errors = _validate_v3_execution_sequences(result.get("rows", [])) if contract_version == RECONCILIATION_CONTRACT_V3 else []
    if price_errors or sequence_errors:
        result["runner_result"] = BLOCKED
        result["errors"] = sorted(
            [*result.get("errors", []), *price_errors, *sequence_errors],
            key=lambda item: (str(item.get("candidate_key") or ""), str(item.get("reason_code") or "")),
        )
        result["invalid_count"] = len(result["errors"])
        _refresh_outcome_counts(result)
    return result


def build_execution_commit_plan(preview: dict[str, Any]) -> dict[str, Any]:
    """Return the only rows that may reach the existing Paper writer."""
    version = preview.get("schema_version") or preview.get("reconciliation_contract_version")
    if version == RECONCILIATION_CONTRACT_V1:
        return {"runner_result": PASS, "dispatch": "V1", "legacy_preview": preview}
    if version not in {RECONCILIATION_CONTRACT_V2, RECONCILIATION_CONTRACT_V3}:
        return _unsupported_version_result(version)
    if preview.get("input_finalized") is not True:
        return {
            "runner_result": BLOCKED,
            "reason_code": "execution_input_not_finalized",
            "persistent_write": False,
            "rows": [],
        }
    if preview.get("runner_result") != PASS or preview.get("count_invariant_satisfied") is not True:
        return {
            "runner_result": BLOCKED,
            "reason_code": "outcome_preview_not_commit_eligible",
            "persistent_write": False,
            "rows": [],
        }
    rows = list(preview.get("rows") or [])
    if any(row.get("status") == BLOCKED for row in rows):
        return {
            "runner_result": BLOCKED,
            "reason_code": "blocked_outcome_row",
            "persistent_write": False,
            "rows": [],
        }
    trade_rows = [row for row in rows if row.get("outcome") in TRADE_BEARING_OUTCOMES]
    if version == RECONCILIATION_CONTRACT_V3:
        trade_rows.sort(key=lambda row: int(row["execution_sequence"]))
    return {
        "runner_result": PASS,
        "dispatch": "V3" if version == RECONCILIATION_CONTRACT_V3 else "V2",
        "rows": trade_rows,
        "candidate_keys": [row.get("candidate_key") for row in trade_rows],
        "committed_trade_count": len(trade_rows),
        "not_executed_count": sum(row.get("outcome") == NOT_EXECUTED for row in rows),
        "persistent_write": bool(trade_rows),
        "requires_latest_state_revalidation": bool(trade_rows),
    }


def filter_execution_preview_candidates(
    preview_payload: dict[str, Any],
    eligible_candidate_keys: set[str],
    *,
    expected_outcome_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Share writer eligibility/consistency checks without changing its existing order."""
    candidates = list(preview_payload.get("candidates") or [])
    keyed = {}
    for candidate in candidates:
        key = str(candidate.get("canonical_key") or candidate.get("notion_external_key") or "").strip()
        if key in eligible_candidate_keys and key in keyed:
            raise ValueError(f"Duplicate input preview candidate key: {key}")
        keyed[key] = candidate
    missing = sorted(eligible_candidate_keys - set(keyed))
    if missing:
        raise ValueError(
            "Outcome preview candidate keys are missing from the input preview: " + ", ".join(missing)
        )
    ordered_keys = sorted(eligible_candidate_keys)
    if expected_outcome_rows is not None:
        expected_by_key = {}
        for row in expected_outcome_rows:
            key = str(row.get("candidate_key") or "").strip()
            if not key or key in expected_by_key:
                raise ValueError("Pinned reconciliation preview has invalid trade-bearing candidate keys.")
            expected_by_key[key] = row
        if set(expected_by_key) != eligible_candidate_keys:
            raise ValueError("Pinned reconciliation preview candidate keys changed before commit.")
        ordered_keys = [str(row.get("candidate_key") or "").strip() for row in expected_outcome_rows]
        for key in ordered_keys:
            candidate = keyed[key]
            expected = expected_by_key.get(key)
            if expected is None:
                raise ValueError(f"Missing outcome row for commit candidate: {key}")
            if (
                str(candidate.get("symbol") or "").strip().upper() != str(expected.get("symbol") or "").strip().upper()
                or str(candidate.get("side") or "").strip().upper() != str(expected.get("side") or "").strip().upper()
                or not _same_number(candidate.get("quantity"), expected.get("actual_quantity"))
                or not _same_number(candidate.get("actual_price"), expected.get("actual_price"))
                or (expected.get("execution_sequence") is not None and not _same_number(candidate.get("execution_sequence"), expected.get("execution_sequence")))
            ):
                raise ValueError(
                    f"Input preview does not match the pinned outcome row: {key}"
                )
    selected = [keyed[key] for key in ordered_keys]
    filtered = dict(preview_payload)
    filtered["candidates"] = selected
    filtered["candidate_count"] = len(selected)
    filtered["pass_count"] = sum(item.get("validation_status") == PASS for item in selected)
    filtered["warning_count"] = sum(item.get("validation_status") == "WARNING" for item in selected)
    filtered["fail_count"] = sum(item.get("validation_status") not in {PASS, "WARNING"} for item in selected)
    filtered["commit_allowed"] = (
        "false"
        if filtered["fail_count"]
        else "true_with_warnings"
        if filtered["warning_count"]
        else "true"
    )
    return filtered


def validate_effective_execution_candidates(
    preview_payload: dict[str, Any],
    reconciliation: dict[str, Any],
) -> None:
    """Reject an invalid v2 write-set before the runner creates a commit attempt."""
    commit_plan = build_execution_commit_plan(reconciliation)
    if commit_plan.get("runner_result") != PASS or commit_plan.get("dispatch") not in {"V2", "V3"}:
        raise ValueError("Pinned reconciliation preview is not outcome commit-eligible.")
    keys = [str(key or "").strip() for key in commit_plan["candidate_keys"]]
    if any(not key for key in keys) or len(set(keys)) != len(keys):
        raise ValueError("Pinned reconciliation preview has invalid trade-bearing candidate keys.")
    effective_preview = filter_execution_preview_candidates(
        preview_payload,
        set(keys),
        expected_outcome_rows=commit_plan["rows"],
    )
    if effective_preview["fail_count"]:
        raise ValueError("Effective execution preview contains FAIL rows; commit is blocked.")
    # WARNING policy remains with the existing writer/runbook contract.


def _same_number(left: Any, right: Any) -> bool:
    try:
        left_number = Decimal(str(left))
        right_number = Decimal(str(right))
    except (InvalidOperation, ValueError):
        return False
    return left_number.is_finite() and right_number.is_finite() and left_number == right_number


def _price_reason(row: dict[str, Any]) -> str | None:
    quantity_blank = _blank(row.get("actual_quantity"))
    price_blank = _blank(row.get("actual_price"))
    if quantity_blank and price_blank:
        return None
    if quantity_blank:
        return "price_without_quantity"
    if price_blank:
        return "quantity_without_price"
    if _positive_finite_decimal(row.get("actual_price")) is None:
        return "actual_price_invalid"
    return None


def _validate_v3_execution_sequences(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    seen: dict[int, str] = {}
    for row in rows:
        sequence = _positive_integer(row.get("execution_sequence"))
        outcome = row.get("outcome")
        key = str(row.get("candidate_key") or "")
        if outcome in TRADE_BEARING_OUTCOMES:
            if sequence is None:
                row.update(status=BLOCKED, outcome=None, reason_code="execution_sequence_required")
                errors.append({"candidate_key": key, "reason_code": "execution_sequence_required", "message": "EXECUTED/PARTIAL requires a positive integer execution_sequence."})
            elif sequence in seen:
                row.update(status=BLOCKED, outcome=None, reason_code="duplicate_execution_sequence")
                errors.append({"candidate_key": key, "reason_code": "duplicate_execution_sequence", "message": "execution_sequence must be unique within the account and trade date."})
            else:
                row["execution_sequence"] = sequence
                seen[sequence] = key
        elif outcome == NOT_EXECUTED and not _blank(row.get("execution_sequence")):
            row.update(status=BLOCKED, outcome=None, reason_code="execution_sequence_not_executed_must_be_blank")
            errors.append({"candidate_key": key, "reason_code": "execution_sequence_not_executed_must_be_blank", "message": "NOT_EXECUTED requires a blank execution_sequence."})
    return errors


def _positive_integer(value: Any) -> int | None:
    if isinstance(value, bool) or _blank(value):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite() or number <= 0 or number != number.to_integral_value():
        return None
    return int(number)


def _positive_finite_decimal(value: Any) -> Decimal | None:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() and number > 0 else None


def _blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def _refresh_outcome_counts(result: dict[str, Any]) -> None:
    rows = result.get("rows", [])
    result["executed_count"] = sum(row.get("outcome") == EXECUTED for row in rows)
    result["partial_count"] = sum(row.get("outcome") == PARTIAL for row in rows)
    result["not_executed_count"] = sum(row.get("outcome") == NOT_EXECUTED for row in rows)
    result["waiting_count"] = sum(row.get("status") == WAIT for row in rows)
    result["resolved_count"] = (
        result["executed_count"] + result["partial_count"] + result["not_executed_count"]
    )
    result["count_invariant_satisfied"] = False


def _unsupported_version_result(version: Any) -> dict[str, Any]:
    return {
        "runner_result": BLOCKED,
        "reason_code": "unsupported_execution_contract_version",
        "contract_version": version,
        "persistent_write": False,
        "rows": [],
        "errors": [
            {
                "candidate_key": None,
                "reason_code": "unsupported_execution_contract_version",
                "message": f"Unsupported execution contract version: {version!r}.",
            }
        ],
    }
