from __future__ import annotations

import csv
from pathlib import Path

from core.paper_account_paths import build_paper_account_paths
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from scripts.generate_paper_daily_review_summary import generate_paper_daily_review_summary
from scripts.generate_paper_drawdown import generate_paper_drawdown_for_account
from scripts.generate_paper_equity_curve import generate_paper_equity_curve_for_account
from scripts.generate_paper_performance_summary import generate_paper_performance_summary
from scripts.generate_paper_realized_ranking_report import generate_paper_realized_ranking_report
from scripts.generate_paper_realized_trade_journal import generate_paper_realized_trade_journal
from scripts.generate_paper_symbol_realized_performance import generate_paper_symbol_realized_performance
from scripts.generate_paper_symbol_review_buckets import generate_paper_symbol_review_buckets
from scripts.generate_paper_symbol_review_worksheet import generate_paper_symbol_review_worksheet
from scripts.generate_paper_symbol_side_by_side_performance import generate_paper_symbol_side_by_side_performance
from scripts.generate_paper_symbol_unrealized_performance import generate_paper_symbol_unrealized_performance


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_non_default_reports_chain_writes_only_under_account_root(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_growth",
        account_root=tmp_path / "paper_accounts" / "paper_growth",
        allow_legacy_default=False,
        create=True,
    )
    _write_csv(
        account_paths.account_snapshot_path,
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
                "snapshot_date": "2026-05-30",
                "cash": "50000.00",
                "positions_cost_value": "50000.00",
                "total_equity_cost_basis": "100000.00",
                "positions_market_value": "52000.00",
                "total_equity_market_value": "102000.00",
                "realized_pnl": "1000.00",
                "unrealized_pnl": "2000.00",
                "total_pnl": "3000.00",
                "market_valuation_status": "success",
            }
        ],
    )
    _write_csv(
        account_paths.position_snapshot_path,
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
                "snapshot_date": "2026-05-30",
                "symbol": "AAPL",
                "shares": "10",
                "avg_price": "5000.00",
                "cost_value": "50000.00",
                "close_price": "5200.00",
                "market_value": "52000.00",
                "unrealized_pnl": "2000.00",
                "unrealized_pnl_pct": "0.04",
                "position_status": "OPEN",
            }
        ],
    )
    _write_csv(account_paths.execution_log_path, PAPER_EXECUTION_LOG_COLUMNS, [])

    eq = generate_paper_equity_curve_for_account(account_paths=account_paths)
    dd = generate_paper_drawdown_for_account(account_paths=account_paths)
    perf = generate_paper_performance_summary(account_paths=account_paths)
    journal = generate_paper_realized_trade_journal(account_paths=account_paths)
    realized = generate_paper_symbol_realized_performance(account_paths=account_paths)
    unrealized = generate_paper_symbol_unrealized_performance(account_paths=account_paths)
    side = generate_paper_symbol_side_by_side_performance(account_paths=account_paths)
    buckets = generate_paper_symbol_review_buckets(account_paths=account_paths)
    worksheet = generate_paper_symbol_review_worksheet(account_paths=account_paths)
    daily = generate_paper_daily_review_summary(account_paths=account_paths)

    for path in [
        eq["output_path"],
        dd["output_path"],
        perf["output_path"],
        journal["output_csv_path"],
        realized["output_csv_path"],
        unrealized["output_csv_path"],
        side["output_csv_path"],
        buckets["output_csv_path"],
        worksheet["markdown_output_path"],
        daily["daily_summary_path"],
    ]:
        assert path.is_relative_to(account_paths.root.resolve())

    assert not (tmp_path / "paper_test").exists()

