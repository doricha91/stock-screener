from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_symbol_unrealized_performance import (
    PAPER_SYMBOL_UNREALIZED_PERFORMANCE_COLUMNS,
    build_paper_symbol_unrealized_performance,
    load_paper_account_snapshot_rows,
    load_paper_position_snapshot_rows,
    render_paper_symbol_unrealized_performance_summary,
    summarize_paper_symbol_unrealized_performance,
    write_paper_symbol_unrealized_performance,
    write_paper_symbol_unrealized_performance_summary,
)
from core.paths import PAPER_TEST_DIR


POSITION_COLUMNS = [
    "snapshot_date",
    "symbol",
    "shares",
    "avg_price",
    "cost_value",
    "close_price",
    "market_value",
    "unrealized_pnl",
    "unrealized_pnl_pct",
    "realized_pnl",
    "total_pnl",
    "total_pnl_pct_on_current_cost",
    "valuation_method",
    "valuation_price_date",
    "price_staleness_days",
    "position_status",
    "created_at",
]

ACCOUNT_COLUMNS = [
    "snapshot_date",
    "currency",
    "initial_cash",
    "cash",
    "positions_cost_value",
    "total_equity_cost_basis",
    "cash_ratio_cost_basis",
    "position_count",
    "symbols",
    "applied_trade_count",
    "valuation_method",
    "source_execution_log",
    "source_current_state",
    "created_at",
    "positions_market_value",
    "total_equity_market_value",
    "cash_ratio_market_value",
    "unrealized_pnl",
    "unrealized_pnl_pct",
    "realized_pnl",
    "realized_pnl_by_symbol",
    "total_pnl",
    "total_pnl_pct",
    "market_valuation_status",
    "market_valuation_error",
    "valuation_price_date",
    "valuation_price_dates",
    "price_staleness_days",
    "max_price_staleness_days",
]


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_symbol_unrealized_performance_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _position_row(
    snapshot_date: str = "2026-05-13",
    symbol: str = "GEN",
    shares: str = "440",
    avg_price: str = "22.68",
    cost_value: str = "9979.20",
    close_price: str = "23.29",
    market_value: str = "10247.60",
    unrealized_pnl: str = "268.40",
    unrealized_pnl_pct: str = "0.0268960",
) -> dict[str, str]:
    row = {column: "" for column in POSITION_COLUMNS}
    row.update(
        {
            "snapshot_date": snapshot_date,
            "symbol": symbol,
            "shares": shares,
            "avg_price": avg_price,
            "cost_value": cost_value,
            "close_price": close_price,
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": unrealized_pnl_pct,
            "realized_pnl": "0.00",
            "total_pnl": unrealized_pnl,
            "total_pnl_pct_on_current_cost": unrealized_pnl_pct,
            "valuation_method": "db_daily_price_close",
            "valuation_price_date": snapshot_date,
            "price_staleness_days": "0",
            "position_status": "OPEN",
            "created_at": f"{snapshot_date}T18:11:11",
        }
    )
    return row


def _account_row(
    snapshot_date: str = "2026-05-13",
    positions_cost_value: str = "39042.79",
    positions_market_value: str = "39322.39",
    unrealized_pnl: str = "279.60",
) -> dict[str, str]:
    row = {column: "" for column in ACCOUNT_COLUMNS}
    row.update(
        {
            "snapshot_date": snapshot_date,
            "currency": "USD",
            "initial_cash": "100000.00",
            "cash": "60344.67",
            "positions_cost_value": positions_cost_value,
            "total_equity_cost_basis": "99387.46",
            "cash_ratio_cost_basis": "0.6071658",
            "position_count": "3",
            "symbols": "BRK-B|F|GEN",
            "applied_trade_count": "10",
            "valuation_method": "db_daily_price_close",
            "source_execution_log": "outputs/paper_test/paper_execution_log.csv",
            "source_current_state": "outputs/paper_test/paper_current_state_20260513.json",
            "created_at": "2026-05-14T18:11:11",
            "positions_market_value": positions_market_value,
            "total_equity_market_value": "99667.06",
            "cash_ratio_market_value": "0.6054625",
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": "0.0071614",
            "realized_pnl": "-612.54",
            "realized_pnl_by_symbol": "{}",
            "total_pnl": "-332.94",
            "total_pnl_pct": "-0.0033294",
            "market_valuation_status": "success",
            "market_valuation_error": "",
            "valuation_price_date": snapshot_date,
            "valuation_price_dates": "{}",
            "price_staleness_days": "{}",
            "max_price_staleness_days": "0",
        }
    )
    return row


def _paper_test_path(prefix: str, tmp_path: Path, suffix: str) -> Path:
    return PAPER_TEST_DIR / f"{prefix}_{tmp_path.name}{suffix}"


def _cleanup(path: Path) -> None:
    if path.exists():
        path.unlink()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_latest_snapshot_date_is_selected_and_only_latest_rows_used():
    rows, summary, warnings = build_paper_symbol_unrealized_performance(
        [
            _position_row(snapshot_date="2026-05-12", symbol="CF"),
            _position_row(snapshot_date="2026-05-13", symbol="GEN"),
            _position_row(snapshot_date="2026-05-13", symbol="F", shares="100", avg_price="10.00", cost_value="1000.00", close_price="11.00", market_value="1100.00", unrealized_pnl="100.00", unrealized_pnl_pct="0.1000000"),
        ],
        [_account_row(positions_cost_value="10979.20", positions_market_value="11347.60", unrealized_pnl="368.40")],
    )
    assert warnings == []
    assert summary["latest_snapshot_date"] == "2026-05-13"
    assert [row["symbol"] for row in rows] == ["F", "GEN"]


def test_position_weight_is_calculated_from_market_value():
    rows, _, _ = build_paper_symbol_unrealized_performance(
        [
            _position_row(symbol="GEN"),
            _position_row(symbol="F", shares="100", avg_price="10.00", cost_value="1000.00", close_price="11.00", market_value="1100.00", unrealized_pnl="100.00", unrealized_pnl_pct="0.1000000"),
        ]
    )
    by_symbol = {row["symbol"]: row for row in rows}
    total_market_value = 10247.60 + 1100.00
    assert round(by_symbol["GEN"]["position_weight_market"], 7) == round(10247.60 / total_market_value, 7)


def test_input_unrealized_values_are_kept():
    rows, _, _ = build_paper_symbol_unrealized_performance([_position_row()])
    row = rows[0]
    assert row["unrealized_pnl"] == 268.40
    assert row["unrealized_return_pct"] == 2.68960


def test_best_worst_rankings_are_assigned():
    rows, summary, _ = build_paper_symbol_unrealized_performance(
        [
            _position_row(symbol="GEN", unrealized_pnl="268.40", unrealized_pnl_pct="0.0268960", market_value="10247.60"),
            _position_row(symbol="F", shares="100", avg_price="10.00", cost_value="1000.00", close_price="9.00", market_value="900.00", unrealized_pnl="-100.00", unrealized_pnl_pct="-0.1000000"),
            _position_row(symbol="BRK-B", shares="20", avg_price="484.96", cost_value="9699.20", close_price="485.52", market_value="9710.40", unrealized_pnl="11.20", unrealized_pnl_pct="0.0011547"),
        ]
    )
    by_symbol = {row["symbol"]: row for row in rows}
    assert by_symbol["GEN"]["unrealized_pnl_rank"] == 1
    assert by_symbol["F"]["unrealized_pnl_rank"] == 3
    assert summary["best_unrealized_pnl_symbols"][0]["symbol"] == "GEN"
    assert summary["worst_unrealized_pnl_symbols"][0]["symbol"] == "F"
    assert summary["largest_market_value_symbols"][0]["symbol"] == "GEN"


def test_account_snapshot_cross_check_passes():
    rows, summary, warnings = build_paper_symbol_unrealized_performance(
        [
            _position_row(symbol="GEN"),
            _position_row(symbol="F", shares="100", avg_price="10.00", cost_value="1000.00", close_price="11.00", market_value="1100.00", unrealized_pnl="100.00", unrealized_pnl_pct="0.1000000"),
        ],
        [_account_row(positions_cost_value="10979.20", positions_market_value="11347.60", unrealized_pnl="368.40")],
    )
    assert rows
    assert warnings == []
    assert summary["account_cross_check"]["status"] == "passed"


def test_account_snapshot_mismatch_adds_warning():
    _, summary, warnings = build_paper_symbol_unrealized_performance(
        [_position_row(symbol="GEN")],
        [_account_row(positions_cost_value="1.00", positions_market_value="1.00", unrealized_pnl="1.00")],
    )
    assert summary["account_cross_check"]["status"] == "warning"
    assert any("mismatch" in warning for warning in warnings)


def test_empty_position_snapshot_handling(tmp_path: Path):
    output_csv_path = _paper_test_path("paper_symbol_unrealized_performance_test", tmp_path, ".csv")
    output_md_path = _paper_test_path("paper_symbol_unrealized_performance_summary_test", tmp_path, ".md")
    try:
        rows, summary_data, warnings = build_paper_symbol_unrealized_performance([])
        assert rows == []
        assert warnings == ["No position snapshot rows found in paper_position_snapshot.csv"]
        write_paper_symbol_unrealized_performance(rows, output_csv_path)
        summary = summarize_paper_symbol_unrealized_performance(summary_data, warnings, Path("in.csv"), output_csv_path)
        markdown = render_paper_symbol_unrealized_performance_summary(summary)
        write_paper_symbol_unrealized_performance_summary(markdown, output_md_path)
        assert "No position snapshot rows found" in markdown
    finally:
        _cleanup(output_csv_path)
        _cleanup(output_md_path)


def test_missing_required_columns_are_detected(tmp_path: Path):
    input_path = _paper_test_path("paper_position_snapshot_test", tmp_path, ".csv")
    try:
        _write_csv(input_path, ["symbol"], [{"symbol": "GEN"}])
        with pytest.raises(ValueError, match="Missing paper position snapshot columns"):
            load_paper_position_snapshot_rows(input_path)
    finally:
        _cleanup(input_path)


def test_invalid_numeric_value_is_detected():
    with pytest.raises(ValueError, match="invalid numeric in market_value"):
        build_paper_symbol_unrealized_performance([_position_row(market_value="bad")])


def test_summary_markdown_includes_limitations():
    rows, summary_data, warnings = build_paper_symbol_unrealized_performance([_position_row()])
    assert rows
    summary = summarize_paper_symbol_unrealized_performance(summary_data, warnings, Path("in.csv"), Path("out.csv"))
    markdown = render_paper_symbol_unrealized_performance_summary(summary)
    assert "This report summarizes current open-position unrealized performance only." in markdown
    assert "Realized PnL and closed trades are not included." in markdown
    assert "Total symbol performance will be handled in a later MFU." in markdown
    assert "FIFO/LIFO/lot ledger accounting is not implemented." in markdown
    assert "open_date and holding_days are intentionally excluded." in markdown


def test_write_csv_contains_expected_columns(tmp_path: Path):
    output_path = _paper_test_path("paper_symbol_unrealized_performance_test", tmp_path, ".csv")
    try:
        rows, _, _ = build_paper_symbol_unrealized_performance([_position_row()])
        write_paper_symbol_unrealized_performance(rows, output_path)
        with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
            written_rows = list(csv.DictReader(handle))
        assert list(written_rows[0].keys()) == PAPER_SYMBOL_UNREALIZED_PERFORMANCE_COLUMNS
    finally:
        _cleanup(output_path)


def test_account_snapshot_loader_detects_missing_columns(tmp_path: Path):
    input_path = _paper_test_path("paper_account_snapshot_test", tmp_path, ".csv")
    try:
        _write_csv(input_path, ["snapshot_date"], [{"snapshot_date": "2026-05-13"}])
        with pytest.raises(ValueError, match="Missing paper account snapshot columns"):
            load_paper_account_snapshot_rows(input_path)
    finally:
        _cleanup(input_path)
