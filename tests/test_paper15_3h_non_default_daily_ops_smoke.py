from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from core.paper_account_guard import assert_non_default_writer_target
from core.paper_account_paths import build_paper_account_paths
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_status import WORKFLOW_COMMITTED, WORKFLOW_REVIEW_READY, run_paper_status
from scripts.append_paper_manual_review_log import append_paper_manual_review_log_from_template
from scripts.generate_paper_daily_review_summary import generate_paper_daily_review_summary
from scripts.generate_paper_drawdown import generate_paper_drawdown_for_account
from scripts.generate_paper_equity_curve import generate_paper_equity_curve_for_account
from scripts.generate_paper_manual_review_log_template import generate_paper_manual_review_log_template
from scripts.generate_paper_performance_summary import generate_paper_performance_summary
from scripts.generate_paper_realized_ranking_report import generate_paper_realized_ranking_report
from scripts.generate_paper_realized_trade_journal import generate_paper_realized_trade_journal
from scripts.generate_paper_symbol_realized_performance import generate_paper_symbol_realized_performance
from scripts.generate_paper_symbol_review_buckets import generate_paper_symbol_review_buckets
from scripts.generate_paper_symbol_review_worksheet import generate_paper_symbol_review_worksheet
from scripts.generate_paper_symbol_side_by_side_performance import generate_paper_symbol_side_by_side_performance
from scripts.generate_paper_symbol_unrealized_performance import generate_paper_symbol_unrealized_performance
from scripts.validate_paper_manual_review_log import validate_paper_manual_review_log


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_non_default_daily_ops_smoke_chain(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_smoke",
        account_root=tmp_path / "paper_accounts" / "paper_smoke",
        allow_legacy_default=False,
        create=True,
    )
    target_date = "2026-05-30"
    compact_date = "20260530"

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
            "position_count",
            "symbols",
        ],
        [
            {
                "snapshot_date": target_date,
                "cash": "50000.00",
                "positions_cost_value": "50000.00",
                "total_equity_cost_basis": "100000.00",
                "positions_market_value": "52000.00",
                "total_equity_market_value": "102000.00",
                "realized_pnl": "1000.00",
                "unrealized_pnl": "2000.00",
                "total_pnl": "3000.00",
                "market_valuation_status": "success",
                "position_count": "1",
                "symbols": "AAPL",
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
                "snapshot_date": target_date,
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
    account_paths.daily_action_plan_path(compact_date).write_text("# Daily Plan\n", encoding="utf-8")
    account_paths.current_state_snapshot_path(compact_date).write_text(
        json.dumps({"account_id": "paper_smoke", "date": target_date}, ensure_ascii=False),
        encoding="utf-8",
    )

    status_before = run_paper_status(compact_date, account_paths=account_paths)
    assert status_before["account_id"] == "paper_smoke"
    assert status_before["account_root"] == str(account_paths.root)
    assert status_before["workflow_status"] == WORKFLOW_COMMITTED
    assert status_before["reports_exists"] is False
    assert status_before["review_template_exists"] is False

    reports_results = [
        generate_paper_equity_curve_for_account(account_paths=account_paths),
        generate_paper_drawdown_for_account(account_paths=account_paths),
        generate_paper_performance_summary(account_paths=account_paths),
        generate_paper_realized_trade_journal(account_paths=account_paths),
        generate_paper_symbol_realized_performance(account_paths=account_paths),
        generate_paper_realized_ranking_report(account_paths=account_paths),
        generate_paper_symbol_unrealized_performance(account_paths=account_paths),
        generate_paper_symbol_side_by_side_performance(account_paths=account_paths),
        generate_paper_symbol_review_buckets(account_paths=account_paths),
        generate_paper_symbol_review_worksheet(account_paths=account_paths),
        generate_paper_daily_review_summary(account_paths=account_paths),
    ]

    template_result = generate_paper_manual_review_log_template(account_paths=account_paths)
    validation_before = validate_paper_manual_review_log(account_paths=account_paths)
    assert validation_before["summary"]["validation_result"] == "PASS"

    template_path = template_result["csv_output_path"]
    with template_path.open("r", encoding="utf-8-sig", newline="") as handle:
        template_rows = list(csv.DictReader(handle))
    assert template_rows
    template_rows[0]["manual_answer"] = "Reviewed in smoke flow"
    template_rows[0]["review_status"] = "reviewed"
    with template_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=template_rows[0].keys())
        writer.writeheader()
        writer.writerows(template_rows)

    validation_after = validate_paper_manual_review_log(account_paths=account_paths)
    append_result = append_paper_manual_review_log_from_template(account_paths=account_paths)
    status_after = run_paper_status(compact_date, account_paths=account_paths)

    assert validation_after["summary"]["validation_result"] == "PASS"
    assert append_result["summary"]["rows_appended"] == 1
    assert status_after["workflow_status"] == WORKFLOW_REVIEW_READY
    assert status_after["reports_exists"] is True
    assert status_after["review_template_exists"] is True
    assert status_after["review_validation_result"] == "PASS"
    assert status_after["manual_review_log_exists"] is True
    assert status_after["manual_review_log_row_count"] == 1

    important_paths = [
        reports_results[0]["output_path"],
        reports_results[1]["output_path"],
        reports_results[2]["output_path"],
        template_result["csv_output_path"],
        validation_after["report_output_path"],
        validation_after["issues_output_path"],
        append_result["target_log_path"],
        append_result["append_report_path"],
        append_result["append_issues_path"],
    ]
    for path in important_paths:
        assert path.is_relative_to(account_paths.root.resolve())

    with pytest.raises(ValueError, match="account root"):
        assert_non_default_writer_target(
            tmp_path / "paper_test" / "reports" / "paper_daily_review_summary.md",
            account_id=account_paths.account_id,
            account_root=account_paths.root,
        )

    assert not (tmp_path / "paper_test").exists()


def test_paper_default_legacy_policy_remains_unchanged(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_default",
        account_root=tmp_path / "paper_test",
        allow_legacy_default=False,
        create=True,
    )
    assert account_paths.account_id == "paper_default"
    assert account_paths.root == tmp_path / "paper_test"
    assert account_paths.reports_dir == account_paths.root / "reports"
    assert account_paths.reviews_dir == account_paths.root / "reviews"
