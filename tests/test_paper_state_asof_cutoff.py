import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_account_state import build_paper_state_from_trades
from core.paper_state_provider import (
    filter_trade_rows_before_plan_date,
    load_official_paper_state_for_daily_plan,
)


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_state_asof_{uuid4().hex}"
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


def _sample_rows() -> list[dict]:
    return [
        {
            "trade_id": "t1",
            "date": "2026-05-11",
            "symbol": "CPAY",
            "side": "BUY",
            "shares": 10,
            "price": 100.0,
            "gross_amount": 1000.0,
        },
        {
            "trade_id": "t2",
            "date": "2026-05-12",
            "symbol": "CPAY",
            "side": "SELL",
            "shares": -10,
            "price": 110.0,
            "gross_amount": 1100.0,
        },
        {
            "trade_id": "t3",
            "date": "2026-05-12",
            "symbol": "CF",
            "side": "BUY",
            "shares": 5,
            "price": 120.0,
            "gross_amount": 600.0,
        },
        {
            "trade_id": "t4",
            "date": "2026-05-13",
            "symbol": "CF",
            "side": "SELL",
            "shares": -5,
            "price": 125.0,
            "gross_amount": 625.0,
        },
        {
            "trade_id": "t5",
            "date": "2026-05-13",
            "symbol": "F",
            "side": "BUY",
            "shares": 20,
            "price": 15.0,
            "gross_amount": 300.0,
        },
    ]


def test_filter_trade_rows_before_plan_date_excludes_same_day_rows():
    filtered_rows = filter_trade_rows_before_plan_date(_sample_rows(), "2026-05-12")
    assert [row["trade_id"] for row in filtered_rows] == ["t1"]


def test_filter_trade_rows_before_plan_date_includes_prior_day_and_excludes_same_day():
    filtered_rows = filter_trade_rows_before_plan_date(_sample_rows(), "2026-05-13")
    assert [row["trade_id"] for row in filtered_rows] == ["t1", "t2", "t3"]


def test_load_official_paper_state_for_daily_plan_uses_trade_date_lt_plan_date(tmp_path: Path):
    log_path = tmp_path / "paper_execution_log.csv"
    _write_execution_log(log_path, _sample_rows())

    state = load_official_paper_state_for_daily_plan("2026-05-12", log_path=log_path)

    assert state.current_symbols == ["CPAY"]
    assert state.shares == {"CPAY": 10}


def test_load_official_paper_state_for_daily_plan_includes_prior_day_commit_only(tmp_path: Path):
    log_path = tmp_path / "paper_execution_log.csv"
    _write_execution_log(log_path, _sample_rows())

    state = load_official_paper_state_for_daily_plan("2026-05-13", log_path=log_path)

    assert state.current_symbols == ["CF"]
    assert state.shares == {"CF": 5}
    assert state.avg_price == {"CF": 120.0}


def test_load_official_paper_state_for_daily_plan_accepts_compact_and_dashed_dates(tmp_path: Path):
    log_path = tmp_path / "paper_execution_log.csv"
    _write_execution_log(log_path, _sample_rows())

    compact_state = load_official_paper_state_for_daily_plan("20260513", log_path=log_path)
    dashed_state = load_official_paper_state_for_daily_plan("2026-05-13", log_path=log_path)

    assert compact_state.current_symbols == dashed_state.current_symbols
    assert compact_state.shares == dashed_state.shares
    assert compact_state.absolute_cash == dashed_state.absolute_cash


def test_eod_style_reducer_semantics_remain_trade_date_lte_target_date():
    full_state = build_paper_state_from_trades(_sample_rows(), initial_cash=100000.0, currency="USD")

    assert full_state.positions.keys() == {"F"}
    assert full_state.positions["F"].shares == 20
