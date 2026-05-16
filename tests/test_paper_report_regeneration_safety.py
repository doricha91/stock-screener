from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.check_paper_report_regeneration_safety import check_paper_report_regeneration_safety


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_report_regen_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_fixture(tmp_path: Path) -> tuple[Path, Path]:
    paper_root = tmp_path / "paper_test"
    reports_dir = paper_root / "reports"
    front_root = tmp_path / "front_test"

    _write_csv(
        paper_root / "paper_execution_log.csv",
        ["trade_id", "date", "regime", "symbol", "side", "shares", "price", "gross_amount", "source", "status", "reason", "notes", "rec_shares", "rec_price", "created_at"],
        [
            {
                "trade_id": "t1",
                "date": "2026-05-13",
                "regime": "BULL",
                "symbol": "GEN",
                "side": "BUY",
                "shares": "440",
                "price": "22.68",
                "gross_amount": "9979.20",
                "source": "paper_virtual_fill",
                "status": "FILLED",
                "reason": "",
                "notes": "",
                "rec_shares": "440",
                "rec_price": "22.68",
                "created_at": "2026-05-13T16:00:00",
            }
        ],
    )
    _write_csv(
        paper_root / "paper_account_snapshot.csv",
        [
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
        ],
        [
            {
                "snapshot_date": "2026-05-13",
                "cash": "60344.67",
                "positions_cost_value": "39042.79",
                "total_equity_cost_basis": "99387.46",
                "positions_market_value": "39322.39",
                "total_equity_market_value": "99667.06",
                "realized_pnl": "-612.54",
                "unrealized_pnl": "279.60",
                "total_pnl": "-332.94",
                "market_valuation_status": "success",
            }
        ],
    )
    _write_csv(
        paper_root / "paper_position_snapshot.csv",
        [
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
        ],
        [
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
        ],
    )
    _write_csv(
        reports_dir / "paper_equity_curve.csv",
        [
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
        ],
        [
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
                "open_position_count": "1",
            }
        ],
    )
    _write_csv(
        reports_dir / "paper_drawdown.csv",
        [
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
        ],
        [
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
        ],
    )
    _write_text(reports_dir / "paper_performance_input_audit.md", "# Paper Performance Input Audit\n\n- Generated at: first\n- Proceed to PAPER8-2: Yes\n")
    _write_text(reports_dir / "paper_equity_curve_summary.md", "# Equity Summary\n")
    _write_text(reports_dir / "paper_drawdown_summary.md", "# Drawdown Summary\n")
    _write_text(reports_dir / "paper_performance_summary.md", "# Current Summary\n")
    _write_text(paper_root / "paper_performance_summary.md", "# Deprecated Root Summary\n")
    _write_text(front_root / "keep.txt", "front-test untouched\n")
    return paper_root, front_root


def _runner_factory(paper_root: Path):
    reports_dir = paper_root / "reports"

    def runner() -> list[str]:
        _write_text(
            reports_dir / "paper_performance_input_audit.md",
            "# Paper Performance Input Audit\n\n- Generated at: second\n- Proceed to PAPER8-2: Yes\n",
        )
        _write_text(reports_dir / "paper_equity_curve_summary.md", "# Equity Summary rewritten\n")
        _write_text(reports_dir / "paper_drawdown_summary.md", "# Drawdown Summary rewritten\n")
        _write_text(reports_dir / "paper_performance_summary.md", "# Performance Summary rewritten\n")
        return [
            "python scripts/audit_paper_performance_inputs.py",
            "python scripts/generate_paper_equity_curve.py",
            "python scripts/generate_paper_drawdown.py",
            "python scripts/generate_paper_performance_summary.py",
        ]

    return runner


def test_check_paper_report_regeneration_safety_protects_sources_and_front_test(tmp_path: Path) -> None:
    paper_root, front_root = _build_fixture(tmp_path)
    result = check_paper_report_regeneration_safety(
        paper_root=paper_root,
        front_root=front_root,
        runner=_runner_factory(paper_root),
    )
    assert result["source_hashes_unchanged"] is True
    assert result["front_test_unchanged"] is True
    assert result["summary_metrics_consistent"] is True
    assert result["report_hashes_consistent"] is True
    assert result["deprecated_root_summary_exists"] is True
    assert result["issues"] == []
    assert any("Deprecated root report exists" in warning for warning in result["warnings"])
    assert (paper_root / "reports" / "paper_report_regeneration_safety.md").exists()


def test_check_paper_report_regeneration_safety_reports_missing_official_file(tmp_path: Path) -> None:
    paper_root, front_root = _build_fixture(tmp_path)
    (paper_root / "reports" / "paper_drawdown.csv").unlink()
    result = check_paper_report_regeneration_safety(
        paper_root=paper_root,
        front_root=front_root,
        runner=_runner_factory(paper_root),
    )
    assert any("Missing official report files" in issue for issue in result["issues"])
