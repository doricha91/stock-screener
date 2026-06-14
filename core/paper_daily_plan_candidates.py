from __future__ import annotations

from typing import Any


EXECUTION_ACTIONS = {"BUY", "SELL"}
CANDIDATE_COUNT_RULE = "items.action_in_buy_sell_quantity_positive.v1"


def _normalize_action(value: Any) -> str:
    return str(value or "").strip().upper()


def _positive_quantity(value: Any) -> float | None:
    try:
        quantity = float(value)
    except (TypeError, ValueError):
        return None
    if quantity <= 0:
        return None
    return quantity


def is_daily_plan_execution_candidate(item: Any) -> bool:
    """Return True for official Daily Plan BUY/SELL rows with positive quantity."""

    if not isinstance(item, dict):
        return False
    action = _normalize_action(item.get("action"))
    if action not in EXECUTION_ACTIONS:
        return False
    symbol = str(item.get("symbol") or "").strip()
    if not symbol:
        return False
    return _positive_quantity(item.get("quantity")) is not None


def extract_daily_plan_execution_candidates(plan: Any) -> list[dict[str, Any]]:
    if not isinstance(plan, dict):
        return []
    items = plan.get("items")
    if not isinstance(items, list):
        return []
    return [item for item in items if is_daily_plan_execution_candidate(item)]


def count_daily_plan_execution_candidates(plan: Any) -> int:
    return len(extract_daily_plan_execution_candidates(plan))
