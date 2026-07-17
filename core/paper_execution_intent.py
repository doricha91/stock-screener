from __future__ import annotations

import math
from typing import Any


DAILY_PLAN_SCHEMA_VERSION = "paper_daily_plan.v1"
EXECUTION_INTENT_SCHEMA_VERSION = "paper_execution_intent.v1"
NO_ACTION_REASON = "no_executable_orders"


def _validate_executable_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        raise ValueError("items_must_be_list")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"item_{index}_must_be_object")
        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError(f"item_{index}_symbol_invalid")
        if item.get("action") not in {"BUY", "SELL"}:
            raise ValueError(f"item_{index}_action_invalid")
        quantity = item.get("quantity")
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, (int, float))
            or not math.isfinite(float(quantity))
            or quantity <= 0
        ):
            raise ValueError(f"item_{index}_quantity_invalid")
    return items


def build_execution_intent(items: list[dict[str, Any]]) -> dict[str, Any]:
    executable_items = _validate_executable_items(items)
    count = len(executable_items)
    if count == 0:
        return {
            "schema_version": EXECUTION_INTENT_SCHEMA_VERSION,
            "action_mode": "NO_ACTION",
            "execution_required": False,
            "candidate_execution_count": 0,
            "no_action_reason": NO_ACTION_REASON,
        }
    return {
        "schema_version": EXECUTION_INTENT_SCHEMA_VERSION,
        "action_mode": "EXECUTION",
        "execution_required": True,
        "candidate_execution_count": count,
        "no_action_reason": None,
    }


def validate_daily_plan_execution_intent(
    payload: dict[str, Any],
    *,
    expected_account_id: str | None = None,
    expected_data_date: str | None = None,
    expected_trade_date: str | None = None,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("daily_plan_payload_must_be_object")
    if payload.get("schema_version") != DAILY_PLAN_SCHEMA_VERSION:
        raise ValueError("daily_plan_schema_version_invalid")
    for field_name in ("account_id", "data_date", "trade_date", "plan_date", "run_mode", "generated_at"):
        value = payload.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"daily_plan_{field_name}_invalid")
    if not isinstance(payload.get("official_run"), bool):
        raise ValueError("daily_plan_official_run_invalid")
    if not isinstance(payload.get("fingerprints"), dict):
        raise ValueError("daily_plan_fingerprints_invalid")

    expected_context = {
        "account_id": expected_account_id,
        "data_date": expected_data_date,
        "trade_date": expected_trade_date,
    }
    for field_name, expected_value in expected_context.items():
        actual_value = payload.get(field_name)
        if expected_value is not None and actual_value != expected_value:
            raise ValueError(f"{field_name}_mismatch")

    expected_intent = build_execution_intent(payload.get("items"))
    intent = payload.get("execution_intent")
    if not isinstance(intent, dict):
        raise ValueError("execution_intent_must_be_object")
    if intent.get("schema_version") != EXECUTION_INTENT_SCHEMA_VERSION:
        raise ValueError("execution_intent_schema_version_invalid")
    if intent.get("action_mode") not in {"EXECUTION", "NO_ACTION"}:
        raise ValueError("execution_intent_action_mode_invalid")
    if not isinstance(intent.get("execution_required"), bool):
        raise ValueError("execution_intent_execution_required_invalid")
    count = intent.get("candidate_execution_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 0:
        raise ValueError("execution_intent_candidate_execution_count_invalid")

    for field_name, expected_value in expected_intent.items():
        if intent.get(field_name) != expected_value:
            raise ValueError(f"execution_intent_{field_name}_mismatch")
    return dict(intent)
