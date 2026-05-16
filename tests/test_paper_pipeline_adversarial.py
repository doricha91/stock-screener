import csv
import json
import shutil
import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_account_snapshot import build_paper_account_snapshot_row
from core.paper_account_state import build_paper_state_from_trades
from core.paper_current_state_serializer import paper_account_state_to_current_state_dict
from core.paper_market_valuation import value_paper_account_state


EXECUTION_LOG_COLUMNS = [
    "trade_id",
    "date",
    "regime",
    "symbol",
    "side",
    "shares",
    "price",
    "gross_amount",
    "source",
    "status",
    "reason",
    "notes",
    "rec_shares",
    "rec_price",
    "created_at",
]


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_pipeline_adversarial_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _make_trade(
    trade_id: str,
    trade_date: str,
    symbol: str,
    side: str,
    shares: int,
    price: float,
) -> dict:
    return {
        "trade_id": trade_id,
        "date": trade_date,
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
        "created_at": f"{trade_date}T20:00:00",
    }


def _write_execution_log(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXECUTION_LOG_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_execution_log(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _build_state_from_log(tmp_path: Path, rows: list[dict]):
    log_path = tmp_path / "paper_execution_log.csv"
    _write_execution_log(log_path, rows)
    return build_paper_state_from_trades(_read_execution_log(log_path))


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


def test_multiday_buy_partial_sell_rebuy_full_sell_pipeline(tmp_path):
    state = _build_state_from_log(
        tmp_path,
        [
            _make_trade("t1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("t2", "2026-05-02", "CPAY", "SELL", -4, 120.0),
            _make_trade("t3", "2026-05-03", "CPAY", "BUY", 6, 90.0),
            _make_trade("t4", "2026-05-04", "CPAY", "SELL", -12, 110.0),
        ],
    )

    # Partial sell then rebuy path implies:
    # after t2: realized +80, remaining 6 @ 100
    # after t3: 12 shares @ 95
    # after t4: realized +(110-95)*12 = 180, cumulative 260
    assert state.realized_pnl == 260.0
    assert state.realized_pnl_by_symbol == {"CPAY": 260.0}
    assert state.cash == 100260.0
    assert "CPAY" not in state.positions

    current_state = paper_account_state_to_current_state_dict(state, "20260504")
    assert current_state["current_symbols"] == []
    assert current_state["shares"] == {}
    assert current_state["avg_price"] == {}
    assert current_state["absolute_cash"] == 100260.0

    db_path = tmp_path / "daily_price.sqlite"
    _init_daily_price_db(db_path, [])
    valuation = value_paper_account_state(state, "2026-05-04", db_path)
    snapshot = build_paper_account_snapshot_row(state, "2026-05-04", market_valuation=valuation)
    assert snapshot["realized_pnl"] == 260.0
    assert json.loads(snapshot["realized_pnl_by_symbol"]) == {"CPAY": 260.0}
    assert snapshot["positions_cost_value"] == 0.0
    assert snapshot["positions_market_value"] == 0.0
    assert snapshot["total_pnl"] == 260.0
    assert snapshot["total_pnl_pct"] == 0.0026


def test_duplicate_buy_and_sell_are_ignored(tmp_path):
    state = _build_state_from_log(
        tmp_path,
        [
            _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -4, 120.0),
            _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -4, 120.0),
        ],
    )
    assert state.cash == 99480.0
    assert state.realized_pnl == 80.0
    assert state.realized_pnl_by_symbol == {"CPAY": 80.0}
    assert state.positions["CPAY"].shares == 6
    assert state.positions["CPAY"].avg_price == 100.0
    assert state.applied_trade_ids == {"buy1", "sell1"}


def test_valuation_failure_isolated_from_cost_basis_snapshot(tmp_path):
    state = _build_state_from_log(
        tmp_path,
        [
            _make_trade("t1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("t2", "2026-05-02", "CPAY", "SELL", -4, 120.0),
            _make_trade("t3", "2026-05-03", "GEN", "BUY", 5, 50.0),
        ],
    )
    assert state.realized_pnl == 80.0
    assert state.realized_pnl_by_symbol == {"CPAY": 80.0}

    db_path = tmp_path / "daily_price.sqlite"
    _init_daily_price_db(
        db_path,
        [
            ("CPAY", "2026-05-04", 120.0),
            # GEN intentionally missing
        ],
    )
    with pytest.raises(ValueError) as excinfo:
        value_paper_account_state(state, "2026-05-04", db_path)
    assert "GEN" in str(excinfo.value)

    snapshot = build_paper_account_snapshot_row(
        state,
        "2026-05-04",
        market_valuation_error=str(excinfo.value),
    )
    assert snapshot["market_valuation_status"] == "failed"
    assert "GEN" in snapshot["market_valuation_error"]
    assert snapshot["positions_cost_value"] == 850.0
    assert snapshot["realized_pnl"] == 80.0
    assert json.loads(snapshot["realized_pnl_by_symbol"]) == {"CPAY": 80.0}
    assert snapshot["total_pnl"] == ""
    assert snapshot["total_pnl_pct"] == ""
    assert snapshot["positions_market_value"] == ""


def test_stale_price_and_snapshot_invariants(tmp_path):
    state = _build_state_from_log(
        tmp_path,
        [
            _make_trade("t1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("t2", "2026-05-02", "CPAY", "SELL", -4, 120.0),
            _make_trade("t3", "2026-05-03", "GEN", "BUY", 5, 50.0),
        ],
    )
    current_state = paper_account_state_to_current_state_dict(state, "20260504")
    assert current_state["shares"] == {"CPAY": 6, "GEN": 5}
    assert current_state["avg_price"] == {"CPAY": 100.0, "GEN": 50.0}
    assert current_state["absolute_cash"] == 99230.0

    db_path = tmp_path / "daily_price.sqlite"
    _init_daily_price_db(
        db_path,
        [
            ("CPAY", "2026-05-03", 121.0),
            ("GEN", "2026-05-02", 55.0),
        ],
    )
    valuation = value_paper_account_state(state, "2026-05-04", db_path)
    snapshot = build_paper_account_snapshot_row(state, "2026-05-04", market_valuation=valuation)

    assert valuation.valuation_price_dates == {"CPAY": "2026-05-03", "GEN": "2026-05-02"}
    assert valuation.price_staleness_days == {"CPAY": 1, "GEN": 2}
    assert snapshot["valuation_price_date"] == "2026-05-02"
    assert json.loads(snapshot["valuation_price_dates"]) == {"CPAY": "2026-05-03", "GEN": "2026-05-02"}
    assert json.loads(snapshot["price_staleness_days"]) == {"CPAY": 1, "GEN": 2}
    assert snapshot["max_price_staleness_days"] == 2

    positions_cost_value = (6 * 100.0) + (5 * 50.0)
    positions_market_value = (6 * 121.0) + (5 * 55.0)
    total_equity_cost_basis = 99230.0 + positions_cost_value
    total_equity_market_value = 99230.0 + positions_market_value
    unrealized_pnl = positions_market_value - positions_cost_value
    total_pnl = 80.0 + unrealized_pnl

    assert snapshot["positions_cost_value"] == positions_cost_value
    assert snapshot["total_equity_cost_basis"] == total_equity_cost_basis
    assert snapshot["cash_ratio_cost_basis"] == 99230.0 / total_equity_cost_basis
    assert snapshot["positions_market_value"] == positions_market_value
    assert snapshot["total_equity_market_value"] == total_equity_market_value
    assert snapshot["unrealized_pnl"] == unrealized_pnl
    assert snapshot["realized_pnl"] == 80.0
    assert snapshot["total_pnl"] == total_pnl
    assert snapshot["total_pnl_pct"] == total_pnl / 100000.0
