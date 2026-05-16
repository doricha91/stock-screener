import csv
import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_account_state import build_paper_state_from_trades
from core.paper_market_valuation import PaperAccountValuation, PaperPositionValuation
from core.paper_position_snapshot import (
    PAPER_POSITION_SNAPSHOT_COLUMNS,
    build_paper_position_snapshot_rows,
    save_paper_position_snapshot,
)
from core.paths import FRONT_TEST_DIR, PAPER_TEST_DIR


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_position_snapshot_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _trade(trade_id: str, symbol: str, side: str, shares: int, price: float) -> dict:
    return {
        "trade_id": trade_id,
        "date": "2026-05-09",
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": price,
        "gross_amount": shares * price,
    }


def _valuation_for_state() -> PaperAccountValuation:
    return PaperAccountValuation(
        snapshot_date="2026-05-09",
        cash=99230.0,
        positions_cost_value=850.0,
        positions_market_value=1001.0,
        total_equity_cost_basis=100080.0,
        total_equity_market_value=100231.0,
        cash_ratio_market_value=99230.0 / 100231.0,
        unrealized_pnl=151.0,
        unrealized_pnl_pct=151.0 / 850.0,
        valuation_method="db_daily_price_close",
        valuation_price_date="2026-05-08",
        valuation_price_dates={"CPAY": "2026-05-08", "GEN": "2026-05-07"},
        price_staleness_days={"CPAY": 1, "GEN": 2},
        positions=[
            PaperPositionValuation(
                symbol="CPAY",
                shares=6,
                avg_price=100.0,
                close_price=121.0,
                market_value=726.0,
                cost_value=600.0,
                unrealized_pnl=126.0,
                unrealized_pnl_pct=0.21,
                valuation_price_date="2026-05-08",
                price_staleness_days=1,
            ),
            PaperPositionValuation(
                symbol="GEN",
                shares=5,
                avg_price=50.0,
                close_price=55.0,
                market_value=275.0,
                cost_value=250.0,
                unrealized_pnl=25.0,
                unrealized_pnl_pct=0.1,
                valuation_price_date="2026-05-07",
                price_staleness_days=2,
            ),
        ],
    )


def _unique_snapshot_path() -> Path:
    return PAPER_TEST_DIR / f"paper_position_snapshot_test_{uuid4().hex}.csv"


def _unique_archive_dir() -> Path:
    return PAPER_TEST_DIR / f"archive_position_snapshot_test_{uuid4().hex}"


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


def test_build_paper_position_snapshot_rows_calculates_fields():
    state = build_paper_state_from_trades(
        [
            _trade("t1", "CPAY", "BUY", 10, 100.0),
            _trade("t2", "CPAY", "SELL", -4, 120.0),
            _trade("t3", "GEN", "BUY", 5, 50.0),
        ]
    )
    rows = build_paper_position_snapshot_rows(state, _valuation_for_state(), "2026-05-09")
    assert len(rows) == 2
    cpay = next(row for row in rows if row["symbol"] == "CPAY")
    assert cpay["shares"] == 6
    assert cpay["avg_price"] == 100.0
    assert cpay["cost_value"] == 600.0
    assert cpay["close_price"] == 121.0
    assert cpay["market_value"] == 726.0
    assert cpay["unrealized_pnl"] == 126.0
    assert cpay["realized_pnl"] == 80.0
    assert cpay["total_pnl"] == 206.0
    assert cpay["total_pnl_pct_on_current_cost"] == 206.0 / 600.0
    assert cpay["position_status"] == "OPEN"


def test_build_paper_position_snapshot_rows_reflects_realized_and_total_pnl():
    state = build_paper_state_from_trades(
        [
            _trade("t1", "CPAY", "BUY", 10, 100.0),
            _trade("t2", "CPAY", "SELL", -4, 120.0),
            _trade("t3", "GEN", "BUY", 5, 50.0),
        ]
    )
    rows = build_paper_position_snapshot_rows(state, _valuation_for_state(), "2026-05-09")
    gen = next(row for row in rows if row["symbol"] == "GEN")
    assert gen["realized_pnl"] == 0.0
    assert gen["unrealized_pnl"] == 25.0
    assert gen["total_pnl"] == 25.0
    assert gen["total_pnl_pct_on_current_cost"] == 0.1


def test_save_paper_position_snapshot_replaces_same_date_and_creates_backup():
    snapshot_path = _unique_snapshot_path()
    archive_dir = _unique_archive_dir()
    try:
        old_row = {column: "" for column in PAPER_POSITION_SNAPSHOT_COLUMNS}
        old_row.update(
            {
                "snapshot_date": "2026-05-09",
                "symbol": "OLD",
                "shares": "1",
                "position_status": "OPEN",
            }
        )
        with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PAPER_POSITION_SNAPSHOT_COLUMNS)
            writer.writeheader()
            writer.writerows([old_row])

        state = build_paper_state_from_trades(
            [
                _trade("t1", "CPAY", "BUY", 10, 100.0),
                _trade("t2", "CPAY", "SELL", -4, 120.0),
                _trade("t3", "GEN", "BUY", 5, 50.0),
            ]
        )
        rows = build_paper_position_snapshot_rows(state, _valuation_for_state(), "2026-05-09")
        result = save_paper_position_snapshot(
            rows,
            "2026-05-09",
            snapshot_path,
            archive_dir,
            now=datetime(2026, 5, 12, 8, 0, 0),
        )
        assert result["replaced"] is True
        assert result["backup_path"] is not None
        assert result["backup_path"].exists()
        saved_rows = _read_rows(snapshot_path)
        assert len(saved_rows) == 2
        assert {row["symbol"] for row in saved_rows} == {"CPAY", "GEN"}
    finally:
        _cleanup(snapshot_path, archive_dir)


def test_save_paper_position_snapshot_keeps_other_dates():
    snapshot_path = _unique_snapshot_path()
    archive_dir = _unique_archive_dir()
    try:
        row_0508 = {column: "" for column in PAPER_POSITION_SNAPSHOT_COLUMNS}
        row_0508.update(
            {
                "snapshot_date": "2026-05-08",
                "symbol": "AAPL",
                "shares": "10",
                "position_status": "OPEN",
            }
        )
        with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=PAPER_POSITION_SNAPSHOT_COLUMNS)
            writer.writeheader()
            writer.writerows([row_0508])

        state = build_paper_state_from_trades(
            [
                _trade("t1", "CPAY", "BUY", 10, 100.0),
                _trade("t2", "CPAY", "SELL", -4, 120.0),
                _trade("t3", "GEN", "BUY", 5, 50.0),
            ]
        )
        rows = build_paper_position_snapshot_rows(state, _valuation_for_state(), "2026-05-09")
        result = save_paper_position_snapshot(rows, "2026-05-09", snapshot_path, archive_dir)
        assert result["replaced"] is False
        saved_rows = _read_rows(snapshot_path)
        assert [(row["snapshot_date"], row["symbol"]) for row in saved_rows] == [
            ("2026-05-08", "AAPL"),
            ("2026-05-09", "CPAY"),
            ("2026-05-09", "GEN"),
        ]
    finally:
        _cleanup(snapshot_path, archive_dir)


def test_save_paper_position_snapshot_rejects_non_paper_path():
    snapshot_path = FRONT_TEST_DIR / f"paper_position_snapshot_test_{uuid4().hex}.csv"
    archive_dir = _unique_archive_dir()
    try:
        state = build_paper_state_from_trades(
            [_trade("t1", "CPAY", "BUY", 10, 100.0)]
        )
        rows = build_paper_position_snapshot_rows(state, _valuation_for_state(), "2026-05-09")
        with pytest.raises(ValueError):
            save_paper_position_snapshot(rows, "2026-05-09", snapshot_path, archive_dir)
    finally:
        if archive_dir.exists():
            for child in archive_dir.iterdir():
                child.unlink()
            archive_dir.rmdir()
