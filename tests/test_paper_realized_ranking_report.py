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
from core.paper_realized_ranking_report import (
    PAPER_REALIZED_RANKING_COLUMNS,
    build_paper_realized_rankings,
    load_paper_symbol_realized_performance_rows,
    render_paper_realized_ranking_report,
    summarize_paper_realized_ranking_report,
    write_paper_realized_ranking_csv,
    write_paper_realized_ranking_report,
)
from core.paths import PAPER_TEST_DIR


SYMBOL_PERFORMANCE_COLUMNS = [
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


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_realized_ranking_report_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _row(
    symbol: str,
    realized_trade_count: str,
    total_realized_pnl: str,
    win_count: str,
    loss_count: str,
    flat_count: str,
    win_rate: str,
    avg_realized_return_pct: str,
    profit_factor: str,
) -> dict[str, str]:
    row = {column: "" for column in SYMBOL_PERFORMANCE_COLUMNS}
    row.update(
        {
            "symbol": symbol,
            "realized_trade_count": realized_trade_count,
            "total_realized_pnl": total_realized_pnl,
            "win_count": win_count,
            "loss_count": loss_count,
            "flat_count": flat_count,
            "win_rate": win_rate,
            "loss_rate": "0.0000000",
            "flat_rate": "0.0000000",
            "avg_realized_pnl": total_realized_pnl,
            "avg_realized_return_pct": avg_realized_return_pct,
            "best_trade_pnl": total_realized_pnl,
            "worst_trade_pnl": total_realized_pnl,
            "best_trade_return_pct": avg_realized_return_pct,
            "worst_trade_return_pct": avg_realized_return_pct,
            "total_shares_closed": "10",
            "cost_basis_method": COST_BASIS_METHOD,
            "entry_basis_type": ENTRY_BASIS_TYPE,
            "lot_linking_status": LOT_LINKING_STATUS,
            "first_close_date": "2026-05-12",
            "last_close_date": "2026-05-12",
            "positive_realized_pnl": "0.00",
            "negative_realized_pnl": "0.00",
            "gross_profit": "0.00",
            "gross_loss": "0.00",
            "profit_factor": profit_factor,
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


def _build_summary(rows: list[dict[str, str]]):
    rankings, ranking_csv_rows, warnings, overall = build_paper_realized_rankings(rows)
    return rankings, ranking_csv_rows, warnings, summarize_paper_realized_ranking_report(
        rankings,
        warnings,
        overall,
        input_path=Path("input.csv"),
        output_csv_path=Path("out.csv"),
        output_markdown_path=Path("out.md"),
    )


def test_top_realized_pnl_ranking_sort_order():
    rows = [
        _row("A", "3", "10.00", "1", "2", "0", "0.3333333", "1.0000000", "1.5000000"),
        _row("B", "3", "50.00", "2", "1", "0", "0.6666667", "2.0000000", "2.0000000"),
        _row("C", "1", "-5.00", "0", "1", "0", "0.0000000", "-1.0000000", "0.0000000"),
    ]
    rankings, _, _, _ = _build_summary(rows)
    assert [row["symbol"] for row in rankings["top_realized_pnl"]] == ["B", "A", "C"]


def test_worst_realized_pnl_ranking_sort_order():
    rows = [
        _row("A", "3", "10.00", "1", "2", "0", "0.3333333", "1.0000000", "1.5000000"),
        _row("B", "3", "50.00", "2", "1", "0", "0.6666667", "2.0000000", "2.0000000"),
        _row("C", "1", "-5.00", "0", "1", "0", "0.0000000", "-1.0000000", "0.0000000"),
    ]
    rankings, _, _, _ = _build_summary(rows)
    assert [row["symbol"] for row in rankings["worst_realized_pnl"]] == ["C", "A", "B"]


def test_loss_contribution_calculation():
    rows = [
        _row("A", "3", "-100.00", "0", "3", "0", "0.0000000", "-2.0000000", "0.0000000"),
        _row("B", "3", "-300.00", "0", "3", "0", "0.0000000", "-4.0000000", "0.0000000"),
    ]
    _, ranking_csv_rows, _, _ = _build_summary(rows)
    loss_rows = [row for row in ranking_csv_rows if row["ranking_type"] == "loss_contribution"]
    assert loss_rows[0]["symbol"] == "B"
    assert round(loss_rows[0]["metric_value"], 7) == 75.0
    assert round(loss_rows[1]["metric_value"], 7) == 25.0


def test_no_loss_symbols_warning():
    rows = [
        _row("A", "3", "100.00", "3", "0", "0", "1.0000000", "2.0000000", ""),
    ]
    _, _, warnings, summary = _build_summary(rows)
    assert "No realized loss symbols" in warnings
    markdown = render_paper_realized_ranking_report(summary)
    assert "No realized loss symbols" in markdown


def test_win_rate_ranking_sort_order():
    rows = [
        _row("A", "3", "10.00", "2", "1", "0", "0.6666667", "1.0000000", "1.5000000"),
        _row("B", "4", "8.00", "2", "2", "0", "0.5000000", "0.5000000", "1.2000000"),
        _row("C", "2", "20.00", "2", "0", "0", "1.0000000", "2.0000000", ""),
    ]
    rankings, _, _, _ = _build_summary(rows)
    assert [row["symbol"] for row in rankings["win_rate"]] == ["C", "A", "B"]


def test_profit_factor_na_is_excluded_from_profit_factor_ranking():
    rows = [
        _row("A", "3", "10.00", "2", "1", "0", "0.6666667", "1.0000000", "1.5000000"),
        _row("B", "3", "8.00", "2", "1", "0", "0.6666667", "0.5000000", ""),
    ]
    rankings, _, warnings, _ = _build_summary(rows)
    assert [row["symbol"] for row in rankings["profit_factor"]] == ["A"]
    assert any("profit_factor" in warning for warning in warnings)


def test_trade_count_ranking_sort_order():
    rows = [
        _row("A", "3", "10.00", "2", "1", "0", "0.6666667", "1.0000000", "1.5000000"),
        _row("B", "5", "8.00", "2", "3", "0", "0.4000000", "0.5000000", "1.2000000"),
        _row("C", "2", "20.00", "2", "0", "0", "1.0000000", "2.0000000", ""),
    ]
    rankings, _, _, _ = _build_summary(rows)
    assert [row["symbol"] for row in rankings["trade_count"]] == ["B", "A", "C"]


def test_markdown_includes_limitations_and_realized_only_text():
    rows = [_row("A", "1", "10.00", "1", "0", "0", "1.0000000", "2.0000000", "")]
    _, _, _, summary = _build_summary(rows)
    markdown = render_paper_realized_ranking_report(summary)
    assert "This report summarizes realized SELL-event performance only." in markdown
    assert "Open positions and unrealized PnL are not included." in markdown
    assert "FIFO/LIFO/lot ledger accounting is not implemented." in markdown
    assert "open_date and holding_days are intentionally excluded." in markdown


def test_ranking_csv_is_created(tmp_path: Path):
    output_csv_path = _paper_test_path("paper_realized_ranking_test", tmp_path, ".csv")
    output_markdown_path = _paper_test_path("paper_realized_ranking_test", tmp_path, ".md")
    try:
        rows = [_row("A", "3", "10.00", "1", "2", "0", "0.3333333", "1.0000000", "1.5000000")]
        rankings, ranking_csv_rows, warnings, overall = build_paper_realized_rankings(rows)
        write_paper_realized_ranking_csv(ranking_csv_rows, output_csv_path)
        summary = summarize_paper_realized_ranking_report(
            rankings,
            warnings,
            overall,
            input_path=Path("input.csv"),
            output_csv_path=output_csv_path,
            output_markdown_path=output_markdown_path,
        )
        write_paper_realized_ranking_report(render_paper_realized_ranking_report(summary), output_markdown_path)
        with output_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            written_rows = list(csv.DictReader(handle))
        assert list(written_rows[0].keys()) == PAPER_REALIZED_RANKING_COLUMNS
        assert output_markdown_path.exists()
    finally:
        _cleanup(output_csv_path)
        _cleanup(output_markdown_path)


def test_empty_input_csv_handling(tmp_path: Path):
    input_path = _paper_test_path("paper_symbol_realized_performance_test", tmp_path, ".csv")
    output_csv_path = _paper_test_path("paper_realized_ranking_test", tmp_path, ".csv")
    output_markdown_path = _paper_test_path("paper_realized_ranking_test", tmp_path, ".md")
    try:
        _write_csv(input_path, SYMBOL_PERFORMANCE_COLUMNS, [])
        loaded_rows = load_paper_symbol_realized_performance_rows(input_path)
        rankings, ranking_csv_rows, warnings, overall = build_paper_realized_rankings(loaded_rows)
        assert ranking_csv_rows == []
        assert "No symbol realized performance rows found" in warnings[0]
        summary = summarize_paper_realized_ranking_report(
            rankings,
            warnings,
            overall,
            input_path=input_path,
            output_csv_path=output_csv_path,
            output_markdown_path=output_markdown_path,
        )
        markdown = render_paper_realized_ranking_report(summary)
        assert "No symbol realized performance rows found" in markdown
    finally:
        _cleanup(input_path)
        _cleanup(output_csv_path)
        _cleanup(output_markdown_path)


def test_missing_required_column_is_detected(tmp_path: Path):
    input_path = _paper_test_path("paper_symbol_realized_performance_test", tmp_path, ".csv")
    try:
        _write_csv(input_path, ["symbol"], [{"symbol": "A"}])
        with pytest.raises(ValueError, match="Missing symbol realized performance columns"):
            load_paper_symbol_realized_performance_rows(input_path)
    finally:
        _cleanup(input_path)
