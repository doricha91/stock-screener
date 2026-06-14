from __future__ import annotations

from core.paper_daily_plan_candidates import (
    CANDIDATE_COUNT_RULE,
    count_daily_plan_execution_candidates,
    extract_daily_plan_execution_candidates,
    is_daily_plan_execution_candidate,
)


def test_current_daily_plan_schema_buy_sell_positive_quantity_counts() -> None:
    plan = {
        "items": [
            {"symbol": "AAPL", "action": "BUY", "quantity": 10},
            {"symbol": "MSFT", "action": " sell ", "quantity": "2"},
            {"symbol": "NVDA", "action": "HOLD", "quantity": 3},
            {"symbol": "TSLA", "action": "BUY", "quantity": 0},
        ]
    }

    assert CANDIDATE_COUNT_RULE == "items.action_in_buy_sell_quantity_positive.v1"
    assert count_daily_plan_execution_candidates(plan) == 2
    assert [item["symbol"] for item in extract_daily_plan_execution_candidates(plan)] == ["AAPL", "MSFT"]


def test_malformed_items_are_not_candidates() -> None:
    assert is_daily_plan_execution_candidate(None) is False
    assert is_daily_plan_execution_candidate({"symbol": "AAPL", "action": "BUY"}) is False
    assert is_daily_plan_execution_candidate({"symbol": "", "action": "BUY", "quantity": 1}) is False
    assert is_daily_plan_execution_candidate({"symbol": "AAPL", "action": "BUY", "quantity": "bad"}) is False
    assert is_daily_plan_execution_candidate({"symbol": "AAPL", "action": "SELL", "quantity": -1}) is False


def test_legacy_execute_pending_side_shape_is_not_official_candidate() -> None:
    plan = {
        "items": [
            {"symbol": "AAPL", "action": "EXECUTE", "status": "PENDING", "side": "BUY", "quantity": 10},
        ]
    }

    assert count_daily_plan_execution_candidates(plan) == 0


def test_20260615_shape_counts_nine_candidates() -> None:
    plan = {
        "items": [
            {"action": "SELL", "symbol": "AMT", "quantity": 51},
            {"action": "BUY", "symbol": "BF-B", "quantity": 353},
            {"action": "SELL", "symbol": "AVB", "quantity": 52},
            {"action": "BUY", "symbol": "PLD", "quantity": 65},
            {"action": "BUY", "symbol": "AMCR", "quantity": 243},
            {"action": "BUY", "symbol": "CCL", "quantity": 120},
            {"action": "BUY", "symbol": "LIN", "quantity": 10},
            {"action": "BUY", "symbol": "LYV", "quantity": 40},
            {"action": "BUY", "symbol": "SW", "quantity": 200},
        ]
    }

    assert count_daily_plan_execution_candidates(plan) == 9
