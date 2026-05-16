import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_account_state import build_paper_state_from_trades, create_initial_paper_state
from core.paper_market_valuation import (
    get_latest_close_on_or_before,
    value_paper_account_state,
)


def _make_trade(
    trade_id: str,
    symbol: str,
    side: str,
    shares: int,
    price: float,
) -> dict:
    return {
        "trade_id": trade_id,
        "date": "2026-05-09",
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": price,
        "gross_amount": shares * price,
    }


def _unique_db_path() -> Path:
    return Path("tests") / f"paper_market_valuation_{uuid4().hex}.tmp"


def _init_daily_price_db(db_path: Path, rows: list[tuple[str, str, float]]) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            """
            CREATE TABLE daily_price (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                date DATE,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                adj_close REAL,
                volume INTEGER
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO daily_price(symbol, date, open, high, low, close, adj_close, volume)
            VALUES (?, ?, 0, 0, 0, ?, ?, 0)
            """,
            [(symbol, date, close, close) for symbol, date, close in rows],
        )
        conn.commit()
    finally:
        conn.close()


def test_get_latest_close_on_or_before_uses_same_day_close():
    db_path = _unique_db_path()
    try:
        _init_daily_price_db(db_path, [("AAPL", "2026-05-09", 123.45)])
        conn = sqlite3.connect(str(db_path))
        try:
            close_price, price_date = get_latest_close_on_or_before(conn, "AAPL", "2026-05-09")
        finally:
            conn.close()
        assert close_price == 123.45
        assert price_date == "2026-05-09"
    finally:
        if db_path.exists():
            db_path.unlink()


def test_get_latest_close_on_or_before_uses_previous_available_close():
    db_path = _unique_db_path()
    try:
        _init_daily_price_db(db_path, [("AAPL", "2026-05-08", 120.0)])
        conn = sqlite3.connect(str(db_path))
        try:
            close_price, price_date = get_latest_close_on_or_before(conn, "AAPL", "2026-05-09")
        finally:
            conn.close()
        assert close_price == 120.0
        assert price_date == "2026-05-08"
    finally:
        if db_path.exists():
            db_path.unlink()


def test_value_paper_account_state_records_staleness_days():
    db_path = _unique_db_path()
    try:
        _init_daily_price_db(db_path, [("AAPL", "2026-05-07", 110.0)])
        state = build_paper_state_from_trades(
            [_make_trade("t1", "AAPL", "BUY", 10, 100.0)],
            initial_cash=100000.0,
            currency="USD",
        )
        valuation = value_paper_account_state(state, "2026-05-09", db_path)
        assert valuation.valuation_price_dates["AAPL"] == "2026-05-07"
        assert valuation.price_staleness_days["AAPL"] == 2
        assert valuation.valuation_price_date == "2026-05-07"
    finally:
        if db_path.exists():
            db_path.unlink()


def test_value_paper_account_state_raises_when_price_missing():
    db_path = _unique_db_path()
    try:
        _init_daily_price_db(db_path, [])
        state = build_paper_state_from_trades(
            [_make_trade("t1", "AAPL", "BUY", 10, 100.0)],
            initial_cash=100000.0,
            currency="USD",
        )
        with pytest.raises(ValueError):
            value_paper_account_state(state, "2026-05-09", db_path)
    finally:
        if db_path.exists():
            db_path.unlink()


def test_value_paper_account_state_computes_account_level_market_values():
    db_path = _unique_db_path()
    try:
        _init_daily_price_db(
            db_path,
            [
                ("CPAY", "2026-05-09", 350.0),
                ("GEN", "2026-05-09", 20.0),
            ],
        )
        state = build_paper_state_from_trades(
            [
                _make_trade("t1", "CPAY", "BUY", 10, 300.0),
                _make_trade("t2", "GEN", "BUY", 5, 10.0),
            ],
            initial_cash=100000.0,
            currency="USD",
        )
        valuation = value_paper_account_state(state, "2026-05-09", db_path)
        assert valuation.positions_cost_value == 3050.0
        assert valuation.positions_market_value == 3600.0
        assert valuation.total_equity_cost_basis == 100000.0
        assert valuation.total_equity_market_value == 100550.0
        assert valuation.cash_ratio_market_value == 96950.0 / 100550.0
        assert valuation.unrealized_pnl == 550.0
        assert valuation.unrealized_pnl_pct == 550.0 / 3050.0
        assert valuation.valuation_method == "db_daily_price_close"
    finally:
        if db_path.exists():
            db_path.unlink()


def test_value_paper_account_state_empty_positions():
    db_path = _unique_db_path()
    try:
        _init_daily_price_db(db_path, [])
        state = create_initial_paper_state()
        valuation = value_paper_account_state(state, "2026-05-09", db_path)
        assert valuation.positions_market_value == 0.0
        assert valuation.total_equity_market_value == 100000.0
        assert valuation.unrealized_pnl == 0.0
        assert valuation.unrealized_pnl_pct is None
        assert valuation.positions == []
        assert valuation.valuation_price_dates == {}
    finally:
        if db_path.exists():
            db_path.unlink()
