import csv
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_account_snapshot import (
    PAPER_ACCOUNT_SNAPSHOT_COLUMNS,
    build_paper_account_snapshot_row,
    save_paper_account_snapshot,
)
from core.paper_market_valuation import PaperAccountValuation
from core.paper_account_state import build_paper_state_from_trades, create_initial_paper_state
from core.paths import FRONT_TEST_DIR, PAPER_TEST_DIR


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


def _unique_snapshot_path() -> Path:
    return PAPER_TEST_DIR / f"paper_account_snapshot_test_{uuid4().hex}.csv"


def _unique_archive_dir() -> Path:
    return PAPER_TEST_DIR / f"archive_snapshot_test_{uuid4().hex}"


def _read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _cleanup(path: Path, archive_dir: Path) -> None:
    if path.exists():
        path.unlink()
    if archive_dir.exists():
        for child in archive_dir.iterdir():
            child.unlink()
        archive_dir.rmdir()


def test_build_paper_account_snapshot_row_calculates_cost_basis_fields():
    state = build_paper_state_from_trades(
        [
            _make_trade("t1", "CPAY", "BUY", 29, 343.99),
            _make_trade("t2", "GEN", "BUY", 440, 22.68),
            _make_trade("t3", "VRSN", "BUY", 34, 288.21),
        ],
        initial_cash=100000.0,
        currency="USD",
    )
    row = build_paper_account_snapshot_row(
        state,
        "20260509",
        initial_cash=100000.0,
        source_execution_log="outputs/paper_test/paper_execution_log.csv",
        source_current_state="outputs/paper_test/paper_current_state_20260509.json",
        created_at="2026-05-11T12:00:00",
    )
    assert row["cash"] == 70245.95
    assert row["positions_cost_value"] == 29754.05
    assert row["total_equity_cost_basis"] == 100000.0
    assert row["cash_ratio_cost_basis"] == 0.7024595
    assert row["position_count"] == 3
    assert row["symbols"] == "CPAY|GEN|VRSN"
    assert row["applied_trade_count"] == 3
    assert row["valuation_method"] == "cost_basis"
    assert row["market_valuation_status"] == "not_run"
    assert row["realized_pnl"] == 0.0
    assert json.loads(row["realized_pnl_by_symbol"]) == {}


def test_build_paper_account_snapshot_row_empty_positions():
    state = create_initial_paper_state()
    row = build_paper_account_snapshot_row(state, "2026-05-09")
    assert row["positions_cost_value"] == 0.0
    assert row["total_equity_cost_basis"] == 100000.0
    assert row["cash_ratio_cost_basis"] == 1.0
    assert row["position_count"] == 0
    assert row["symbols"] == ""


def test_build_paper_account_snapshot_row_with_market_valuation_success():
    state = build_paper_state_from_trades(
        [
            _make_trade("t1", "CPAY", "BUY", 10, 100.0),
            _make_trade("t2", "CPAY", "SELL", -4, 120.0),
        ],
        initial_cash=100000.0,
        currency="USD",
    )
    valuation = PaperAccountValuation(
        snapshot_date="2026-05-09",
        cash=99480.0,
        positions_cost_value=600.0,
        positions_market_value=720.0,
        total_equity_cost_basis=100080.0,
        total_equity_market_value=100200.0,
        cash_ratio_market_value=99480.0 / 100200.0,
        unrealized_pnl=200.0,
        unrealized_pnl_pct=200.0 / 600.0,
        valuation_method="db_daily_price_close",
        valuation_price_date="2026-05-09",
        valuation_price_dates={"CPAY": "2026-05-09"},
        price_staleness_days={"CPAY": 0},
        positions=[],
    )
    row = build_paper_account_snapshot_row(
        state,
        "2026-05-09",
        market_valuation=valuation,
    )
    assert row["realized_pnl"] == 80.0
    assert json.loads(row["realized_pnl_by_symbol"]) == {"CPAY": 80.0}
    assert row["positions_market_value"] == 720.0
    assert row["total_equity_market_value"] == 100200.0
    assert row["market_valuation_status"] == "success"
    assert row["market_valuation_error"] == ""
    assert row["valuation_method"] == "db_daily_price_close"
    assert row["total_pnl"] == 280.0
    assert row["total_pnl_pct"] == 0.0028
    assert json.loads(row["valuation_price_dates"]) == {"CPAY": "2026-05-09"}
    assert json.loads(row["price_staleness_days"]) == {"CPAY": 0}
    assert row["max_price_staleness_days"] == 0


def test_build_paper_account_snapshot_row_with_market_valuation_failure():
    state = build_paper_state_from_trades(
        [
            _make_trade("t1", "CPAY", "BUY", 10, 100.0),
            _make_trade("t2", "CPAY", "SELL", -4, 120.0),
        ],
        initial_cash=100000.0,
        currency="USD",
    )
    row = build_paper_account_snapshot_row(
        state,
        "2026-05-09",
        market_valuation_error="No daily_price close found for CPAY on or before 2026-05-09",
    )
    assert row["positions_cost_value"] == 600.0
    assert row["realized_pnl"] == 80.0
    assert json.loads(row["realized_pnl_by_symbol"]) == {"CPAY": 80.0}
    assert row["market_valuation_status"] == "failed"
    assert "No daily_price close found" in row["market_valuation_error"]
    assert row["positions_market_value"] == ""
    assert row["total_equity_market_value"] == ""
    assert row["total_pnl"] == ""
    assert row["total_pnl_pct"] == ""
    assert row["valuation_method"] == "db_daily_price_close_failed"


def test_save_paper_account_snapshot_replaces_same_date_and_creates_backup():
    snapshot_path = _unique_snapshot_path()
    archive_dir = _unique_archive_dir()
    try:
        old_row = {column: "" for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS}
        old_row.update(
            {
                "snapshot_date": "2026-05-09",
                "currency": "USD",
                "initial_cash": 100000.0,
                "cash": 90000.0,
                "positions_cost_value": 10000.0,
                "total_equity_cost_basis": 100000.0,
                "cash_ratio_cost_basis": 0.9,
                "position_count": 1,
                "symbols": "OLD",
                "applied_trade_count": 1,
                "valuation_method": "cost_basis",
                "source_execution_log": "old_log.csv",
                "source_current_state": "old_state.json",
                "created_at": "2026-05-10T00:00:00",
            }
        )
        with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
            writer.writeheader()
            writer.writerows([old_row])

        state = build_paper_state_from_trades(
            [_make_trade("t1", "CPAY", "BUY", 29, 343.99)],
            initial_cash=100000.0,
            currency="USD",
        )
        new_row = build_paper_account_snapshot_row(state, "2026-05-09")
        result = save_paper_account_snapshot(
            new_row,
            snapshot_path,
            archive_dir,
            now=datetime(2026, 5, 11, 12, 0, 0),
        )
        assert result["replaced"] is True
        assert result["backup_path"] is not None
        assert result["backup_path"].exists()
        rows = _read_rows(snapshot_path)
        assert len(rows) == 1
        assert rows[0]["snapshot_date"] == "2026-05-09"
        assert rows[0]["symbols"] == "CPAY"
    finally:
        _cleanup(snapshot_path, archive_dir)


def test_build_paper_account_snapshot_row_records_max_price_staleness_days():
    state = build_paper_state_from_trades(
        [
            _make_trade("t1", "CPAY", "BUY", 10, 100.0),
            _make_trade("t2", "GEN", "BUY", 20, 50.0),
        ],
        initial_cash=100000.0,
        currency="USD",
    )
    valuation = PaperAccountValuation(
        snapshot_date="2026-05-09",
        cash=98000.0,
        positions_cost_value=2000.0,
        positions_market_value=2100.0,
        total_equity_cost_basis=100000.0,
        total_equity_market_value=100100.0,
        cash_ratio_market_value=98000.0 / 100100.0,
        unrealized_pnl=100.0,
        unrealized_pnl_pct=0.05,
        valuation_method="db_daily_price_close",
        valuation_price_date="2026-05-07",
        valuation_price_dates={"CPAY": "2026-05-09", "GEN": "2026-05-07"},
        price_staleness_days={"CPAY": 0, "GEN": 2},
        positions=[],
    )
    row = build_paper_account_snapshot_row(
        state,
        "2026-05-09",
        market_valuation=valuation,
    )
    assert row["max_price_staleness_days"] == 2
    assert json.loads(row["price_staleness_days"]) == {"CPAY": 0, "GEN": 2}


def test_save_paper_account_snapshot_keeps_other_dates():
    snapshot_path = _unique_snapshot_path()
    archive_dir = _unique_archive_dir()
    try:
        row_0508 = {column: "" for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS}
        row_0508.update(
            {
                "snapshot_date": "2026-05-08",
                "currency": "USD",
                "initial_cash": 100000.0,
                "cash": 100000.0,
                "positions_cost_value": 0.0,
                "total_equity_cost_basis": 100000.0,
                "cash_ratio_cost_basis": 1.0,
                "position_count": 0,
                "symbols": "",
                "applied_trade_count": 0,
                "valuation_method": "cost_basis",
                "source_execution_log": "",
                "source_current_state": "",
                "created_at": "2026-05-10T00:00:00",
            }
        )
        with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
            writer.writeheader()
            writer.writerows([row_0508])

        state = build_paper_state_from_trades(
            [_make_trade("t1", "CPAY", "BUY", 29, 343.99)],
            initial_cash=100000.0,
            currency="USD",
        )
        new_row = build_paper_account_snapshot_row(state, "2026-05-09")
        result = save_paper_account_snapshot(new_row, snapshot_path, archive_dir)
        assert result["replaced"] is False
        rows = _read_rows(snapshot_path)
        assert [row["snapshot_date"] for row in rows] == ["2026-05-08", "2026-05-09"]
    finally:
        _cleanup(snapshot_path, archive_dir)


def test_save_paper_account_snapshot_rejects_non_paper_path():
    snapshot_path = FRONT_TEST_DIR / f"paper_account_snapshot_test_{uuid4().hex}.csv"
    archive_dir = _unique_archive_dir()
    try:
        state = create_initial_paper_state()
        row = build_paper_account_snapshot_row(state, "2026-05-09")
        with pytest.raises(ValueError):
            save_paper_account_snapshot(row, snapshot_path, archive_dir)
    finally:
        if archive_dir.exists():
            for child in archive_dir.iterdir():
                child.unlink()
            archive_dir.rmdir()
