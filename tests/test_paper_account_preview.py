import csv
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paths import PAPER_TEST_DIR
from scripts.run_paper_eod_update import (
    build_paper_account_preview_from_log,
    load_paper_execution_rows,
)


def _unique_log_path() -> Path:
    return PAPER_TEST_DIR / f"paper_execution_log_preview_test_{uuid4().hex}.csv"


def _write_rows(log_path: Path, rows: list[dict]) -> None:
    with log_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _make_row(
    trade_id: str,
    symbol: str,
    side: str,
    shares: int,
    price: float,
) -> dict:
    return {
        "trade_id": trade_id,
        "date": "2026-05-07",
        "regime": "BULL",
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": price,
        "gross_amount": shares * price,
        "source": "journal_actual_fill",
        "status": "READY_FOR_PAPER_TRADE",
        "reason": "PAPER_FILLED",
        "notes": "",
        "rec_shares": abs(shares),
        "rec_price": price,
        "created_at": "2026-05-09T00:00:00",
    }


def test_build_paper_account_preview_from_single_buy_log():
    log_path = _unique_log_path()
    try:
        _write_rows(log_path, [_make_row("t1", "AAPL", "BUY", 10, 100.0)])
        state = build_paper_account_preview_from_log(log_path)
        assert state.cash == 99000.0
        assert state.positions["AAPL"].shares == 10
        assert state.positions["AAPL"].avg_price == 100.0
    finally:
        if log_path.exists():
            log_path.unlink()


def test_build_paper_account_preview_from_two_buys_updates_average_price():
    log_path = _unique_log_path()
    try:
        _write_rows(
            log_path,
            [
                _make_row("t1", "AAPL", "BUY", 10, 100.0),
                _make_row("t2", "AAPL", "BUY", 10, 200.0),
            ],
        )
        state = build_paper_account_preview_from_log(log_path)
        assert state.positions["AAPL"].shares == 20
        assert state.positions["AAPL"].avg_price == 150.0
    finally:
        if log_path.exists():
            log_path.unlink()


def test_build_paper_account_preview_applies_sell_trade():
    log_path = _unique_log_path()
    try:
        _write_rows(
            log_path,
            [
                _make_row("t1", "AAPL", "BUY", 20, 150.0),
                _make_row("t2", "AAPL", "SELL", -5, 300.0),
            ],
        )
        state = build_paper_account_preview_from_log(log_path)
        assert state.cash == 98500.0
        assert state.positions["AAPL"].shares == 15
    finally:
        if log_path.exists():
            log_path.unlink()


def test_load_missing_paper_execution_log_returns_empty_rows_and_initial_state():
    log_path = _unique_log_path()
    rows = load_paper_execution_rows(log_path)
    state = build_paper_account_preview_from_log(log_path)
    assert rows == []
    assert state.cash == 100000.0
    assert state.positions == {}
    assert state.applied_trade_ids == set()


def test_invalid_paper_execution_log_raises_value_error():
    log_path = _unique_log_path()
    try:
        _write_rows(log_path, [_make_row("t1", "AAPL", "BUY", 2000, 100.0)])
        with pytest.raises(ValueError):
            build_paper_account_preview_from_log(log_path)
    finally:
        if log_path.exists():
            log_path.unlink()
