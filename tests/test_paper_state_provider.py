import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_state_provider import (
    load_official_paper_state_for_daily_plan,
    load_paper_execution_rows_for_state,
)


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_state_provider_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _write_execution_log(path: Path, rows: list[dict]) -> None:
    fieldnames = ["trade_id", "date", "symbol", "side", "shares", "price", "gross_amount"]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_load_paper_execution_rows_for_state_reads_csv(tmp_path: Path):
    log_path = tmp_path / "paper_execution_log.csv"
    _write_execution_log(
        log_path,
        [
            {
                "trade_id": "t1",
                "date": "2026-05-09",
                "symbol": "CPAY",
                "side": "BUY",
                "shares": 10,
                "price": 100.0,
                "gross_amount": 1000.0,
            }
        ],
    )

    rows = load_paper_execution_rows_for_state(log_path=log_path)

    assert len(rows) == 1
    assert rows[0]["symbol"] == "CPAY"


def test_load_official_paper_state_for_daily_plan_maps_cash_and_holdings_from_prior_trades(tmp_path: Path):
    log_path = tmp_path / "paper_execution_log.csv"
    _write_execution_log(
        log_path,
        [
            {
                "trade_id": "t1",
                "date": "2026-05-09",
                "symbol": "CPAY",
                "side": "BUY",
                "shares": 10,
                "price": 100.0,
                "gross_amount": 1000.0,
            },
            {
                "trade_id": "t2",
                "date": "2026-05-09",
                "symbol": "GEN",
                "side": "BUY",
                "shares": 5,
                "price": 200.0,
                "gross_amount": 1000.0,
            },
        ],
    )

    state = load_official_paper_state_for_daily_plan("20260510", log_path=log_path)

    assert state.absolute_cash == 98000.0
    assert state.current_symbols == ["CPAY", "GEN"]
    assert state.shares == {"CPAY": 10, "GEN": 5}
    assert state.avg_price == {"CPAY": 100.0, "GEN": 200.0}
    assert state.highest_prices == {"CPAY": 100.0, "GEN": 200.0}
    assert state.current_cash_ratio == 0.98
    assert state.current_hedge_ratio == 0.0
    assert state.hedge_symbols == []
