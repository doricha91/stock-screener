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
    path = root / f"paper_sell_e2e_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _make_trade(
    trade_id: str,
    symbol: str,
    side: str,
    shares: int,
    price: float,
    trade_date: str = "2026-05-10",
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


def _build_state_from_tmp_execution_log(tmp_path: Path, trade_rows: list[dict]):
    log_path = tmp_path / "paper_execution_log.csv"
    _write_execution_log(log_path, trade_rows)
    return build_paper_state_from_trades(_read_execution_log(log_path))


def test_partial_sell_end_to_end(tmp_path):
    state = _build_state_from_tmp_execution_log(
        tmp_path,
        [
            _make_trade("buy1", "CPAY", "BUY", 10, 100.0),
            _make_trade("sell1", "CPAY", "SELL", -4, 120.0),
        ],
    )
    assert state.realized_pnl == 80.0
    assert state.realized_pnl_by_symbol == {"CPAY": 80.0}
    assert state.cash == 99480.0
    assert state.positions["CPAY"].shares == 6
    assert state.positions["CPAY"].avg_price == 100.0

    current_state = paper_account_state_to_current_state_dict(state, "20260510")
    assert current_state["current_symbols"] == ["CPAY"]
    assert current_state["shares"]["CPAY"] == 6
    assert current_state["avg_price"]["CPAY"] == 100.0

    db_path = tmp_path / "daily_price.sqlite"
    _init_daily_price_db(db_path, [("CPAY", "2026-05-10", 120.0)])
    valuation = value_paper_account_state(state, "2026-05-10", db_path)
    snapshot = build_paper_account_snapshot_row(
        state,
        "2026-05-10",
        market_valuation=valuation,
    )
    assert snapshot["realized_pnl"] == 80.0
    assert json.loads(snapshot["realized_pnl_by_symbol"]) == {"CPAY": 80.0}
    assert snapshot["positions_market_value"] == 720.0
    assert snapshot["unrealized_pnl"] == 120.0
    assert snapshot["total_pnl"] == 200.0
    assert snapshot["total_pnl_pct"] == 0.002
    assert snapshot["market_valuation_status"] == "success"


def test_full_sell_end_to_end_removes_position(tmp_path):
    state = _build_state_from_tmp_execution_log(
        tmp_path,
        [
            _make_trade("buy1", "CPAY", "BUY", 10, 100.0),
            _make_trade("sell1", "CPAY", "SELL", -10, 110.0),
        ],
    )
    assert state.realized_pnl == 100.0
    assert state.realized_pnl_by_symbol == {"CPAY": 100.0}
    assert "CPAY" not in state.positions
    assert state.cash == 100100.0

    current_state = paper_account_state_to_current_state_dict(state, "20260510")
    assert current_state["current_symbols"] == []
    assert current_state["shares"] == {}
    assert current_state["avg_price"] == {}

    db_path = tmp_path / "daily_price.sqlite"
    _init_daily_price_db(db_path, [])
    valuation = value_paper_account_state(state, "2026-05-10", db_path)
    snapshot = build_paper_account_snapshot_row(
        state,
        "2026-05-10",
        market_valuation=valuation,
    )
    assert snapshot["realized_pnl"] == 100.0
    assert snapshot["positions_market_value"] == 0.0
    assert snapshot["total_pnl"] == 100.0
    assert snapshot["total_pnl_pct"] == 0.001


def test_loss_sell_end_to_end(tmp_path):
    state = _build_state_from_tmp_execution_log(
        tmp_path,
        [
            _make_trade("buy1", "GEN", "BUY", 10, 100.0),
            _make_trade("sell1", "GEN", "SELL", -5, 80.0),
        ],
    )
    assert state.realized_pnl == -100.0
    assert state.realized_pnl_by_symbol == {"GEN": -100.0}
    assert state.cash == 99400.0
    assert state.positions["GEN"].shares == 5
    assert state.positions["GEN"].avg_price == 100.0

    db_path = tmp_path / "daily_price.sqlite"
    _init_daily_price_db(db_path, [("GEN", "2026-05-10", 80.0)])
    valuation = value_paper_account_state(state, "2026-05-10", db_path)
    snapshot = build_paper_account_snapshot_row(
        state,
        "2026-05-10",
        market_valuation=valuation,
    )
    assert snapshot["realized_pnl"] == -100.0
    assert snapshot["unrealized_pnl"] == -100.0
    assert snapshot["total_pnl"] == -200.0
    assert snapshot["total_pnl_pct"] == -0.002


def test_duplicate_sell_end_to_end_is_ignored(tmp_path):
    state = _build_state_from_tmp_execution_log(
        tmp_path,
        [
            _make_trade("buy1", "CPAY", "BUY", 10, 100.0),
            _make_trade("sell1", "CPAY", "SELL", -4, 120.0),
            _make_trade("sell1", "CPAY", "SELL", -4, 120.0),
        ],
    )
    assert state.realized_pnl == 80.0
    assert state.realized_pnl_by_symbol == {"CPAY": 80.0}
    assert state.cash == 99480.0
    assert state.positions["CPAY"].shares == 6
    assert state.applied_trade_ids == {"buy1", "sell1"}

    db_path = tmp_path / "daily_price.sqlite"
    _init_daily_price_db(db_path, [("CPAY", "2026-05-10", 120.0)])
    valuation = value_paper_account_state(state, "2026-05-10", db_path)
    snapshot = build_paper_account_snapshot_row(
        state,
        "2026-05-10",
        market_valuation=valuation,
    )
    assert snapshot["realized_pnl"] == 80.0
    assert snapshot["total_pnl"] == 200.0
