from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from core.paper_benchmark_comparison import (
    build_paper_benchmark_comparison_summary,
    generate_paper_benchmark_comparison,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_market_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE market_index (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                date TEXT,
                close REAL,
                adj_close REAL,
                moving_avg_200 REAL
            )
            """
        )
        cur.executemany(
            "INSERT INTO market_index(symbol, date, close, adj_close, moving_avg_200) VALUES (?, ?, ?, ?, ?)",
            [
                ("SPY", "2026-05-09", 100.0, 101.0, None),
                ("SPY", "2026-05-19", 104.0, 105.0, None),
                ("SPY", "2026-05-20", 110.0, 111.0, None),
                ("QQQ", "2026-05-09", 200.0, None, None),
                ("QQQ", "2026-05-19", 210.0, None, None),
                ("QQQ", "2026-05-20", 220.0, None, None),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def _seed_account_snapshot(root: Path, text: str) -> None:
    _write(root / "paper_account_snapshot.csv", text)


def test_initial_cash_is_read_from_account_snapshot(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n"
        "2026-05-20,100000,102000,102000,success,2026-05-20\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    assert summary["initial_cash"] == 100000.0


def test_snapshot_dates_drive_paper_series(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-20,100000,102000,102000,success,2026-05-20\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    assert [row["date"] for row in summary["paper_series"]] == ["2026-05-09", "2026-05-20"]


def test_market_value_is_preferred_over_cost_basis(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100500,100000,success,2026-05-09\n"
        "2026-05-20,100000,101500,101000,success,2026-05-20\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    assert summary["paper_series"][0]["paper_equity"] == 100500.0
    assert summary["paper_series"][0]["valuation_basis"] == "total_equity_market_value"


def test_cost_basis_is_used_as_fallback(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,,100000,success,2026-05-09\n"
        "2026-05-20,100000,,101000,success,2026-05-20\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    assert summary["paper_series"][0]["paper_equity"] == 100000.0
    assert summary["paper_series"][0]["valuation_basis"] == "total_equity_cost_basis"


def test_spy_uses_adj_close_when_available(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n"
        "2026-05-20,100000,102000,102000,success,2026-05-20\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    assert summary["benchmark_series"]["SPY"][0]["price"] == 101.0


def test_qqq_falls_back_to_close_when_adj_close_missing(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n"
        "2026-05-20,100000,102000,102000,success,2026-05-20\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    assert summary["benchmark_series"]["QQQ"][0]["price"] == 200.0


def test_previous_trade_day_price_is_used_when_same_day_missing(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n"
        "2026-05-20,100000,102000,102000,success,2026-05-20\n"
        "2026-05-21,100000,103000,103000,success,2026-05-21\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    latest_spy = summary["benchmark_series"]["SPY"][-1]
    assert latest_spy["price_date"] == "2026-05-20"
    assert latest_spy["used_fallback_price"] is True
    assert latest_spy["staleness_days"] == 1


def test_cash_benchmark_is_flat(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n"
        "2026-05-20,100000,102000,102000,success,2026-05-20\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    cash = summary["summary"]["benchmarks"]["CASH"]
    assert cash["benchmark_return"] == 0.0
    assert cash["benchmark_max_drawdown"] == 0.0


def test_returns_and_excess_return_are_computed(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n"
        "2026-05-20,100000,110000,110000,success,2026-05-20\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    assert round(summary["summary"]["paper"]["paper_return"], 10) == 0.1
    spy = summary["summary"]["benchmarks"]["SPY"]
    assert round(spy["benchmark_return"], 6) == round(111.0 / 101.0 - 1.0, 6)
    assert round(spy["excess_return"], 6) == round(0.1 - spy["benchmark_return"], 6)


def test_max_drawdown_is_computed(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n"
        "2026-05-20,100000,90000,90000,success,2026-05-20\n"
        "2026-05-21,100000,95000,95000,success,2026-05-21\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    assert round(summary["summary"]["paper"]["paper_max_drawdown"], 10) == -0.1


def test_snapshot_count_under_two_returns_insufficient_data(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n",
    )
    summary = build_paper_benchmark_comparison_summary(paper_root=root, market_db=db_path)
    assert summary["availability_status"] == "INSUFFICIENT_DATA"


def test_markdown_and_json_outputs_are_generated(tmp_path):
    root = tmp_path / "paper_test"
    db_path = tmp_path / "market_data.db"
    _seed_market_db(db_path)
    _seed_account_snapshot(
        root,
        "snapshot_date,initial_cash,total_equity_market_value,total_equity_cost_basis,market_valuation_status,valuation_price_date\n"
        "2026-05-09,100000,100000,100000,success,2026-05-09\n"
        "2026-05-20,100000,102000,102000,success,2026-05-20\n",
    )
    result = generate_paper_benchmark_comparison(paper_root=root, market_db=db_path)
    assert result["markdown_path"].exists()
    assert result["json_path"].exists()
    payload = json.loads(result["json_path"].read_text(encoding="utf-8"))
    assert payload["run_mode"] == "exploratory"
    assert payload["official_run"] is False
