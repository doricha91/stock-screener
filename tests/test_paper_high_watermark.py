from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.daily_plan_generator import (
    WARNING_HIGHEST_PRICE_MARKET_DATA_UNAVAILABLE,
    diagnose_highest_price_state,
)
from core.paper_account_state import build_paper_state_from_trades
from core.paper_high_watermark import (
    calculate_paper_high_watermarks,
    filter_execution_rows_on_or_before,
)


def trade(
    trade_id: str,
    date: str,
    side: str,
    shares: int,
    price: float,
    symbol: str = "TEST",
) -> dict:
    return {
        "trade_id": trade_id,
        "date": date,
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": price,
        "gross_amount": shares * price,
    }


def market_db(tmp_path: Path, rows: list[tuple[str, str, float | None, float]]) -> Path:
    path = tmp_path / "market.db"
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "CREATE TABLE daily_price "
            "(symbol TEXT NOT NULL, date TEXT NOT NULL, high REAL, close REAL NOT NULL)"
        )
        conn.executemany(
            "INSERT INTO daily_price(symbol, date, high, close) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return path


def calculate(tmp_path: Path, trades: list[dict], prices, as_of: str):
    filtered = filter_execution_rows_on_or_before(trades, as_of)
    state = build_paper_state_from_trades(filtered)
    return calculate_paper_high_watermarks(state, filtered, as_of, market_db(tmp_path, prices))


def test_entry_day_high_is_excluded(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-02", "BUY", 10, 100.0)],
        [("TEST", "2026-07-02", 120.0, 110.0)],
        "2026-07-02",
    )
    assert result.decision_highest["TEST"] == 100.0
    assert result.updated_highest["TEST"] == 100.0


def test_high_is_applied_from_next_trading_day(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-02", "BUY", 10, 100.0)],
        [
            ("TEST", "2026-07-02", 120.0, 110.0),
            ("TEST", "2026-07-03", 125.0, 121.0),
        ],
        "2026-07-03",
    )
    assert result.decision_highest["TEST"] == 100.0
    assert result.updated_highest["TEST"] == 125.0
    assert result.updated_state.positions["TEST"].highest_price == 125.0


def test_intermediate_high_is_retained_after_price_declines(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-01", "BUY", 10, 100.0)],
        [
            ("TEST", "2026-07-02", 130.0, 125.0),
            ("TEST", "2026-07-03", 115.0, 110.0),
        ],
        "2026-07-03",
    )
    assert result.decision_highest["TEST"] == 130.0
    assert result.updated_highest["TEST"] == 130.0
    assert result.max_high_dates["TEST"] == "2026-07-02"


def test_additional_buy_preserves_existing_high_and_allows_same_day_high(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [
            trade("b1", "2026-07-01", "BUY", 10, 100.0),
            trade("b2", "2026-07-03", "BUY", 5, 105.0),
        ],
        [
            ("TEST", "2026-07-02", 130.0, 125.0),
            ("TEST", "2026-07-03", 135.0, 132.0),
        ],
        "2026-07-03",
    )
    assert result.decision_highest["TEST"] == 130.0
    assert result.updated_highest["TEST"] == 135.0
    assert result.updated_state.positions["TEST"].shares == 15


def test_partial_sell_preserves_high(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [
            trade("b1", "2026-07-01", "BUY", 10, 100.0),
            trade("s1", "2026-07-03", "SELL", -4, 120.0),
        ],
        [("TEST", "2026-07-02", 130.0, 125.0)],
        "2026-07-03",
    )
    assert result.decision_highest["TEST"] == 130.0
    assert result.updated_state.positions["TEST"].shares == 6


def test_full_sell_removes_high(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [
            trade("b1", "2026-07-01", "BUY", 10, 100.0),
            trade("s1", "2026-07-03", "SELL", -10, 120.0),
        ],
        [("TEST", "2026-07-02", 130.0, 125.0)],
        "2026-07-03",
    )
    assert result.decision_highest == {}
    assert result.updated_highest == {}
    assert result.updated_state.positions == {}


def test_reentry_resets_prior_lifecycle_high(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [
            trade("b1", "2026-07-01", "BUY", 10, 100.0),
            trade("s1", "2026-07-03", "SELL", -10, 120.0),
            trade("b2", "2026-07-06", "BUY", 8, 90.0),
        ],
        [
            ("TEST", "2026-07-02", 130.0, 125.0),
            ("TEST", "2026-07-06", 110.0, 100.0),
        ],
        "2026-07-06",
    )
    assert result.position_open_dates["TEST"] == "2026-07-06"
    assert result.decision_highest["TEST"] == 90.0
    assert result.updated_highest["TEST"] == 90.0


def test_execution_after_data_date_is_excluded() -> None:
    rows = [
        trade("b1", "2026-07-02", "BUY", 10, 100.0),
        trade("b2", "2026-07-06", "BUY", 5, 200.0),
    ]
    assert [row["trade_id"] for row in filter_execution_rows_on_or_before(rows, "2026-07-02")] == ["b1"]


def test_market_price_after_data_date_is_excluded(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-01", "BUY", 10, 100.0)],
        [
            ("TEST", "2026-07-02", 120.0, 115.0),
            ("TEST", "2026-07-06", 200.0, 190.0),
        ],
        "2026-07-02",
    )
    assert result.updated_highest["TEST"] == 120.0


def test_current_day_high_is_not_used_for_current_day_stop_decision(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-01", "BUY", 10, 100.0)],
        [("TEST", "2026-07-02", 150.0, 90.0)],
        "2026-07-02",
    )
    atr = 10.0
    assert result.decision_highest["TEST"] - (2.5 * atr) == 75.0
    assert 90.0 >= 75.0
    assert result.updated_highest["TEST"] - (2.5 * atr) == 125.0
    assert 90.0 < 125.0


def test_missing_current_high_keeps_existing_high_and_warns(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-01", "BUY", 10, 100.0)],
        [("TEST", "2026-07-02", None, 95.0)],
        "2026-07-02",
    )
    assert result.updated_highest["TEST"] == 100.0
    assert result.metadata["TEST"]["fallback_reason"] == "as_of_high_invalid"
    assert result.warnings


def test_empty_account_and_no_action_day_are_valid(tmp_path: Path) -> None:
    result = calculate(tmp_path, [], [], "2026-07-02")
    assert result.decision_highest == {}
    assert result.updated_highest == {}
    assert result.updated_state.positions == {}


@pytest.mark.parametrize("invalid_high", [None, 0.0])
def test_invalid_as_of_high_keeps_prior_high_and_records_partial_observation(
    tmp_path: Path,
    invalid_high: float | None,
) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-01", "BUY", 10, 100.0)],
        [
            ("TEST", "2026-07-02", 120.0, 115.0),
            ("TEST", "2026-07-03", invalid_high, 130.0),
        ],
        "2026-07-03",
    )

    assert result.decision_highest["TEST"] == 120.0
    assert result.updated_highest["TEST"] == 120.0
    assert result.metadata["TEST"]["source"] == "market_data_partial"
    assert result.metadata["TEST"]["observed_through"] == "2026-07-02"
    assert result.metadata["TEST"]["requested_through"] == "2026-07-03"
    assert result.metadata["TEST"]["fallback_reason"] == "as_of_high_invalid"
    assert result.warnings == [{"symbol": "TEST", "reason": "as_of_high_invalid"}]


def test_missing_as_of_row_keeps_prior_high_and_does_not_use_future_row(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-01", "BUY", 10, 100.0)],
        [
            ("TEST", "2026-07-02", 120.0, 115.0),
            ("TEST", "2026-07-06", 200.0, 190.0),
        ],
        "2026-07-03",
    )

    assert result.updated_highest["TEST"] == 120.0
    assert result.metadata["TEST"]["observed_through"] == "2026-07-02"
    assert result.metadata["TEST"]["requested_through"] == "2026-07-03"
    assert result.metadata["TEST"]["fallback_reason"] == "as_of_market_row_missing"
    assert result.max_high_dates["TEST"] == "2026-07-02"


def test_valid_as_of_high_records_complete_observation(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-01", "BUY", 10, 100.0)],
        [
            ("TEST", "2026-07-02", 120.0, 115.0),
            ("TEST", "2026-07-03", 125.0, 121.0),
        ],
        "2026-07-03",
    )

    assert result.updated_highest["TEST"] == 125.0
    assert result.metadata["TEST"]["observed_through"] == "2026-07-03"
    assert "requested_through" not in result.metadata["TEST"]
    assert "fallback_reason" not in result.metadata["TEST"]


def test_missing_as_of_row_without_any_prior_high_preserves_trade_high(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-01", "BUY", 10, 100.0)],
        [],
        "2026-07-03",
    )

    assert result.updated_highest["TEST"] == 100.0
    assert result.metadata["TEST"]["observed_through"] is None
    assert result.metadata["TEST"]["fallback_reason"] == "as_of_market_row_missing"


def test_daily_plan_warning_exposes_as_of_high_fallback_reason(tmp_path: Path) -> None:
    result = calculate(
        tmp_path,
        [trade("b1", "2026-07-01", "BUY", 10, 100.0)],
        [
            ("TEST", "2026-07-02", 120.0, 115.0),
            ("TEST", "2026-07-03", None, 130.0),
        ],
        "2026-07-03",
    )
    state = result.decision_state
    from core.paper_current_state_serializer import paper_account_state_to_current_state_dict
    from core.target_portfolio_state import CurrentPortfolioState

    payload = paper_account_state_to_current_state_dict(state, "2026-07-03")
    current_state = CurrentPortfolioState(**{
        key: payload[key]
        for key in CurrentPortfolioState.__dataclass_fields__
        if key in payload
    })
    _, _, warnings, _ = diagnose_highest_price_state(
        "TEST", "2026-07-03", current_state, close=130.0, high=None
    )

    warning = next(
        item
        for item in warnings
        if item["reason"] == WARNING_HIGHEST_PRICE_MARKET_DATA_UNAVAILABLE
    )
    assert warning["fallback_reason"] == "as_of_high_invalid"


@pytest.mark.parametrize("db_kind", ["missing_file", "missing_table"])
def test_market_db_errors_are_converted_to_domain_value_error(
    tmp_path: Path,
    db_kind: str,
) -> None:
    db_path = tmp_path / "broken.db"
    if db_kind == "missing_table":
        sqlite3.connect(db_path).close()
    rows = [trade("b1", "2026-07-01", "BUY", 10, 100.0)]
    state = build_paper_state_from_trades(rows)

    with pytest.raises(ValueError, match="paper_high_watermark_market_db_error"):
        calculate_paper_high_watermarks(state, rows, "2026-07-02", db_path)
