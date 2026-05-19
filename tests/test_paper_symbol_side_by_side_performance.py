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
from core.paper_symbol_side_by_side_performance import (
    PAPER_SYMBOL_SIDE_BY_SIDE_PERFORMANCE_COLUMNS,
    build_paper_symbol_side_by_side_performance,
    load_paper_symbol_realized_performance_rows,
    load_paper_symbol_unrealized_performance_rows,
    render_paper_symbol_side_by_side_performance_summary,
    summarize_paper_symbol_side_by_side_performance,
    write_paper_symbol_side_by_side_performance,
    write_paper_symbol_side_by_side_performance_summary,
)
from core.paths import PAPER_TEST_DIR


REALIZED_COLUMNS = [
    "symbol",
    "realized_trade_count",
    "total_realized_pnl",
    "win_count",
    "loss_count",
    "flat_count",
    "win_rate",
    "loss_rate",
    "flat_rate",
    "avg_realized_pnl",
    "avg_realized_return_pct",
    "best_trade_pnl",
    "worst_trade_pnl",
    "best_trade_return_pct",
    "worst_trade_return_pct",
    "total_shares_closed",
    "cost_basis_method",
    "entry_basis_type",
    "lot_linking_status",
    "first_close_date",
    "last_close_date",
    "positive_realized_pnl",
    "negative_realized_pnl",
    "gross_profit",
    "gross_loss",
    "profit_factor",
]

UNREALIZED_COLUMNS = [
    "snapshot_date",
    "symbol",
    "shares",
    "avg_price",
    "market_price",
    "cost_basis",
    "market_value",
    "unrealized_pnl",
    "unrealized_return_pct",
    "position_weight_market",
    "position_status",
    "unrealized_pnl_rank",
    "market_value_rank",
    "unrealized_return_rank",
    "cost_basis_method",
    "valuation_status",
]


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_symbol_side_by_side_performance_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _realized_row(symbol: str, pnl: str, trade_count: str = "1") -> dict[str, str]:
    row = {column: "" for column in REALIZED_COLUMNS}
    row.update(
        {
            "symbol": symbol,
            "realized_trade_count": trade_count,
            "total_realized_pnl": pnl,
            "win_count": "0",
            "loss_count": "1",
            "flat_count": "0",
            "win_rate": "0.0000000",
            "loss_rate": "1.0000000",
            "flat_rate": "0.0000000",
            "avg_realized_pnl": pnl,
            "avg_realized_return_pct": "-1.0000000",
            "best_trade_pnl": pnl,
            "worst_trade_pnl": pnl,
            "best_trade_return_pct": "-1.0000000",
            "worst_trade_return_pct": "-1.0000000",
            "total_shares_closed": "10",
            "cost_basis_method": COST_BASIS_METHOD,
            "entry_basis_type": ENTRY_BASIS_TYPE,
            "lot_linking_status": LOT_LINKING_STATUS,
            "first_close_date": "2026-05-12",
            "last_close_date": "2026-05-12",
            "positive_realized_pnl": "0.00",
            "negative_realized_pnl": pnl,
            "gross_profit": "0.00",
            "gross_loss": "100.00",
            "profit_factor": "0.0000000",
        }
    )
    return row


def _unrealized_row(symbol: str, unrealized_pnl: str, market_value: str, shares: str = "10") -> dict[str, str]:
    row = {column: "" for column in UNREALIZED_COLUMNS}
    row.update(
        {
            "snapshot_date": "2026-05-13",
            "symbol": symbol,
            "shares": shares,
            "avg_price": "10.00",
            "market_price": "11.00",
            "cost_basis": "100.00",
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_return_pct": "10.0000000",
            "position_weight_market": "0.5000000",
            "position_status": "OPEN",
            "unrealized_pnl_rank": "1",
            "market_value_rank": "1",
            "unrealized_return_rank": "1",
            "cost_basis_method": COST_BASIS_METHOD,
            "valuation_status": "success",
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


def test_realized_only_symbol_is_included():
    rows, _, _ = build_paper_symbol_side_by_side_performance(
        [_realized_row("CPAY", "-100.00")],
        [],
    )
    assert rows[0]["symbol"] == "CPAY"
    assert rows[0]["symbol_status"] == "realized_only"


def test_unrealized_only_symbol_is_included():
    rows, _, _ = build_paper_symbol_side_by_side_performance(
        [],
        [_unrealized_row("GEN", "50.00", "150.00")],
    )
    assert rows[0]["symbol"] == "GEN"
    assert rows[0]["symbol_status"] == "unrealized_only"


def test_realized_and_unrealized_symbol_is_included():
    rows, _, _ = build_paper_symbol_side_by_side_performance(
        [_realized_row("GEN", "-100.00")],
        [_unrealized_row("GEN", "50.00", "150.00")],
    )
    assert rows[0]["symbol_status"] == "realized_and_unrealized"


def test_outer_join_includes_all_symbols():
    rows, summary, _ = build_paper_symbol_side_by_side_performance(
        [_realized_row("CPAY", "-100.00"), _realized_row("GEN", "20.00")],
        [_unrealized_row("GEN", "50.00", "150.00"), _unrealized_row("F", "10.00", "110.00")],
    )
    assert [row["symbol"] for row in rows] == ["CPAY", "F", "GEN"]
    assert summary["realized_only_count"] == 1
    assert summary["unrealized_only_count"] == 1
    assert summary["realized_and_unrealized_count"] == 1


def test_total_pnl_is_sum_of_realized_and_unrealized():
    rows, _, _ = build_paper_symbol_side_by_side_performance(
        [_realized_row("GEN", "-100.00")],
        [_unrealized_row("GEN", "50.00", "150.00")],
    )
    assert rows[0]["total_pnl"] == -50.0


def test_missing_realized_defaults_are_applied():
    rows, _, _ = build_paper_symbol_side_by_side_performance([], [_unrealized_row("F", "10.00", "110.00")])
    row = rows[0]
    assert row["realized_pnl"] == 0.0
    assert row["realized_trade_count"] == 0
    assert row["win_count"] == 0


def test_missing_unrealized_defaults_are_applied():
    rows, _, _ = build_paper_symbol_side_by_side_performance([_realized_row("CPAY", "-100.00")], [])
    row = rows[0]
    assert row["unrealized_pnl"] == 0.0
    assert row["open_shares"] == 0
    assert row["open_market_value"] == 0.0


def test_top_and_worst_total_pnl_ranking():
    rows, summary, _ = build_paper_symbol_side_by_side_performance(
        [_realized_row("CPAY", "-100.00"), _realized_row("GEN", "20.00")],
        [_unrealized_row("GEN", "50.00", "150.00"), _unrealized_row("F", "10.00", "110.00")],
    )
    assert rows
    assert summary["top_total_pnl_symbols"][0]["symbol"] == "GEN"
    assert summary["worst_total_pnl_symbols"][0]["symbol"] == "CPAY"


def test_markdown_includes_limitations():
    _, summary_data, warnings = build_paper_symbol_side_by_side_performance(
        [_realized_row("CPAY", "-100.00")],
        [_unrealized_row("GEN", "50.00", "150.00")],
    )
    summary = summarize_paper_symbol_side_by_side_performance(
        summary_data,
        warnings,
        realized_input_path=Path("r.csv"),
        unrealized_input_path=Path("u.csv"),
        output_path=Path("o.csv"),
    )
    markdown = render_paper_symbol_side_by_side_performance_summary(summary)
    assert "This report shows realized and unrealized performance side by side." in markdown
    assert "total_pnl is a reference metric, not a lot-matched accounting result." in markdown
    assert "Realized PnL is average-cost SELL-event based." in markdown
    assert "Unrealized PnL is current open-position snapshot based." in markdown


def test_empty_realized_input_is_handled():
    rows, summary, warnings = build_paper_symbol_side_by_side_performance([], [_unrealized_row("GEN", "50.00", "150.00")])
    assert len(rows) == 1
    assert summary["realized_only_count"] == 0
    assert warnings == []


def test_empty_unrealized_input_is_handled():
    rows, summary, warnings = build_paper_symbol_side_by_side_performance([_realized_row("CPAY", "-100.00")], [])
    assert len(rows) == 1
    assert summary["unrealized_only_count"] == 0
    assert warnings == []


def test_missing_required_realized_columns_detected(tmp_path: Path):
    path = _paper_test_path("paper_symbol_realized_performance_test", tmp_path, ".csv")
    try:
        _write_csv(path, ["symbol"], [{"symbol": "CPAY"}])
        with pytest.raises(ValueError, match="Missing paper symbol realized performance columns"):
            load_paper_symbol_realized_performance_rows(path)
    finally:
        _cleanup(path)


def test_missing_required_unrealized_columns_detected(tmp_path: Path):
    path = _paper_test_path("paper_symbol_unrealized_performance_test", tmp_path, ".csv")
    try:
        _write_csv(path, ["symbol"], [{"symbol": "GEN"}])
        with pytest.raises(ValueError, match="Missing paper symbol unrealized performance columns"):
            load_paper_symbol_unrealized_performance_rows(path)
    finally:
        _cleanup(path)


def test_invalid_numeric_values_are_detected():
    with pytest.raises(ValueError, match="invalid numeric in total_realized_pnl"):
        build_paper_symbol_side_by_side_performance([_realized_row("CPAY", "bad")], [])


def test_write_csv_contains_expected_columns(tmp_path: Path):
    output_csv_path = _paper_test_path("paper_symbol_side_by_side_performance_test", tmp_path, ".csv")
    output_md_path = _paper_test_path("paper_symbol_side_by_side_performance_test", tmp_path, ".md")
    try:
        rows, summary_data, warnings = build_paper_symbol_side_by_side_performance(
            [_realized_row("CPAY", "-100.00")],
            [_unrealized_row("GEN", "50.00", "150.00")],
        )
        write_paper_symbol_side_by_side_performance(rows, output_csv_path)
        summary = summarize_paper_symbol_side_by_side_performance(
            summary_data,
            warnings,
            realized_input_path=Path("r.csv"),
            unrealized_input_path=Path("u.csv"),
            output_path=output_csv_path,
        )
        write_paper_symbol_side_by_side_performance_summary(
            render_paper_symbol_side_by_side_performance_summary(summary),
            output_md_path,
        )
        with output_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            written_rows = list(csv.DictReader(handle))
        assert list(written_rows[0].keys()) == PAPER_SYMBOL_SIDE_BY_SIDE_PERFORMANCE_COLUMNS
        assert output_md_path.exists()
    finally:
        _cleanup(output_csv_path)
        _cleanup(output_md_path)
