from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.generate_paper_equity_curve import (
    build_paper_equity_curve,
    generate_paper_equity_curve,
    load_account_snapshot,
)


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_equity_curve_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


ACCOUNT_COLUMNS = [
    "snapshot_date",
    "cash",
    "positions_cost_value",
    "total_equity_cost_basis",
    "positions_market_value",
    "total_equity_market_value",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "market_valuation_status",
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


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _account_row(**overrides: str) -> dict[str, str]:
    row = {
        "snapshot_date": "2026-05-12",
        "cash": "90.00",
        "positions_cost_value": "10.00",
        "total_equity_cost_basis": "100.00",
        "positions_market_value": "12.00",
        "total_equity_market_value": "102.00",
        "realized_pnl": "1.00",
        "unrealized_pnl": "1.00",
        "total_pnl": "2.00",
        "market_valuation_status": "success",
    }
    row.update(overrides)
    return row


def _position_row(**overrides: str) -> dict[str, str]:
    row = {
        "snapshot_date": "2026-05-12",
        "symbol": "AAA",
        "shares": "1",
        "avg_price": "10.00",
        "cost_value": "10.00",
        "close_price": "12.00",
        "market_value": "12.00",
        "unrealized_pnl": "1.00",
        "unrealized_pnl_pct": "0.1000000",
        "position_status": "OPEN",
    }
    row.update(overrides)
    return row


def test_build_paper_equity_curve_uses_market_and_cost_basis() -> None:
    rows = [
        _account_row(snapshot_date="2026-05-12", total_equity_market_value="102.00", total_equity_cost_basis="100.00"),
        _account_row(snapshot_date="2026-05-13", cash="95.00", positions_cost_value="9.00", total_equity_cost_basis="104.00", positions_market_value="15.00", total_equity_market_value="110.00"),
    ]

    curve_rows, warnings = build_paper_equity_curve(rows, {"2026-05-12": 1, "2026-05-13": 2})

    assert warnings == []
    assert curve_rows[0]["primary_equity"] == 102.0
    assert curve_rows[0]["secondary_equity"] == 100.0
    assert curve_rows[1]["primary_equity"] == 110.0
    assert curve_rows[1]["secondary_equity"] == 104.0
    assert curve_rows[1]["open_position_count"] == 2


def test_load_account_snapshot_sorts_dates_ascending(tmp_path: Path) -> None:
    account_path = tmp_path / "paper_account_snapshot.csv"
    _write_csv(
        account_path,
        ACCOUNT_COLUMNS,
        [
            _account_row(snapshot_date="2026-05-13"),
            _account_row(snapshot_date="2026-05-12"),
        ],
    )

    rows = load_account_snapshot(account_path)

    assert [row["snapshot_date"] for row in rows] == ["2026-05-12", "2026-05-13"]


def test_build_paper_equity_curve_calculates_returns_and_ratios() -> None:
    rows = [
        _account_row(snapshot_date="2026-05-12", cash="90.00", positions_market_value="10.00", total_equity_market_value="100.00", positions_cost_value="10.00", total_equity_cost_basis="100.00"),
        _account_row(snapshot_date="2026-05-13", cash="55.00", positions_market_value="55.00", total_equity_market_value="110.00", positions_cost_value="50.00", total_equity_cost_basis="105.00"),
    ]

    curve_rows, _ = build_paper_equity_curve(rows)

    assert curve_rows[1]["primary_return_from_start_pct"] == pytest.approx(10.0)
    assert curve_rows[1]["secondary_return_from_start_pct"] == pytest.approx(5.0)
    assert curve_rows[1]["cash_ratio_market"] == pytest.approx(0.5)
    assert curve_rows[1]["position_ratio_market"] == pytest.approx(0.5)


def test_build_paper_equity_curve_keeps_market_valuation_status() -> None:
    rows = [
        _account_row(snapshot_date="2026-05-12", market_valuation_status="partial"),
    ]

    curve_rows, warnings = build_paper_equity_curve(rows)

    assert curve_rows[0]["market_valuation_status"] == "partial"
    assert warnings == ["2026-05-12: market_valuation_status=partial"]


def test_load_account_snapshot_detects_duplicate_snapshot_date(tmp_path: Path) -> None:
    account_path = tmp_path / "paper_account_snapshot.csv"
    _write_csv(
        account_path,
        ACCOUNT_COLUMNS,
        [
            _account_row(snapshot_date="2026-05-12"),
            _account_row(snapshot_date="2026-05-12", cash="91.00"),
        ],
    )

    with pytest.raises(ValueError, match="Duplicate snapshot_date values"):
        load_account_snapshot(account_path)


def test_build_paper_equity_curve_detects_invalid_numeric() -> None:
    rows = [
        _account_row(total_equity_market_value="bad"),
    ]

    with pytest.raises(ValueError, match="invalid numeric in total_equity_market_value"):
        build_paper_equity_curve(rows)


def test_generate_paper_equity_curve_writes_csv(tmp_path: Path) -> None:
    account_path = tmp_path / "paper_account_snapshot.csv"
    position_path = tmp_path / "paper_position_snapshot.csv"
    output_path = tmp_path / "paper_equity_curve.csv"
    summary_path = tmp_path / "paper_equity_curve_summary.md"

    _write_csv(
        account_path,
        ACCOUNT_COLUMNS,
        [
            _account_row(snapshot_date="2026-05-12"),
            _account_row(snapshot_date="2026-05-13", total_equity_market_value="103.00", total_equity_cost_basis="101.00"),
        ],
    )
    _write_csv(
        position_path,
        POSITION_COLUMNS,
        [
            _position_row(snapshot_date="2026-05-12"),
            _position_row(snapshot_date="2026-05-13", symbol="BBB"),
        ],
    )

    result = generate_paper_equity_curve(
        account_snapshot_path=account_path,
        position_snapshot_path=position_path,
        output_path=output_path,
        summary_path=summary_path,
    )

    assert result["row_count"] == 2
    assert output_path.exists()
    rows = list(csv.DictReader(output_path.open("r", encoding="utf-8-sig", newline="")))
    assert len(rows) == 2
    assert rows[0]["primary_equity"] == "102.00"
    assert rows[0]["secondary_equity"] == "100.00"
    assert rows[1]["market_valuation_status"] == "success"
