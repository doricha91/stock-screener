from __future__ import annotations

import copy

import pytest

from core.paper_execution_intent import (
    build_execution_intent,
    validate_daily_plan_execution_intent,
)


def _item(action: str = "BUY") -> dict:
    return {"symbol": "AAPL", "action": action, "quantity": 3}


def _payload(items: list[dict]) -> dict:
    return {
        "schema_version": "paper_daily_plan.v1",
        "account_id": "paper_test",
        "data_date": "2026-07-15",
        "trade_date": "2026-07-16",
        "plan_date": "2026-07-16",
        "run_mode": "official",
        "official_run": True,
        "generated_at": "2026-07-15T12:00:00Z",
        "items": items,
        "execution_intent": build_execution_intent(items),
        "fingerprints": {"generator_version": "paper_daily_plan.v1"},
    }


def test_build_execution_intent_for_no_action() -> None:
    assert build_execution_intent([]) == {
        "schema_version": "paper_execution_intent.v1",
        "action_mode": "NO_ACTION",
        "execution_required": False,
        "candidate_execution_count": 0,
        "no_action_reason": "no_executable_orders",
    }


@pytest.mark.parametrize("action", ["BUY", "SELL"])
def test_build_execution_intent_for_one_order(action: str) -> None:
    intent = build_execution_intent([_item(action)])
    assert intent["action_mode"] == "EXECUTION"
    assert intent["execution_required"] is True
    assert intent["candidate_execution_count"] == 1
    assert intent["no_action_reason"] is None


def test_build_execution_intent_counts_buy_and_sell() -> None:
    assert build_execution_intent([_item("BUY"), _item("SELL")])["candidate_execution_count"] == 2


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("symbol", "", "symbol_invalid"),
        ("action", "HOLD", "action_invalid"),
        ("quantity", 0, "quantity_invalid"),
        ("quantity", -1, "quantity_invalid"),
    ],
)
def test_malformed_item_is_rejected(field: str, value: object, error: str) -> None:
    item = _item()
    item[field] = value
    with pytest.raises(ValueError, match=error):
        build_execution_intent([item])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("candidate_execution_count", 2),
        ("execution_required", False),
        ("action_mode", "NO_ACTION"),
    ],
)
def test_execution_intent_contradictions_are_rejected(field: str, value: object) -> None:
    payload = _payload([_item()])
    payload["execution_intent"][field] = value
    with pytest.raises(ValueError, match="execution_intent"):
        validate_daily_plan_execution_intent(payload)


def test_execution_mode_without_items_is_rejected() -> None:
    payload = _payload([])
    payload["execution_intent"] = {
        "schema_version": "paper_execution_intent.v1",
        "action_mode": "EXECUTION",
        "execution_required": True,
        "candidate_execution_count": 0,
        "no_action_reason": None,
    }
    with pytest.raises(ValueError, match="execution_intent"):
        validate_daily_plan_execution_intent(payload)


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        ("account_id", "paper_other"),
        ("data_date", "2026-07-14"),
        ("trade_date", "2026-07-17"),
    ],
)
def test_context_mismatch_is_rejected(field: str, expected: str) -> None:
    payload = _payload([_item()])
    kwargs = {
        "expected_account_id": payload["account_id"],
        "expected_data_date": payload["data_date"],
        "expected_trade_date": payload["trade_date"],
    }
    kwargs[f"expected_{field}"] = expected
    with pytest.raises(ValueError, match=f"{field}_mismatch"):
        validate_daily_plan_execution_intent(copy.deepcopy(payload), **kwargs)


def test_items_must_be_a_list() -> None:
    payload = _payload([])
    payload["items"] = {}
    with pytest.raises(ValueError, match="items_must_be_list"):
        validate_daily_plan_execution_intent(payload)


@pytest.mark.parametrize(
    ("target", "value", "error"),
    [
        ("payload", "paper_daily_plan.v2", "daily_plan_schema_version_invalid"),
        ("intent", "paper_execution_intent.v2", "execution_intent_schema_version_invalid"),
        ("mode", "SKIP", "execution_intent_action_mode_invalid"),
    ],
)
def test_unknown_schema_or_action_mode_is_rejected(target: str, value: str, error: str) -> None:
    payload = _payload([_item()])
    if target == "payload":
        payload["schema_version"] = value
    elif target == "intent":
        payload["execution_intent"]["schema_version"] = value
    else:
        payload["execution_intent"]["action_mode"] = value
    with pytest.raises(ValueError, match=error):
        validate_daily_plan_execution_intent(payload)
