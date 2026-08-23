from __future__ import annotations

import sqlite3
from pathlib import Path

from core.paper_data_freshness import run_paper_data_freshness_check


def _create_base_db(
    db_path: Path,
    *,
    daily_price_rows: list[tuple[str, str]] | None = None,
    market_index_rows: list[tuple[str, str]] | None = None,
    daily_indicator_rows: list[tuple[str, str]] | None = None,
    ticker_rows: list[tuple[str, str | None]] | None = None,
    include_tables: tuple[str, ...] = ("daily_price", "market_index", "daily_indicators", "tickers"),
) -> None:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    if "daily_price" in include_tables:
        cur.execute("CREATE TABLE daily_price (symbol TEXT, date TEXT)")
    if "market_index" in include_tables:
        cur.execute("CREATE TABLE market_index (symbol TEXT, date TEXT)")
    if "daily_indicators" in include_tables:
        cur.execute("CREATE TABLE daily_indicators (symbol TEXT, date TEXT)")
    if "tickers" in include_tables:
        cur.execute("CREATE TABLE tickers (symbol TEXT, listing_board TEXT)")

    for symbol, date in daily_price_rows or []:
        cur.execute("INSERT INTO daily_price (symbol, date) VALUES (?, ?)", (symbol, date))
    for symbol, date in market_index_rows or []:
        cur.execute("INSERT INTO market_index (symbol, date) VALUES (?, ?)", (symbol, date))
    for symbol, date in daily_indicator_rows or []:
        cur.execute("INSERT INTO daily_indicators (symbol, date) VALUES (?, ?)", (symbol, date))
    for symbol, listing_board in ticker_rows or []:
        cur.execute("INSERT INTO tickers (symbol, listing_board) VALUES (?, ?)", (symbol, listing_board))

    conn.commit()
    conn.close()


def _create_ready_db(db_path: Path, target_date: str = "2026-06-05") -> None:
    _create_base_db(
        db_path,
        daily_price_rows=[("AAPL", target_date)],
        market_index_rows=[("SPY", target_date), ("QQQ", target_date), ("^VIX", target_date)],
        daily_indicator_rows=[("AAPL", target_date)],
        ticker_rows=[(f"T{i}", "NASDAQ100") for i in range(60)],
    )


def _write_universe_snapshot(universe_root: Path, date_str: str, content: str = '{"removed":[]}\n') -> Path:
    universe_root.mkdir(parents=True, exist_ok=True)
    path = universe_root / f"universe_snapshot_{date_str.replace('-', '')}.json"
    path.write_text(content, encoding="utf-8")
    return path


def _universe_check(summary: dict) -> dict:
    return next(item for item in summary["checks"] if item["check_name"] == "universe_snapshot")


def test_db_missing_fails(tmp_path):
    summary = run_paper_data_freshness_check(
        date_str="20260513",
        db_path=tmp_path / "missing.db",
        universe_root=tmp_path / "universe",
    )
    assert summary["result"] == "FAIL"
    assert summary["error_count"] >= 1


def test_required_table_missing_fails(tmp_path):
    db_path = tmp_path / "market.db"
    _create_base_db(db_path, include_tables=("daily_price", "market_index", "tickers"))
    summary = run_paper_data_freshness_check(
        date_str="20260513",
        db_path=db_path,
        universe_root=tmp_path / "universe",
    )
    assert summary["result"] == "FAIL"
    assert any(item["check_name"] == "daily_indicators_table_exists" for item in summary["checks"])


def test_daily_price_empty_fails(tmp_path):
    db_path = tmp_path / "market.db"
    _create_base_db(
        db_path,
        market_index_rows=[("SPY", "2026-05-13"), ("QQQ", "2026-05-13"), ("^VIX", "2026-05-13")],
        daily_indicator_rows=[("AAPL", "2026-05-13")],
        ticker_rows=[("AAPL", "NASDAQ100")],
    )
    summary = run_paper_data_freshness_check(date_str="20260513", db_path=db_path, universe_root=tmp_path / "universe")
    assert summary["result"] == "FAIL"
    assert any(item["check_name"] == "daily_price_data" and item["severity"] == "error" for item in summary["checks"])


def test_spy_missing_fails(tmp_path):
    db_path = tmp_path / "market.db"
    _create_base_db(
        db_path,
        daily_price_rows=[("AAPL", "2026-05-13")],
        market_index_rows=[("QQQ", "2026-05-13"), ("^VIX", "2026-05-13")],
        daily_indicator_rows=[("AAPL", "2026-05-13")],
        ticker_rows=[("AAPL", "NASDAQ100")] * 60,
    )
    summary = run_paper_data_freshness_check(date_str="20260513", db_path=db_path, universe_root=tmp_path / "universe")
    assert summary["result"] == "FAIL"
    assert any(item["symbol"] == "SPY" and item["severity"] == "error" for item in summary["checks"])


def test_daily_indicators_missing_target_fails(tmp_path):
    db_path = tmp_path / "market.db"
    _create_base_db(
        db_path,
        daily_price_rows=[("AAPL", "2026-05-13")],
        market_index_rows=[("SPY", "2026-05-13"), ("QQQ", "2026-05-13"), ("^VIX", "2026-05-13")],
        daily_indicator_rows=[("AAPL", "2026-05-12")],
        ticker_rows=[(f"T{i}", "NASDAQ100") for i in range(60)],
    )
    summary = run_paper_data_freshness_check(date_str="20260513", db_path=db_path, universe_root=tmp_path / "universe")
    assert summary["result"] == "FAIL"
    assert any(
        item["check_name"] == "daily_indicators_target_coverage" and item["severity"] == "error"
        for item in summary["checks"]
    )


def test_strict_escalates_stale_warning_to_error(tmp_path):
    db_path = tmp_path / "market.db"
    _create_base_db(
        db_path,
        daily_price_rows=[("AAPL", "2026-05-13")],
        market_index_rows=[("SPY", "2026-05-12"), ("QQQ", "2026-05-13"), ("^VIX", "2026-05-13")],
        daily_indicator_rows=[("AAPL", "2026-05-12")],
        ticker_rows=[(f"T{i}", "NASDAQ100") for i in range(60)],
    )
    summary = run_paper_data_freshness_check(
        date_str="20260513",
        strict=True,
        db_path=db_path,
        universe_root=tmp_path / "universe",
    )
    assert summary["result"] == "FAIL"
    assert any(item["severity"] == "error" and item["check_name"] in {"market_index_target_coverage", "daily_indicators_target_coverage"} for item in summary["checks"])


def test_future_global_max_with_exact_target_coverage_can_pass(tmp_path):
    db_path = tmp_path / "market.db"
    _create_base_db(
        db_path,
        daily_price_rows=[("AAPL", "2026-05-13"), ("AAPL", "2026-05-14")],
        market_index_rows=[
            ("SPY", "2026-05-13"), ("SPY", "2026-05-14"),
            ("QQQ", "2026-05-13"), ("QQQ", "2026-05-14"),
            ("^VIX", "2026-05-13"), ("^VIX", "2026-05-14"),
        ],
        daily_indicator_rows=[("AAPL", "2026-05-13"), ("AAPL", "2026-05-14")],
        ticker_rows=[(f"T{i}", "NASDAQ100") for i in range(60)],
    )

    summary = run_paper_data_freshness_check(
        date_str="20260513",
        strict=True,
        db_path=db_path,
        universe_root=tmp_path / "universe",
    )

    assert summary["result"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert not any(item["severity"] == "error" for item in summary["checks"])


def test_tickers_zero_fails(tmp_path):
    db_path = tmp_path / "market.db"
    _create_base_db(
        db_path,
        daily_price_rows=[("AAPL", "2026-05-13")],
        market_index_rows=[("SPY", "2026-05-13"), ("QQQ", "2026-05-13"), ("^VIX", "2026-05-13")],
        daily_indicator_rows=[("AAPL", "2026-05-13")],
        ticker_rows=[],
    )
    summary = run_paper_data_freshness_check(date_str="20260513", db_path=db_path, universe_root=tmp_path / "universe")
    assert summary["result"] == "FAIL"
    assert any(item["check_name"] == "tickers_row_count" and item["severity"] == "error" for item in summary["checks"])


def test_universe_snapshot_missing_warns(tmp_path):
    db_path = tmp_path / "market.db"
    _create_base_db(
        db_path,
        daily_price_rows=[("AAPL", "2026-05-13")],
        market_index_rows=[("SPY", "2026-05-13"), ("QQQ", "2026-05-13"), ("^VIX", "2026-05-13")],
        daily_indicator_rows=[("AAPL", "2026-05-13")],
        ticker_rows=[(f"T{i}", "NASDAQ100") for i in range(60)],
    )
    summary = run_paper_data_freshness_check(date_str="20260513", db_path=db_path, universe_root=tmp_path / "universe")
    assert any(item["check_name"] == "universe_snapshot" and item["severity"] == "warning" for item in summary["checks"])


def test_universe_snapshot_exact_target_date_passes(tmp_path):
    db_path = tmp_path / "market.db"
    universe_root = tmp_path / "universe"
    _create_ready_db(db_path)
    _write_universe_snapshot(universe_root, "2026-06-05")

    summary = run_paper_data_freshness_check(date_str="20260605", db_path=db_path, universe_root=universe_root)
    check = _universe_check(summary)

    assert summary["result"] == "PASS"
    assert check["severity"] == "info"
    assert check["status"] == "ok"
    assert check["latest_date"] == "2026-06-05"


def test_universe_snapshot_same_quarter_asof_passes_without_warning(tmp_path):
    db_path = tmp_path / "market.db"
    universe_root = tmp_path / "universe"
    _create_ready_db(db_path)
    _write_universe_snapshot(universe_root, "2026-04-01")

    summary = run_paper_data_freshness_check(date_str="20260605", db_path=db_path, universe_root=universe_root)
    check = _universe_check(summary)

    assert summary["result"] == "PASS"
    assert summary["warning_count"] == 0
    assert check["severity"] == "info"
    assert check["status"] == "ok"
    assert check["latest_date"] == "2026-04-01"
    assert "same-quarter" in check["message"]


def test_universe_snapshot_prior_quarter_fallback_warns(tmp_path):
    db_path = tmp_path / "market.db"
    universe_root = tmp_path / "universe"
    _create_ready_db(db_path)
    _write_universe_snapshot(universe_root, "2026-03-31")

    summary = run_paper_data_freshness_check(date_str="20260605", db_path=db_path, universe_root=universe_root)
    check = _universe_check(summary)

    assert summary["result"] == "PASS_WITH_WARNINGS"
    assert check["severity"] == "warning"
    assert check["status"] == "fallback"
    assert check["latest_date"] == "2026-03-31"


def test_universe_snapshot_directory_missing_warns(tmp_path):
    db_path = tmp_path / "market.db"
    _create_ready_db(db_path)

    summary = run_paper_data_freshness_check(date_str="20260605", db_path=db_path, universe_root=tmp_path / "missing")
    check = _universe_check(summary)

    assert summary["result"] == "PASS_WITH_WARNINGS"
    assert check["severity"] == "warning"
    assert check["status"] == "missing"


def test_universe_snapshot_corrupt_file_warns(tmp_path):
    db_path = tmp_path / "market.db"
    universe_root = tmp_path / "universe"
    _create_ready_db(db_path)
    _write_universe_snapshot(universe_root, "2026-04-01", content="{bad json")

    summary = run_paper_data_freshness_check(date_str="20260605", db_path=db_path, universe_root=universe_root)
    check = _universe_check(summary)

    assert summary["result"] == "PASS_WITH_WARNINGS"
    assert check["severity"] == "warning"
    assert check["status"] == "unreadable"
    assert check["latest_date"] == "2026-04-01"


def test_warning_only_returns_pass_with_warnings(tmp_path):
    db_path = tmp_path / "market.db"
    _create_base_db(
        db_path,
        daily_price_rows=[("AAPL", "2026-05-13")],
        market_index_rows=[("SPY", "2026-05-13"), ("QQQ", "2026-05-13"), ("^VIX", "2026-05-13")],
        daily_indicator_rows=[("AAPL", "2026-05-13")],
        ticker_rows=[(f"T{i}", "NASDAQ100") for i in range(60)],
    )
    summary = run_paper_data_freshness_check(date_str="20260513", db_path=db_path, universe_root=tmp_path / "universe")
    assert summary["result"] == "PASS_WITH_WARNINGS"
    assert summary["error_count"] == 0
    assert summary["warning_count"] >= 1


def test_error_returns_fail(tmp_path):
    db_path = tmp_path / "market.db"
    _create_base_db(
        db_path,
        daily_price_rows=[("AAPL", "2026-05-12")],
        market_index_rows=[("SPY", "2026-05-12"), ("QQQ", "2026-05-12"), ("^VIX", "2026-05-12")],
        daily_indicator_rows=[("AAPL", "2026-05-12")],
        ticker_rows=[],
    )
    summary = run_paper_data_freshness_check(
        date_str="20260513",
        strict=True,
        db_path=db_path,
        universe_root=tmp_path / "universe",
    )
    assert summary["result"] == "FAIL"
    assert summary["error_count"] > 0


def test_data_freshness_does_not_include_writer_calls():
    helper_text = Path("core/paper_data_freshness.py").read_text(encoding="utf-8")
    assert "update_market_indices" not in helper_text
    assert "update_tickers_info" not in helper_text
    assert "update_stock_data" not in helper_text
    assert "update_technical_indicators" not in helper_text
