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
    REALIZED_TRADE_JOURNAL_COLUMNS,
    build_average_cost_realized_trade_journal,
    load_paper_execution_rows,
    render_realized_trade_journal_summary,
    summarize_realized_trade_journal,
    write_realized_trade_journal,
    write_realized_trade_journal_summary,
)
from core.paths import PAPER_TEST_DIR


EXECUTION_LOG_COLUMNS = [
    "trade_id",
    "date",
    "regime",
    "symbol",
    "side",
    "shares",
    "price",
    "gross_amount",
    "source",
    "status",
    "reason",
    "notes",
    "rec_shares",
    "rec_price",
    "created_at",
]


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_realized_trade_journal_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _make_trade(
    trade_id: str,
    trade_date: str,
    symbol: str,
    side: str,
    shares: int,
    price: float,
) -> dict[str, str]:
    return {
        "trade_id": trade_id,
        "date": trade_date,
        "regime": "BULL",
        "symbol": symbol,
        "side": side,
        "shares": str(shares),
        "price": f"{price:.2f}",
        "gross_amount": f"{shares * price:.2f}",
        "source": "journal_actual_fill",
        "status": "READY_FOR_PAPER_TRADE",
        "reason": "PAPER_FILLED",
        "notes": "",
        "rec_shares": str(abs(shares)),
        "rec_price": f"{price:.2f}",
        "created_at": f"{trade_date}T20:00:00",
    }


def _write_execution_log(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXECUTION_LOG_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _paper_test_path(prefix: str, tmp_path: Path, suffix: str) -> Path:
    return PAPER_TEST_DIR / f"{prefix}_{tmp_path.name}{suffix}"


def _cleanup(path: Path) -> None:
    if path.exists():
        path.unlink()


def test_buy_only_generates_zero_realized_rows():
    result = build_average_cost_realized_trade_journal(
        [_make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0)]
    )
    assert result.rows == []
    assert result.duplicate_skipped_count == 0


def test_partial_sell_generates_one_realized_row():
    result = build_average_cost_realized_trade_journal(
        [
            _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -4, 120.0),
        ]
    )
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["shares_closed"] == 4
    assert row["entry_price_basis"] == 100.0
    assert row["exit_price"] == 120.0
    assert row["realized_pnl"] == 80.0
    assert row["realized_return_pct"] == 20.0
    assert row["position_shares_before_sell"] == 10
    assert row["position_shares_after_sell"] == 6
    assert row["avg_price_before_sell"] == 100.0
    assert row["cash_after_trade"] == 99480.0
    assert row["realized_pnl_cumulative_after_trade"] == 80.0
    assert row["realized_pnl_by_symbol_after_trade"] == 80.0


def test_full_sell_generates_one_realized_row_and_zero_remaining():
    result = build_average_cost_realized_trade_journal(
        [
            _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -10, 110.0),
        ]
    )
    assert len(result.rows) == 1
    row = result.rows[0]
    assert row["shares_closed"] == 10
    assert row["realized_pnl"] == 100.0
    assert row["position_shares_after_sell"] == 0
    assert row["cash_after_trade"] == 100100.0


def test_multiple_buys_then_sell_uses_average_cost():
    result = build_average_cost_realized_trade_journal(
        [
            _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("buy2", "2026-05-02", "CPAY", "BUY", 6, 90.0),
            _make_trade("sell1", "2026-05-03", "CPAY", "SELL", -8, 110.0),
        ]
    )
    row = result.rows[0]
    assert row["entry_price_basis"] == 96.25
    assert row["avg_price_before_sell"] == 96.25
    assert row["realized_pnl"] == 110.0
    assert round(row["realized_return_pct"], 7) == round((110.0 / 96.25 - 1.0) * 100.0, 7)


def test_sell_then_remaining_shares_keep_same_average_cost():
    result = build_average_cost_realized_trade_journal(
        [
            _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -4, 120.0),
            _make_trade("sell2", "2026-05-03", "CPAY", "SELL", -2, 130.0),
        ]
    )
    assert len(result.rows) == 2
    first, second = result.rows
    assert first["position_shares_after_sell"] == 6
    assert second["position_shares_before_sell"] == 6
    assert second["avg_price_before_sell"] == 100.0
    assert second["realized_pnl"] == 60.0


def test_full_sell_removes_position_for_next_symbol_cycle():
    result = build_average_cost_realized_trade_journal(
        [
            _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -10, 110.0),
            _make_trade("buy2", "2026-05-03", "CPAY", "BUY", 5, 80.0),
            _make_trade("sell2", "2026-05-04", "CPAY", "SELL", -5, 100.0),
        ]
    )
    assert len(result.rows) == 2
    assert result.rows[0]["entry_price_basis"] == 100.0
    assert result.rows[1]["entry_price_basis"] == 80.0


def test_duplicate_trade_id_is_skipped_once():
    result = build_average_cost_realized_trade_journal(
        [
            _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -4, 120.0),
            _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -4, 120.0),
        ]
    )
    assert len(result.rows) == 1
    assert result.duplicate_skipped_count == 1
    assert any("Duplicate trade_id skipped" in warning for warning in result.warnings)


def test_sell_more_than_held_raises_error():
    with pytest.raises(ValueError, match="cannot SELL more shares than held"):
        build_average_cost_realized_trade_journal(
            [
                _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
                _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -11, 120.0),
            ]
        )


def test_sell_without_position_raises_error():
    with pytest.raises(ValueError, match="cannot SELL without an open position"):
        build_average_cost_realized_trade_journal(
            [_make_trade("sell1", "2026-05-02", "CPAY", "SELL", -4, 120.0)]
        )


def test_csv_includes_cost_basis_metadata_columns(tmp_path: Path):
    output_path = _paper_test_path("paper_realized_trade_journal_test", tmp_path, ".csv")
    try:
        result = build_average_cost_realized_trade_journal(
            [
                _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
                _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -4, 120.0),
            ]
        )
        write_realized_trade_journal(result.rows, output_path)
        with output_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert rows[0]["cost_basis_method"] == COST_BASIS_METHOD
        assert rows[0]["entry_basis_type"] == ENTRY_BASIS_TYPE
        assert rows[0]["lot_linking_status"] == LOT_LINKING_STATUS
    finally:
        _cleanup(output_path)


def test_open_date_and_holding_days_columns_are_not_generated():
    assert "open_date" not in REALIZED_TRADE_JOURNAL_COLUMNS
    assert "holding_days" not in REALIZED_TRADE_JOURNAL_COLUMNS


def test_summary_markdown_includes_limitations(tmp_path: Path):
    input_path = _paper_test_path("paper_execution_log_test", tmp_path, ".csv")
    output_csv_path = _paper_test_path("paper_realized_trade_journal_test", tmp_path, ".csv")
    summary_path = _paper_test_path("paper_realized_trade_journal_summary_test", tmp_path, ".md")
    try:
        rows = [
            _make_trade("buy1", "2026-05-01", "CPAY", "BUY", 10, 100.0),
            _make_trade("sell1", "2026-05-02", "CPAY", "SELL", -4, 120.0),
        ]
        _write_execution_log(input_path, rows)
        loaded_rows = load_paper_execution_rows(input_path)
        result = build_average_cost_realized_trade_journal(loaded_rows)
        write_realized_trade_journal(result.rows, output_csv_path)
        summary = summarize_realized_trade_journal(
            result.rows,
            input_path=input_path,
            output_path=output_csv_path,
            duplicate_skipped_count=result.duplicate_skipped_count,
            warnings=result.warnings,
        )
        markdown = render_realized_trade_journal_summary(summary)
        write_realized_trade_journal_summary(markdown, summary_path)
        assert "This journal is SELL-event based, not lot-matched closed trade accounting." in markdown
        assert "open_date and holding_days are intentionally excluded." in markdown
        assert "FIFO/LIFO/specific-lot accounting is not implemented." in markdown
        assert "entry_price_basis uses average cost immediately before each SELL." in markdown
        assert summary_path.exists()
    finally:
        _cleanup(input_path)
        _cleanup(output_csv_path)
        _cleanup(summary_path)
