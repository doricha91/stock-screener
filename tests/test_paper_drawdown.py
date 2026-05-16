from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.generate_paper_drawdown import (
    build_paper_drawdown,
    generate_paper_drawdown,
    load_equity_curve,
    summarize_drawdown,
)


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_drawdown_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


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


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EQUITY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _row(
    snapshot_date: str,
    primary_equity: str,
    secondary_equity: str,
    market_valuation_status: str = "success",
) -> dict[str, str]:
    return {
        "snapshot_date": snapshot_date,
        "primary_equity": primary_equity,
        "secondary_equity": secondary_equity,
        "cash": "",
        "positions_market_value": "",
        "positions_cost_value": "",
        "realized_pnl": "",
        "unrealized_pnl": "",
        "total_pnl": "",
        "market_valuation_status": market_valuation_status,
        "primary_return_from_start_pct": "",
        "secondary_return_from_start_pct": "",
        "cash_ratio_market": "",
        "position_ratio_market": "",
        "open_position_count": "",
    }


def test_build_paper_drawdown_calculates_peaks_drawdowns_and_mdd() -> None:
    rows = [
        _row("2026-05-01", "100", "100"),
        _row("2026-05-02", "110", "108"),
        _row("2026-05-03", "105", "103"),
        _row("2026-05-04", "120", "109"),
        _row("2026-05-05", "90", "95"),
    ]

    drawdown_rows, warnings = build_paper_drawdown(rows)
    summary = summarize_drawdown(drawdown_rows, warnings)

    assert warnings == []
    assert [row["primary_peak_equity"] for row in drawdown_rows] == [100.0, 110.0, 110.0, 120.0, 120.0]
    assert [row["primary_drawdown"] for row in drawdown_rows] == [0.0, 0.0, -5.0, 0.0, -30.0]
    assert drawdown_rows[0]["primary_drawdown_pct"] == pytest.approx(0.0)
    assert drawdown_rows[-1]["primary_drawdown_pct"] == pytest.approx(-25.0)
    assert drawdown_rows[0]["secondary_drawdown_pct"] == pytest.approx(0.0)
    assert summary["primary_mdd_pct"] == pytest.approx(-25.0)


def test_build_paper_drawdown_keeps_market_status_and_warnings() -> None:
    rows = [_row("2026-05-01", "100", "100", market_valuation_status="partial")]

    drawdown_rows, warnings = build_paper_drawdown(rows)

    assert drawdown_rows[0]["market_valuation_status"] == "partial"
    assert warnings == ["2026-05-01: market_valuation_status=partial"]


def test_load_equity_curve_sorts_dates_ascending(tmp_path: Path) -> None:
    path = tmp_path / "paper_equity_curve.csv"
    _write_csv(
        path,
        [
            _row("2026-05-03", "105", "103"),
            _row("2026-05-01", "100", "100"),
        ],
    )

    rows = load_equity_curve(path)

    assert [row["snapshot_date"] for row in rows] == ["2026-05-01", "2026-05-03"]


def test_load_equity_curve_detects_duplicate_snapshot_date(tmp_path: Path) -> None:
    path = tmp_path / "paper_equity_curve.csv"
    _write_csv(
        path,
        [
            _row("2026-05-01", "100", "100"),
            _row("2026-05-01", "101", "101"),
        ],
    )

    with pytest.raises(ValueError, match="Duplicate snapshot_date values"):
        load_equity_curve(path)


def test_build_paper_drawdown_detects_invalid_numeric() -> None:
    rows = [_row("2026-05-01", "bad", "100")]

    with pytest.raises(ValueError, match="invalid numeric in primary_equity"):
        build_paper_drawdown(rows)


def test_generate_paper_drawdown_writes_outputs(tmp_path: Path) -> None:
    equity_curve_path = tmp_path / "paper_equity_curve.csv"
    output_path = tmp_path / "paper_drawdown.csv"
    summary_path = tmp_path / "paper_drawdown_summary.md"
    _write_csv(
        equity_curve_path,
        [
            _row("2026-05-01", "100", "100"),
            _row("2026-05-02", "110", "108"),
            _row("2026-05-03", "105", "103"),
        ],
    )

    result = generate_paper_drawdown(
        equity_curve_path=equity_curve_path,
        output_path=output_path,
        summary_path=summary_path,
    )

    assert result["row_count"] == 3
    assert output_path.exists()
    assert summary_path.exists()
    rows = list(csv.DictReader(output_path.open("r", encoding="utf-8-sig", newline="")))
    assert len(rows) == 3
    assert rows[0]["primary_drawdown"] == "0.00"
    assert rows[2]["market_valuation_status"] == "success"
    assert rows[2]["primary_mdd_to_date_pct"] == "-4.5454545"
