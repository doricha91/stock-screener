from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_performance_summary import (
    build_paper_performance_summary,
    load_latest_position_snapshot_rows,
    load_paper_account_snapshots,
    load_paper_drawdown,
    load_paper_equity_curve,
    render_paper_performance_summary_markdown,
    write_paper_performance_summary,
)
from core.paths import PAPER_TEST_DIR


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_performance_summary_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


SNAPSHOT_COLUMNS = [
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

EQUITY_COLUMNS = [
    "snapshot_date",
    "primary_equity",
    "secondary_equity",
    "cash",
    "positions_market_value",
    "positions_cost_value",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "market_valuation_status",
    "primary_return_from_start_pct",
    "secondary_return_from_start_pct",
    "cash_ratio_market",
    "position_ratio_market",
    "open_position_count",
]

DRAWDOWN_COLUMNS = [
    "snapshot_date",
    "primary_equity",
    "primary_peak_equity",
    "primary_drawdown",
    "primary_drawdown_pct",
    "secondary_equity",
    "secondary_peak_equity",
    "secondary_drawdown",
    "secondary_drawdown_pct",
    "market_valuation_status",
    "is_primary_new_peak",
    "is_secondary_new_peak",
    "primary_mdd_to_date_pct",
    "secondary_mdd_to_date_pct",
]

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
    "position_status",
]


def _paper_path(prefix: str, tmp_path: Path, suffix: str) -> Path:
    return PAPER_TEST_DIR / f"{prefix}_{tmp_path.name}{suffix}"


def _cleanup(path: Path) -> None:
    if path.exists():
        path.unlink()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _snapshot_row(**overrides) -> dict[str, str]:
    row = {column: "" for column in SNAPSHOT_COLUMNS}
    row.update(
        {
            "snapshot_date": "2026-05-13",
            "currency": "USD",
            "initial_cash": "100000.00",
            "cash": "60344.67",
            "positions_cost_value": "39042.79",
            "total_equity_cost_basis": "99387.46",
            "cash_ratio_cost_basis": "0.6071658",
            "position_count": "3",
            "symbols": "BRK-B|F|GEN",
            "applied_trade_count": "10",
            "valuation_method": "db_daily_price_close",
            "source_execution_log": "outputs/paper_test/paper_execution_log.csv",
            "source_current_state": "outputs/paper_test/paper_current_state_20260513.json",
            "created_at": "2026-05-14T18:11:11",
            "positions_market_value": "39322.39",
            "total_equity_market_value": "99667.06",
            "cash_ratio_market_value": "0.6054625",
            "unrealized_pnl": "279.60",
            "unrealized_pnl_pct": "0.0071614",
            "realized_pnl": "-612.54",
            "realized_pnl_by_symbol": "{\"CF\": -366.75}",
            "total_pnl": "-332.94",
            "total_pnl_pct": "-0.0033294",
            "market_valuation_status": "success",
            "market_valuation_error": "",
            "valuation_price_date": "2026-05-13",
            "valuation_price_dates": "{\"BRK-B\": \"2026-05-13\"}",
            "price_staleness_days": "{\"BRK-B\": 0}",
            "max_price_staleness_days": "0",
        }
    )
    row.update(overrides)
    return row


def _equity_row(**overrides) -> dict[str, str]:
    row = {column: "" for column in EQUITY_COLUMNS}
    row.update(
        {
            "snapshot_date": "2026-05-13",
            "primary_equity": "99667.06",
            "secondary_equity": "99387.46",
            "cash": "60344.67",
            "positions_market_value": "39322.39",
            "positions_cost_value": "39042.79",
            "realized_pnl": "-612.54",
            "unrealized_pnl": "279.60",
            "total_pnl": "-332.94",
            "market_valuation_status": "success",
            "primary_return_from_start_pct": "-0.33",
            "secondary_return_from_start_pct": "-0.61",
            "cash_ratio_market": "0.6054625",
            "position_ratio_market": "0.3945375",
            "open_position_count": "3",
        }
    )
    row.update(overrides)
    return row


def _drawdown_row(**overrides) -> dict[str, str]:
    row = {column: "" for column in DRAWDOWN_COLUMNS}
    row.update(
        {
            "snapshot_date": "2026-05-13",
            "primary_equity": "99667.06",
            "primary_peak_equity": "100000.00",
            "primary_drawdown": "-332.94",
            "primary_drawdown_pct": "-0.3329400",
            "secondary_equity": "99387.46",
            "secondary_peak_equity": "100000.00",
            "secondary_drawdown": "-612.54",
            "secondary_drawdown_pct": "-0.6125400",
            "market_valuation_status": "success",
            "is_primary_new_peak": "N",
            "is_secondary_new_peak": "N",
            "primary_mdd_to_date_pct": "-0.5273900",
            "secondary_mdd_to_date_pct": "-0.6125400",
        }
    )
    row.update(overrides)
    return row


def _position_row(**overrides) -> dict[str, str]:
    row = {column: "" for column in POSITION_COLUMNS}
    row.update(
        {
            "snapshot_date": "2026-05-13",
            "symbol": "GEN",
            "shares": "440",
            "avg_price": "22.68",
            "cost_value": "9979.20",
            "close_price": "23.29",
            "market_value": "10247.60",
            "unrealized_pnl": "268.40",
            "unrealized_pnl_pct": "0.0268960",
            "position_status": "OPEN",
        }
    )
    row.update(overrides)
    return row


def _build_summary(snapshot_path: Path, equity_path: Path, drawdown_path: Path, position_path: Path) -> dict[str, str]:
    return build_paper_performance_summary(
        load_paper_equity_curve(equity_path),
        load_paper_drawdown(drawdown_path),
        load_paper_account_snapshots(snapshot_path),
        *load_latest_position_snapshot_rows(position_path),
    )


def test_latest_snapshot_summary_selects_latest_row(tmp_path):
    snapshot_path = _paper_path("paper_account_snapshot_test", tmp_path, ".csv")
    equity_path = _paper_path("paper_equity_curve_test", tmp_path, ".csv")
    drawdown_path = _paper_path("paper_drawdown_test", tmp_path, ".csv")
    position_path = _paper_path("paper_position_snapshot_test", tmp_path, ".csv")
    try:
        _write_csv(snapshot_path, SNAPSHOT_COLUMNS, [_snapshot_row(snapshot_date="2026-05-12"), _snapshot_row(snapshot_date="2026-05-13")])
        _write_csv(equity_path, EQUITY_COLUMNS, [_equity_row(snapshot_date="2026-05-12"), _equity_row(snapshot_date="2026-05-13")])
        _write_csv(drawdown_path, DRAWDOWN_COLUMNS, [_drawdown_row(snapshot_date="2026-05-12"), _drawdown_row(snapshot_date="2026-05-13")])
        _write_csv(position_path, POSITION_COLUMNS, [_position_row(snapshot_date="2026-05-13")])
        summary = _build_summary(snapshot_path, equity_path, drawdown_path, position_path)
        assert summary["first_snapshot_date"] == "2026-05-12"
        assert summary["latest_snapshot_date"] == "2026-05-13"
        assert summary["snapshot_count"] == 2
        assert summary["account_latest"]["total_pnl"] == "-332.94"
    finally:
        _cleanup(snapshot_path)
        _cleanup(equity_path)
        _cleanup(drawdown_path)
        _cleanup(position_path)


def test_render_paper_performance_summary_success(tmp_path):
    snapshot_path = _paper_path("paper_account_snapshot_test", tmp_path, ".csv")
    equity_path = _paper_path("paper_equity_curve_test", tmp_path, ".csv")
    drawdown_path = _paper_path("paper_drawdown_test", tmp_path, ".csv")
    position_path = _paper_path("paper_position_snapshot_test", tmp_path, ".csv")
    output_path = _paper_path("paper_performance_summary_test", tmp_path, ".md")
    try:
        _write_csv(snapshot_path, SNAPSHOT_COLUMNS, [_snapshot_row()])
        _write_csv(equity_path, EQUITY_COLUMNS, [_equity_row()])
        _write_csv(drawdown_path, DRAWDOWN_COLUMNS, [_drawdown_row()])
        _write_csv(position_path, POSITION_COLUMNS, [_position_row(), _position_row(symbol="F", shares="1427", avg_price="13.57", cost_value="19364.39", close_price="13.57", market_value="19364.39", unrealized_pnl="-0.00", unrealized_pnl_pct="-0.0000000")])
        original_snapshot = snapshot_path.read_text(encoding="utf-8-sig")
        summary = _build_summary(snapshot_path, equity_path, drawdown_path, position_path)
        markdown = render_paper_performance_summary_markdown(summary)
        write_paper_performance_summary(markdown, output_path)
        assert "Primary Equity: $99,667.06" in markdown
        assert "Secondary Equity: $99,387.46" in markdown
        assert "Primary Return From Start: -0.33%" in markdown
        assert "| Primary MDD | -0.33% |" in markdown
        assert "Realized PnL: $-612.54" in markdown
        assert "Unrealized PnL: $279.60" in markdown
        assert "Cash Ratio Market: 60.55%" in markdown
        assert "| GEN | 440 | $22.68 | $23.29 | $9,979.20 | $10,247.60 | $268.40 | 2.69% |" in markdown
        assert "| F | 1,427 | $13.57 | $13.57 | $19,364.39 | $19,364.39 | $-0.00 | -0.00% |" in markdown
        assert snapshot_path.read_text(encoding="utf-8-sig") == original_snapshot
        assert output_path.exists()
    finally:
        _cleanup(snapshot_path)
        _cleanup(equity_path)
        _cleanup(drawdown_path)
        _cleanup(position_path)
        _cleanup(output_path)


def test_render_paper_performance_summary_failed_valuation(tmp_path):
    snapshot_path = _paper_path("paper_account_snapshot_test", tmp_path, ".csv")
    equity_path = _paper_path("paper_equity_curve_test", tmp_path, ".csv")
    drawdown_path = _paper_path("paper_drawdown_test", tmp_path, ".csv")
    position_path = _paper_path("paper_position_snapshot_test", tmp_path, ".csv")
    try:
        _write_csv(snapshot_path, SNAPSHOT_COLUMNS, [_snapshot_row(market_valuation_status="failed", total_equity_market_value="", unrealized_pnl="", total_pnl="")])
        _write_csv(equity_path, EQUITY_COLUMNS, [_equity_row(market_valuation_status="failed", primary_equity="", positions_market_value="", unrealized_pnl="", total_pnl="")])
        _write_csv(drawdown_path, DRAWDOWN_COLUMNS, [_drawdown_row(market_valuation_status="failed")])
        _write_csv(position_path, POSITION_COLUMNS, [_position_row()])
        summary = _build_summary(snapshot_path, equity_path, drawdown_path, position_path)
        markdown = render_paper_performance_summary_markdown(summary)
        assert "Latest market_valuation_status is not success: failed" in markdown
        assert "Market Valuation Status: failed" in markdown
        assert "Primary Equity: N/A" in markdown
    finally:
        _cleanup(snapshot_path)
        _cleanup(equity_path)
        _cleanup(drawdown_path)
        _cleanup(position_path)


def test_missing_input_file_raises_file_not_found(tmp_path):
    snapshot_path = _paper_path("paper_missing_test", tmp_path, ".csv")
    try:
        with pytest.raises(FileNotFoundError):
            load_paper_equity_curve(snapshot_path)
    finally:
        _cleanup(snapshot_path)
