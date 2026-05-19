from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_symbol_review_buckets import (
    PAPER_SYMBOL_REVIEW_BUCKET_COLUMNS,
    build_paper_symbol_review_buckets,
    load_paper_symbol_side_by_side_performance_rows,
    render_paper_symbol_review_buckets_summary,
    summarize_paper_symbol_review_buckets,
    write_paper_symbol_review_buckets,
    write_paper_symbol_review_buckets_summary,
)
from core.paths import PAPER_TEST_DIR


SIDE_BY_SIDE_COLUMNS = [
    "symbol",
    "symbol_status",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "realized_trade_count",
    "win_count",
    "loss_count",
    "flat_count",
    "win_rate",
    "avg_realized_return_pct",
    "open_shares",
    "open_market_value",
    "open_cost_basis",
    "open_unrealized_return_pct",
    "position_weight_market",
    "cost_basis_method",
    "entry_basis_type",
    "lot_linking_status",
    "snapshot_date",
    "realized_pnl_rank",
    "unrealized_pnl_rank",
    "total_pnl_rank",
    "total_pnl_contribution_pct",
    "risk_note",
]


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_symbol_review_buckets_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _row(
    symbol: str = "GEN",
    symbol_status: str = "unrealized_only",
    realized_pnl: str = "0.00",
    unrealized_pnl: str = "0.00",
    total_pnl: str = "0.00",
    realized_trade_count: str = "0",
    win_rate: str = "0.0000000",
    avg_realized_return_pct: str = "0.0000000",
    open_shares: str = "0",
    open_market_value: str = "0.00",
    open_unrealized_return_pct: str = "0.0000000",
    position_weight_market: str = "0.0000000",
) -> dict[str, str]:
    row = {column: "" for column in SIDE_BY_SIDE_COLUMNS}
    row.update(
        {
            "symbol": symbol,
            "symbol_status": symbol_status,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "realized_trade_count": realized_trade_count,
            "win_count": "0",
            "loss_count": "0",
            "flat_count": "0",
            "win_rate": win_rate,
            "avg_realized_return_pct": avg_realized_return_pct,
            "open_shares": open_shares,
            "open_market_value": open_market_value,
            "open_cost_basis": "0.00",
            "open_unrealized_return_pct": open_unrealized_return_pct,
            "position_weight_market": position_weight_market,
            "cost_basis_method": "average_cost",
            "entry_basis_type": "position_avg_price_before_sell",
            "lot_linking_status": "not_applicable",
            "snapshot_date": "2026-05-13",
            "realized_pnl_rank": "1",
            "unrealized_pnl_rank": "1",
            "total_pnl_rank": "1",
            "total_pnl_contribution_pct": "0.0000000",
            "risk_note": "",
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


def test_monitor_open_gain_classification():
    rows, _, _ = build_paper_symbol_review_buckets(
        [_row(open_shares="10", open_market_value="100.00", open_unrealized_return_pct="0.6000000")]
    )
    assert rows[0]["review_bucket"] == "monitor_open_gain"


def test_monitor_open_loss_classification():
    rows, _, _ = build_paper_symbol_review_buckets(
        [_row(open_shares="10", open_market_value="100.00", open_unrealized_return_pct="-0.6000000")]
    )
    assert rows[0]["review_bucket"] == "monitor_open_loss"


def test_review_loss_classification():
    rows, _, _ = build_paper_symbol_review_buckets(
        [_row(symbol_status="realized_only", realized_pnl="-100.00", total_pnl="-100.00", realized_trade_count="4", avg_realized_return_pct="-0.6000000")]
    )
    assert rows[0]["review_bucket"] == "review_loss"


def test_track_realized_gain_classification():
    rows, _, _ = build_paper_symbol_review_buckets(
        [_row(symbol_status="realized_only", realized_pnl="100.00", total_pnl="100.00", realized_trade_count="4", avg_realized_return_pct="0.6000000")]
    )
    assert rows[0]["review_bucket"] == "track_realized_gain"


def test_neutral_classification():
    rows, _, _ = build_paper_symbol_review_buckets(
        [_row(symbol_status="realized_only", realized_pnl="0.00", total_pnl="0.00", realized_trade_count="4", avg_realized_return_pct="0.1000000")]
    )
    assert rows[0]["review_bucket"] == "neutral"


def test_neutral_threshold_0_5_is_applied():
    rows, _, _ = build_paper_symbol_review_buckets(
        [_row(open_shares="10", open_market_value="100.00", open_unrealized_return_pct="0.5000000")]
    )
    assert rows[0]["review_bucket"] == "neutral"


def test_open_position_priority_over_realized():
    rows, _, _ = build_paper_symbol_review_buckets(
        [_row(symbol_status="realized_and_unrealized", realized_pnl="-100.00", unrealized_pnl="5.00", total_pnl="-95.00", realized_trade_count="4", avg_realized_return_pct="-1.0000000", open_shares="10", open_market_value="100.00", open_unrealized_return_pct="0.7000000")]
    )
    assert rows[0]["review_bucket"] == "monitor_open_gain"


def test_sample_size_flag_calculation():
    rows, _, warnings = build_paper_symbol_review_buckets(
        [
            _row(symbol="A", realized_trade_count="0"),
            _row(symbol="B", realized_trade_count="2"),
            _row(symbol="C", realized_trade_count="3"),
        ]
    )
    flags = {row["symbol"]: row["sample_size_flag"] for row in rows}
    assert flags["A"] == "no_realized_trades"
    assert flags["B"] == "low_sample"
    assert flags["C"] == "enough_sample"
    assert any("low_sample" in warning for warning in warnings)


def test_review_priority_calculation():
    rows, summary, _ = build_paper_symbol_review_buckets(
        [
            _row(symbol="A", symbol_status="realized_only", realized_pnl="-100.00", total_pnl="-100.00", realized_trade_count="4", avg_realized_return_pct="-0.6000000"),
            _row(symbol="B", open_shares="10", open_market_value="100.00", open_unrealized_return_pct="0.6000000"),
            _row(symbol="C"),
        ]
    )
    priorities = {row["symbol"]: row["review_priority"] for row in rows}
    assert priorities["A"] == "high"
    assert priorities["B"] == "medium"
    assert priorities["C"] == "low"
    assert summary["priority_counts"]["high"] == 1


def test_is_actionable_is_always_false():
    rows, _, _ = build_paper_symbol_review_buckets([_row()])
    assert rows[0]["is_actionable"] == "false"


def test_summary_contains_non_actionable_text():
    rows, summary_data, warnings = build_paper_symbol_review_buckets([_row()])
    assert rows
    summary = summarize_paper_symbol_review_buckets(summary_data, warnings, Path("in.csv"), Path("out.csv"))
    markdown = render_paper_symbol_review_buckets_summary(summary)
    assert "This is a non-actionable review classification report." in markdown
    assert "It does not recommend buy/sell/hold actions." in markdown
    assert "is_actionable: false" in markdown


def test_missing_required_columns_detected(tmp_path: Path):
    path = _paper_test_path("paper_symbol_side_by_side_performance_test", tmp_path, ".csv")
    try:
        _write_csv(path, ["symbol"], [{"symbol": "GEN"}])
        with pytest.raises(ValueError, match="Missing paper symbol side-by-side performance columns"):
            load_paper_symbol_side_by_side_performance_rows(path)
    finally:
        _cleanup(path)


def test_invalid_numeric_values_detected():
    with pytest.raises(ValueError, match="invalid numeric in realized_pnl"):
        build_paper_symbol_review_buckets([_row(realized_pnl="bad")])


def test_write_csv_contains_expected_columns(tmp_path: Path):
    output_csv_path = _paper_test_path("paper_symbol_review_buckets_test", tmp_path, ".csv")
    output_md_path = _paper_test_path("paper_symbol_review_buckets_test", tmp_path, ".md")
    try:
        rows, summary_data, warnings = build_paper_symbol_review_buckets([_row()])
        write_paper_symbol_review_buckets(rows, output_csv_path)
        summary = summarize_paper_symbol_review_buckets(summary_data, warnings, Path("in.csv"), output_csv_path)
        write_paper_symbol_review_buckets_summary(
            render_paper_symbol_review_buckets_summary(summary),
            output_md_path,
        )
        with output_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            written_rows = list(csv.DictReader(handle))
        assert list(written_rows[0].keys()) == PAPER_SYMBOL_REVIEW_BUCKET_COLUMNS
        assert output_md_path.exists()
    finally:
        _cleanup(output_csv_path)
        _cleanup(output_md_path)
