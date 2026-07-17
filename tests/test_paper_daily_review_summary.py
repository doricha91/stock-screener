from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_daily_review_summary import (
    REQUIRED_REVIEW_BUCKET_COLUMNS,
    REQUIRED_SIDE_BY_SIDE_COLUMNS,
    build_paper_daily_review_summary_data,
    load_csv_rows,
    render_paper_daily_review_summary,
    render_paper_report_index,
    summarize_paper_daily_review_summary,
    write_markdown,
)
from core.paths import PAPER_TEST_DIR


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_daily_review_summary_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _paper_test_path(prefix: str, tmp_path: Path, suffix: str) -> Path:
    return PAPER_TEST_DIR / f"{prefix}_{tmp_path.name}{suffix}"


def _cleanup(path: Path) -> None:
    if path.exists():
        path.unlink()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _performance_summary_text() -> str:
    return """# Paper Performance Summary

## Summary
- Latest Snapshot Date: 2026-05-13
- Primary Equity: $99,667.06
- Cash: $60,344.67
- Cash Ratio: 60.55%

## PnL Summary
- Realized PnL: $-612.54
- Unrealized PnL: $279.60
- Total PnL: $-332.94

## Allocation Summary
- Cash: $60,344.67
- Position Ratio Market: 39.45%
"""


def _side_row(symbol: str, status: str, realized: str, unrealized: str, total: str) -> dict[str, str]:
    row = {column: "" for column in REQUIRED_SIDE_BY_SIDE_COLUMNS + [
        "realized_trade_count","win_count","loss_count","flat_count","win_rate","avg_realized_return_pct",
        "open_shares","open_market_value","open_cost_basis","open_unrealized_return_pct","position_weight_market",
        "cost_basis_method","entry_basis_type","lot_linking_status","snapshot_date","realized_pnl_rank",
        "unrealized_pnl_rank","total_pnl_rank","total_pnl_contribution_pct","risk_note"
    ]}
    row.update(
        {
            "symbol": symbol,
            "symbol_status": status,
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": total,
        }
    )
    return row


def _bucket_row(symbol: str, bucket: str, priority: str, sample: str) -> dict[str, str]:
    row = {column: "" for column in REQUIRED_REVIEW_BUCKET_COLUMNS + [
        "symbol_status","is_actionable","review_reason","realized_pnl","unrealized_pnl","total_pnl",
        "realized_trade_count","win_rate","avg_realized_return_pct","open_shares","open_market_value",
        "open_unrealized_return_pct","position_weight_market","neutral_threshold_pct"
    ]}
    row.update(
        {
            "symbol": symbol,
            "review_bucket": bucket,
            "review_priority": priority,
            "sample_size_flag": sample,
        }
    )
    return row


def test_daily_review_summary_markdown_and_report_index_generation(tmp_path: Path):
    performance_path = _paper_test_path("paper_performance_summary_test", tmp_path, ".md")
    side_path = _paper_test_path("paper_symbol_side_by_side_performance_test", tmp_path, ".csv")
    bucket_path = _paper_test_path("paper_symbol_review_buckets_test", tmp_path, ".csv")
    worksheet_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".md")
    daily_path = _paper_test_path("paper_daily_review_summary_test", tmp_path, ".md")
    index_path = _paper_test_path("paper_report_index_test", tmp_path, ".md")
    try:
        _write_text(performance_path, _performance_summary_text())
        _write_csv(
            side_path,
            list((_side_row("GEN", "unrealized_only", "0.00", "268.40", "268.40")).keys()),
            [
                _side_row("GEN", "unrealized_only", "0.00", "268.40", "268.40"),
                _side_row("CF", "realized_only", "-366.75", "0.00", "-366.75"),
            ],
        )
        _write_csv(
            bucket_path,
            list((_bucket_row("GEN", "monitor_open_gain", "medium", "no_realized_trades")).keys()),
            [
                _bucket_row("GEN", "monitor_open_gain", "medium", "no_realized_trades"),
                _bucket_row("CF", "review_loss", "high", "low_sample"),
            ],
        )
        _write_text(worksheet_path, "# Worksheet")

        side_rows = load_csv_rows(side_path, REQUIRED_SIDE_BY_SIDE_COLUMNS, "paper_symbol_side_by_side_performance.csv")
        bucket_rows = load_csv_rows(bucket_path, REQUIRED_REVIEW_BUCKET_COLUMNS, "paper_symbol_review_buckets.csv")
        summary_data, warnings, report_rows = build_paper_daily_review_summary_data(
            performance_path, side_rows, bucket_rows, worksheet_path
        )
        summary = summarize_paper_daily_review_summary(summary_data, warnings)
        daily_markdown = render_paper_daily_review_summary(summary)
        index_markdown = render_paper_report_index(report_rows)
        write_markdown(daily_path, daily_markdown)
        write_markdown(index_path, index_markdown)

        assert "## Account Summary" in daily_markdown
        assert "## Symbol Side-by-Side Summary" in daily_markdown
        assert "## Review Bucket Summary" in daily_markdown
        assert "## Review Worksheet Pointers" in daily_markdown
        assert "## Report Index" in daily_markdown
        assert "Paper Report Index" in index_markdown
        assert daily_path.exists()
        assert index_path.exists()
    finally:
        for path in [performance_path, side_path, bucket_path, worksheet_path, daily_path, index_path]:
            _cleanup(path)


def test_side_by_side_summary_values_and_high_priority_symbols_are_shown(tmp_path: Path):
    performance_path = _paper_test_path("paper_performance_summary_test", tmp_path, ".md")
    side_path = _paper_test_path("paper_symbol_side_by_side_performance_test", tmp_path, ".csv")
    bucket_path = _paper_test_path("paper_symbol_review_buckets_test", tmp_path, ".csv")
    worksheet_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".md")
    try:
        _write_text(performance_path, _performance_summary_text())
        _write_csv(
            side_path,
            list((_side_row("GEN", "unrealized_only", "0.00", "268.40", "268.40")).keys()),
            [
                _side_row("GEN", "unrealized_only", "0.00", "268.40", "268.40"),
                _side_row("CF", "realized_only", "-366.75", "0.00", "-366.75"),
            ],
        )
        _write_csv(
            bucket_path,
            list((_bucket_row("GEN", "monitor_open_gain", "medium", "no_realized_trades")).keys()),
            [
                _bucket_row("GEN", "monitor_open_gain", "medium", "no_realized_trades"),
                _bucket_row("CF", "review_loss", "high", "low_sample"),
            ],
        )
        _write_text(worksheet_path, "# Worksheet")
        side_rows = load_csv_rows(side_path, REQUIRED_SIDE_BY_SIDE_COLUMNS, "paper_symbol_side_by_side_performance.csv")
        bucket_rows = load_csv_rows(bucket_path, REQUIRED_REVIEW_BUCKET_COLUMNS, "paper_symbol_review_buckets.csv")
        summary_data, warnings, _ = build_paper_daily_review_summary_data(
            performance_path, side_rows, bucket_rows, worksheet_path
        )
        summary = summarize_paper_daily_review_summary(summary_data, warnings)
        markdown = render_paper_daily_review_summary(summary)
        assert "- Symbol count: 2" in markdown
        assert "- Total realized PnL: -366.75" in markdown
        assert "- Total unrealized PnL: 268.40" in markdown
        assert "- high priority symbols: CF" in markdown
        assert "- Worksheet path:" in markdown
    finally:
        for path in [performance_path, side_path, bucket_path, worksheet_path]:
            _cleanup(path)


def test_no_action_daily_review_supports_empty_symbol_reports(tmp_path: Path):
    performance_path = _paper_test_path("paper_performance_summary_empty", tmp_path, ".md")
    side_path = _paper_test_path("paper_symbol_side_by_side_empty", tmp_path, ".csv")
    bucket_path = _paper_test_path("paper_symbol_review_buckets_empty", tmp_path, ".csv")
    worksheet_path = _paper_test_path("paper_symbol_review_worksheet_empty", tmp_path, ".md")
    try:
        _write_text(performance_path, _performance_summary_text())
        _write_csv(side_path, REQUIRED_SIDE_BY_SIDE_COLUMNS, [])
        _write_csv(bucket_path, REQUIRED_REVIEW_BUCKET_COLUMNS, [])
        _write_text(worksheet_path, "# Empty worksheet\n")
        side_rows = load_csv_rows(side_path, REQUIRED_SIDE_BY_SIDE_COLUMNS, "paper_symbol_side_by_side_performance.csv")
        bucket_rows = load_csv_rows(bucket_path, REQUIRED_REVIEW_BUCKET_COLUMNS, "paper_symbol_review_buckets.csv")

        summary_data, warnings, _ = build_paper_daily_review_summary_data(
            performance_path, side_rows, bucket_rows, worksheet_path
        )
        markdown = render_paper_daily_review_summary(
            summarize_paper_daily_review_summary(summary_data, warnings)
        )

        assert "- Symbol count: 0" in markdown
        assert "## Account Summary" in markdown
    finally:
        for path in [performance_path, side_path, bucket_path, worksheet_path]:
            _cleanup(path)


def test_non_actionable_and_limitations_are_included(tmp_path: Path):
    performance_path = _paper_test_path("paper_performance_summary_test", tmp_path, ".md")
    side_path = _paper_test_path("paper_symbol_side_by_side_performance_test", tmp_path, ".csv")
    bucket_path = _paper_test_path("paper_symbol_review_buckets_test", tmp_path, ".csv")
    worksheet_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".md")
    try:
        _write_text(performance_path, _performance_summary_text())
        _write_csv(side_path, list((_side_row("GEN", "unrealized_only", "0.00", "268.40", "268.40")).keys()), [_side_row("GEN", "unrealized_only", "0.00", "268.40", "268.40")])
        _write_csv(bucket_path, list((_bucket_row("GEN", "monitor_open_gain", "medium", "no_realized_trades")).keys()), [_bucket_row("GEN", "monitor_open_gain", "medium", "no_realized_trades")])
        _write_text(worksheet_path, "# Worksheet")
        side_rows = load_csv_rows(side_path, REQUIRED_SIDE_BY_SIDE_COLUMNS, "paper_symbol_side_by_side_performance.csv")
        bucket_rows = load_csv_rows(bucket_path, REQUIRED_REVIEW_BUCKET_COLUMNS, "paper_symbol_review_buckets.csv")
        summary_data, warnings, report_rows = build_paper_daily_review_summary_data(
            performance_path, side_rows, bucket_rows, worksheet_path
        )
        summary = summarize_paper_daily_review_summary(summary_data, warnings)
        daily_markdown = render_paper_daily_review_summary(summary)
        index_markdown = render_paper_report_index(report_rows)
        assert "This report is non-actionable." in daily_markdown
        assert "It does not recommend buy/sell/hold actions." in daily_markdown
        assert "## Limitations" in daily_markdown
        assert "## 1. Final / operator-facing reports" in index_markdown
        assert "## 5. Review / worksheet reports" in index_markdown
    finally:
        for path in [performance_path, side_path, bucket_path, worksheet_path]:
            _cleanup(path)


def test_missing_required_input_raises_error(tmp_path: Path):
    missing_path = _paper_test_path("paper_missing_test", tmp_path, ".csv")
    try:
        with pytest.raises(FileNotFoundError):
            load_csv_rows(missing_path, REQUIRED_SIDE_BY_SIDE_COLUMNS, "paper_symbol_side_by_side_performance.csv")
    finally:
        _cleanup(missing_path)


def test_original_report_csv_is_not_modified(tmp_path: Path):
    performance_path = _paper_test_path("paper_performance_summary_test", tmp_path, ".md")
    side_path = _paper_test_path("paper_symbol_side_by_side_performance_test", tmp_path, ".csv")
    bucket_path = _paper_test_path("paper_symbol_review_buckets_test", tmp_path, ".csv")
    worksheet_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".md")
    try:
        _write_text(performance_path, _performance_summary_text())
        _write_csv(side_path, list((_side_row("GEN", "unrealized_only", "0.00", "268.40", "268.40")).keys()), [_side_row("GEN", "unrealized_only", "0.00", "268.40", "268.40")])
        _write_csv(bucket_path, list((_bucket_row("GEN", "monitor_open_gain", "medium", "no_realized_trades")).keys()), [_bucket_row("GEN", "monitor_open_gain", "medium", "no_realized_trades")])
        _write_text(worksheet_path, "# Worksheet")
        before = side_path.read_text(encoding="utf-8-sig")
        side_rows = load_csv_rows(side_path, REQUIRED_SIDE_BY_SIDE_COLUMNS, "paper_symbol_side_by_side_performance.csv")
        bucket_rows = load_csv_rows(bucket_path, REQUIRED_REVIEW_BUCKET_COLUMNS, "paper_symbol_review_buckets.csv")
        build_paper_daily_review_summary_data(performance_path, side_rows, bucket_rows, worksheet_path)
        after = side_path.read_text(encoding="utf-8-sig")
        assert before == after
    finally:
        for path in [performance_path, side_path, bucket_path, worksheet_path]:
            _cleanup(path)
