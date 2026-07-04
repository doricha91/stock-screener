from __future__ import annotations

import pytest

from core.execution_reconciliation import (
    BLOCKED,
    DEVIATED,
    EXTRA,
    IDENTITY,
    MATCHED,
    MISSING,
    NEEDS_REVIEW,
    PASS,
    PRICE,
    PRICE_AND_QUANTITY,
    QUANTITY,
    WARNING,
    build_manual_execution_key,
    classify_reconciliation,
    compute_execution_deltas,
    normalize_execution_row,
    normalize_plan_items,
    reconcile_plan_and_executions,
)
from core.notion_account_keys import build_daily_plan_external_key


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-06-30"
TRADE_DATE = "2026-07-01"


def _plan_items() -> list[dict[str, object]]:
    return [
        {"symbol": "CCI", "action": "SELL", "quantity": 84, "price": 100.0, "reason": "EXIT"},
        {"symbol": "TDY", "action": "BUY", "quantity": 9, "price": 200.0, "reason": "ENTRY"},
    ]


def _execution(
    symbol: str,
    side: str,
    sequence: int,
    *,
    quantity: object,
    actual_price: object,
    account_id: str = ACCOUNT_ID,
    execution_date: str = TRADE_DATE,
    linked_daily_plan_key: str | None = None,
    import_status: str = "NOT_IMPORTED",
) -> dict[str, object]:
    return {
        "page_id": f"page-{symbol}",
        "external_key": build_manual_execution_key(account_id, execution_date, symbol, side, sequence),
        "account_id": account_id,
        "execution_date": execution_date,
        "linked_daily_plan_key": linked_daily_plan_key or build_daily_plan_external_key(account_id, execution_date),
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "actual_price": actual_price,
        "status": "READY",
        "import_status": import_status,
        "commission": 0,
    }


def _reconcile(executions: list[dict[str, object]]) -> dict[str, object]:
    return reconcile_plan_and_executions(
        _plan_items(),
        executions,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        daily_plan_path="daily_action_plan_20260701.json",
    )


def test_all_matched_returns_pass() -> None:
    result = _reconcile(
        [
            _execution("CCI", "SELL", 1, quantity=84, actual_price=100.0),
            _execution("TDY", "BUY", 1, quantity=9, actual_price=200.0),
        ]
    )

    assert result["runner_result"] == PASS
    assert result["matched_count"] == 2
    assert result["blocked_count"] == 0


def test_price_only_deviation_returns_warning() -> None:
    result = _reconcile(
        [
            _execution("CCI", "SELL", 1, quantity=84, actual_price=105.0),
            _execution("TDY", "BUY", 1, quantity=9, actual_price=200.0),
        ]
    )

    row = result["rows"][0]
    assert result["runner_result"] == WARNING
    assert row["reconciliation_status"] == DEVIATED
    assert row["deviation_type"] == PRICE
    assert row["severity"] == WARNING


def test_quantity_deviation_returns_needs_review() -> None:
    result = _reconcile(
        [
            _execution("CCI", "SELL", 1, quantity=80, actual_price=100.0),
            _execution("TDY", "BUY", 1, quantity=9, actual_price=200.0),
        ]
    )

    assert result["runner_result"] == NEEDS_REVIEW
    assert result["rows"][0]["deviation_type"] == QUANTITY


def test_price_and_quantity_deviation_returns_needs_review() -> None:
    result = _reconcile(
        [
            _execution("CCI", "SELL", 1, quantity=80, actual_price=105.0),
            _execution("TDY", "BUY", 1, quantity=9, actual_price=200.0),
        ]
    )

    assert result["runner_result"] == NEEDS_REVIEW
    assert result["rows"][0]["deviation_type"] == PRICE_AND_QUANTITY


def test_missing_planned_execution_blocks() -> None:
    result = _reconcile([_execution("CCI", "SELL", 1, quantity=84, actual_price=100.0)])

    assert result["runner_result"] == BLOCKED
    assert result["missing_count"] == 1
    assert any(row["reconciliation_status"] == MISSING for row in result["rows"])


def test_extra_execution_blocks() -> None:
    result = _reconcile(
        [
            _execution("CCI", "SELL", 1, quantity=84, actual_price=100.0),
            _execution("TDY", "BUY", 1, quantity=9, actual_price=200.0),
            _execution("PLD", "SELL", 1, quantity=52, actual_price=90.0),
        ]
    )

    assert result["runner_result"] == BLOCKED
    assert result["extra_count"] == 1
    assert any(row["reconciliation_status"] == EXTRA for row in result["rows"])


def test_identity_mismatch_blocks() -> None:
    plan_row = normalize_plan_items([_plan_items()[0]], ACCOUNT_ID, TRADE_DATE)[0]
    actual = normalize_execution_row(
        _execution("CCI", "SELL", 1, quantity=84, actual_price=100.0, account_id="other_paper"),
        ACCOUNT_ID,
        TRADE_DATE,
    )
    deltas = compute_execution_deltas(plan_row, actual)

    row = classify_reconciliation(plan_row, actual, deltas)

    assert row["deviation_type"] == IDENTITY
    assert row["severity"] == BLOCKED


def test_import_status_conflict_blocks() -> None:
    result = _reconcile(
        [
            _execution("CCI", "SELL", 1, quantity=84, actual_price=100.0, import_status="IMPORTED"),
            _execution("TDY", "BUY", 1, quantity=9, actual_price=200.0),
        ]
    )

    assert result["runner_result"] == BLOCKED
    assert result["rows"][0]["deviation_type"] == IDENTITY


def test_notional_delta_pct_is_computed() -> None:
    result = _reconcile(
        [
            _execution("CCI", "SELL", 1, quantity=84, actual_price=105.0),
            _execution("TDY", "BUY", 1, quantity=9, actual_price=200.0),
        ]
    )

    assert result["rows"][0]["planned_notional"] == 8400
    assert result["rows"][0]["actual_notional"] == 8820
    assert result["rows"][0]["notional_delta_pct"] == 5


@pytest.mark.parametrize(
    ("quantity", "actual_price"),
    [(None, 100.0), (84, None), (0, 100.0), (84, 0)],
)
def test_none_or_zero_values_do_not_crash(quantity: object, actual_price: object) -> None:
    result = _reconcile(
        [
            _execution("CCI", "SELL", 1, quantity=quantity, actual_price=actual_price),
            _execution("TDY", "BUY", 1, quantity=9, actual_price=200.0),
        ]
    )

    assert result["runner_result"] in {BLOCKED, NEEDS_REVIEW, WARNING, PASS}
