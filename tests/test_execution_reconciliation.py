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
    validate_reconciliation_preview_for_commit,
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


def _pass_preview() -> dict[str, object]:
    return {
        "schema_version": "execution_reconciliation_preview.v1",
        "runner_result": "PASS",
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "planned_count": 2,
        "actual_count": 2,
        "matched_count": 2,
        "deviated_count": 0,
        "missing_count": 0,
        "extra_count": 0,
        "warning_count": 0,
        "needs_review_count": 0,
        "blocked_count": 0,
        "rows": [],
    }


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


def test_commit_gate_accepts_pass_artifact() -> None:
    result = validate_reconciliation_preview_for_commit(
        _pass_preview(),
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["ok"] is True


@pytest.mark.parametrize("runner_result", ["WARNING", "NEEDS_REVIEW", "BLOCKED"])
def test_commit_gate_blocks_non_pass_runner_result(runner_result: str) -> None:
    preview = _pass_preview()
    preview["runner_result"] = runner_result

    result = validate_reconciliation_preview_for_commit(
        preview,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["ok"] is False
    assert result["reason_code"] == "reconciliation_not_pass"


def test_commit_gate_blocks_schema_mismatch() -> None:
    preview = _pass_preview()
    preview["schema_version"] = "other.v1"

    result = validate_reconciliation_preview_for_commit(
        preview,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["ok"] is False
    assert result["reason_code"] == "invalid_reconciliation_schema"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("account_id", "paper_other"),
        ("data_date", "2026-06-29"),
        ("trade_date", "2026-07-02"),
    ],
)
def test_commit_gate_blocks_context_mismatch(field: str, value: str) -> None:
    preview = _pass_preview()
    preview[field] = value

    result = validate_reconciliation_preview_for_commit(
        preview,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["ok"] is False
    assert result["reason_code"] == "reconciliation_context_mismatch"


@pytest.mark.parametrize(
    ("field", "reason_code"),
    [
        ("warning_count", "reconciliation_warning_nonzero"),
        ("needs_review_count", "reconciliation_needs_review_nonzero"),
        ("blocked_count", "reconciliation_blocked_count_nonzero"),
        ("missing_count", "reconciliation_missing_count_nonzero"),
        ("extra_count", "reconciliation_extra_count_nonzero"),
    ],
)
def test_commit_gate_blocks_nonzero_counts(field: str, reason_code: str) -> None:
    preview = _pass_preview()
    preview[field] = 1

    result = validate_reconciliation_preview_for_commit(
        preview,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["ok"] is False
    assert result["reason_code"] == reason_code


def test_commit_gate_blocks_count_mismatch() -> None:
    preview = _pass_preview()
    preview["actual_count"] = 1

    result = validate_reconciliation_preview_for_commit(
        preview,
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
    )

    assert result["ok"] is False
    assert result["reason_code"] == "reconciliation_count_mismatch"
