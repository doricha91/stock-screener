from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_realized_trade_journal import (
    COST_BASIS_METHOD,
    ENTRY_BASIS_TYPE,
    LOT_LINKING_STATUS,
)
from core.paper_symbol_realized_performance import (
    PAPER_SYMBOL_REALIZED_PERFORMANCE_COLUMNS,
    build_paper_symbol_realized_performance,
    load_paper_realized_trade_journal_rows,
    render_paper_symbol_realized_performance_summary,
    summarize_paper_symbol_realized_performance,
    write_paper_symbol_realized_performance,
    write_paper_symbol_realized_performance_summary,
)
from core.paths import PAPER_TEST_DIR


REALIZED_TRADE_JOURNAL_COLUMNS = [
    "close_date",
    "symbol",
    "shares_closed",
    "entry_price_basis",
    "exit_price",
    "realized_pnl",
    "realized_return_pct",
    "close_trade_id",
    "source",
    "reason",
    "cost_basis_method",
    "entry_basis_type",
    "lot_linking_status",
    "regime",
    "gross_amount",
    "notes",
    "rec_shares",
    "rec_price",
    "position_shares_before_sell",
    "position_shares_after_sell",
    "avg_price_before_sell",
    "cash_after_trade",
    "realized_pnl_cumulative_after_trade",
    "realized_pnl_by_symbol_after_trade",
]


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_symbol_realized_performance_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _row(
    symbol: str = "CPAY",
    close_date: str = "2026-05-12",
    shares_closed: str = "10",
    realized_pnl: str = "80.00",
    realized_return_pct: str = "20.0000000",
    close_trade_id: str = "t1",
) -> dict[str, str]:
    row = {column: "" for column in REALIZED_TRADE_JOURNAL_COLUMNS}
    row.update(
        {
            "close_date": close_date,
            "symbol": symbol,
            "shares_closed": shares_closed,
            "entry_price_basis": "100.00",
            "exit_price": "120.00",
            "realized_pnl": realized_pnl,
            "realized_return_pct": realized_return_pct,
            "close_trade_id": close_trade_id,
            "source": "paper_virtual_fill",
            "reason": "PAPER_FILLED",
            "cost_basis_method": COST_BASIS_METHOD,
            "entry_basis_type": ENTRY_BASIS_TYPE,
            "lot_linking_status": LOT_LINKING_STATUS,
            "regime": "BULL",
            "gross_amount": "1200.00",
            "notes": "",
            "rec_shares": shares_closed,
            "rec_price": "120.00",
            "position_shares_before_sell": shares_closed,
            "position_shares_after_sell": "0",
            "avg_price_before_sell": "100.00",
            "cash_after_trade": "100100.00",
            "realized_pnl_cumulative_after_trade": realized_pnl,
            "realized_pnl_by_symbol_after_trade": realized_pnl,
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


def test_single_symbol_single_row_aggregation():
    rows, warnings = build_paper_symbol_realized_performance([_row()])
    assert warnings == []
    assert len(rows) == 1
    row = rows[0]
    assert row["symbol"] == "CPAY"
    assert row["realized_trade_count"] == 1
    assert row["total_realized_pnl"] == 80.0
    assert row["win_count"] == 1
    assert row["loss_count"] == 0
    assert row["flat_count"] == 0


def test_single_symbol_multiple_rows_aggregation():
    rows, _ = build_paper_symbol_realized_performance(
        [
            _row(realized_pnl="80.00", realized_return_pct="20.0000000", close_trade_id="t1"),
            _row(realized_pnl="-20.00", realized_return_pct="-5.0000000", close_trade_id="t2", close_date="2026-05-13"),
            _row(realized_pnl="0.00", realized_return_pct="0.0000000", close_trade_id="t3", close_date="2026-05-14"),
        ]
    )
    row = rows[0]
    assert row["realized_trade_count"] == 3
    assert row["total_realized_pnl"] == 60.0
    assert row["avg_realized_pnl"] == 20.0
    assert row["avg_realized_return_pct"] == 5.0
    assert row["first_close_date"] == "2026-05-12"
    assert row["last_close_date"] == "2026-05-14"


def test_multiple_symbol_aggregation():
    rows, _ = build_paper_symbol_realized_performance(
        [
            _row(symbol="CPAY", realized_pnl="80.00", close_trade_id="t1"),
            _row(symbol="GEN", realized_pnl="-30.00", realized_return_pct="-3.0000000", close_trade_id="t2"),
        ]
    )
    assert [row["symbol"] for row in rows] == ["CPAY", "GEN"]


def test_win_loss_flat_counts_and_rates():
    rows, _ = build_paper_symbol_realized_performance(
        [
            _row(realized_pnl="80.00", realized_return_pct="20.0000000", close_trade_id="t1"),
            _row(realized_pnl="-20.00", realized_return_pct="-5.0000000", close_trade_id="t2", close_date="2026-05-13"),
            _row(realized_pnl="0.00", realized_return_pct="0.0000000", close_trade_id="t3", close_date="2026-05-14"),
        ]
    )
    row = rows[0]
    assert row["win_count"] == 1
    assert row["loss_count"] == 1
    assert row["flat_count"] == 1
    assert round(row["win_rate"], 7) == round(1 / 3, 7)
    assert round(row["loss_rate"], 7) == round(1 / 3, 7)
    assert round(row["flat_rate"], 7) == round(1 / 3, 7)


def test_best_worst_trade_metrics_and_shares_closed():
    rows, _ = build_paper_symbol_realized_performance(
        [
            _row(shares_closed="10", realized_pnl="80.00", realized_return_pct="20.0000000", close_trade_id="t1"),
            _row(shares_closed="5", realized_pnl="-20.00", realized_return_pct="-5.0000000", close_trade_id="t2", close_date="2026-05-13"),
            _row(shares_closed="2", realized_pnl="10.00", realized_return_pct="2.0000000", close_trade_id="t3", close_date="2026-05-14"),
        ]
    )
    row = rows[0]
    assert row["best_trade_pnl"] == 80.0
    assert row["worst_trade_pnl"] == -20.0
    assert row["best_trade_return_pct"] == 20.0
    assert row["worst_trade_return_pct"] == -5.0
    assert row["total_shares_closed"] == 17


def test_gross_profit_gross_loss_and_profit_factor():
    rows, _ = build_paper_symbol_realized_performance(
        [
            _row(realized_pnl="80.00", close_trade_id="t1"),
            _row(realized_pnl="-20.00", realized_return_pct="-5.0000000", close_trade_id="t2", close_date="2026-05-13"),
            _row(realized_pnl="10.00", realized_return_pct="2.0000000", close_trade_id="t3", close_date="2026-05-14"),
        ]
    )
    row = rows[0]
    assert row["positive_realized_pnl"] == 90.0
    assert row["negative_realized_pnl"] == -20.0
    assert row["gross_profit"] == 90.0
    assert row["gross_loss"] == 20.0
    assert row["profit_factor"] == 4.5


def test_profit_factor_blank_when_gross_loss_zero():
    rows, _ = build_paper_symbol_realized_performance(
        [
            _row(realized_pnl="80.00", close_trade_id="t1"),
            _row(realized_pnl="10.00", realized_return_pct="2.0000000", close_trade_id="t2", close_date="2026-05-13"),
        ]
    )
    assert rows[0]["profit_factor"] == ""


def test_cost_basis_metadata_is_preserved():
    rows, _ = build_paper_symbol_realized_performance([_row()])
    row = rows[0]
    assert row["cost_basis_method"] == COST_BASIS_METHOD
    assert row["entry_basis_type"] == ENTRY_BASIS_TYPE
    assert row["lot_linking_status"] == LOT_LINKING_STATUS


def test_empty_input_returns_empty_rows_and_warning(tmp_path: Path):
    output_csv_path = _paper_test_path("paper_symbol_realized_performance_test", tmp_path, ".csv")
    summary_path = _paper_test_path("paper_symbol_realized_performance_summary_test", tmp_path, ".md")
    try:
        rows, warnings = build_paper_symbol_realized_performance([])
        assert rows == []
        assert warnings == ["No realized trade rows found in paper_realized_trade_journal.csv"]
        write_paper_symbol_realized_performance(rows, output_csv_path)
        summary = summarize_paper_symbol_realized_performance(
            rows,
            input_path=Path("input.csv"),
            output_path=output_csv_path,
            warnings=warnings,
        )
        markdown = render_paper_symbol_realized_performance_summary(summary)
        write_paper_symbol_realized_performance_summary(markdown, summary_path)
        assert "No realized trade rows found" in markdown
        assert "No realized trades available; symbol performance report is empty." in markdown
    finally:
        _cleanup(output_csv_path)
        _cleanup(summary_path)


def test_missing_required_column_is_detected(tmp_path: Path):
    input_path = _paper_test_path("paper_realized_trade_journal_test", tmp_path, ".csv")
    try:
        _write_csv(input_path, ["symbol"], [{"symbol": "CPAY"}])
        with pytest.raises(ValueError, match="Missing realized trade journal columns"):
            load_paper_realized_trade_journal_rows(input_path)
    finally:
        _cleanup(input_path)


def test_invalid_numeric_value_is_detected():
    with pytest.raises(ValueError, match="invalid numeric in realized_pnl"):
        build_paper_symbol_realized_performance([_row(realized_pnl="bad")])


def test_write_csv_contains_expected_columns(tmp_path: Path):
    output_path = _paper_test_path("paper_symbol_realized_performance_test", tmp_path, ".csv")
    try:
        rows, _ = build_paper_symbol_realized_performance([_row()])
        write_paper_symbol_realized_performance(rows, output_path)
        with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
            written_rows = list(csv.DictReader(handle))
        assert list(written_rows[0].keys()) == PAPER_SYMBOL_REALIZED_PERFORMANCE_COLUMNS
    finally:
        _cleanup(output_path)


def test_summary_contains_limitations():
    rows, warnings = build_paper_symbol_realized_performance([_row()])
    summary = summarize_paper_symbol_realized_performance(
        rows,
        input_path=Path("input.csv"),
        output_path=Path("output.csv"),
        warnings=warnings,
    )
    markdown = render_paper_symbol_realized_performance_summary(summary)
    assert "This report summarizes realized SELL-event performance only." in markdown
    assert "Unrealized PnL and current open positions are not included." in markdown
    assert "FIFO/LIFO/lot-matched closed trade accounting is not implemented." in markdown
    assert "open_date and holding_days are intentionally excluded." in markdown
    assert "Metrics are preliminary when realized trade count is small." in markdown
