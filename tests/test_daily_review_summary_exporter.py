from __future__ import annotations

import json
from pathlib import Path

from core.daily_review_summary_exporter import (
    build_daily_review_summary,
    build_daily_review_summary_external_key,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_base(root: Path) -> None:
    _write(
        root / "paper_execution_log.csv",
        "trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at\n"
        "trade-aapl,2026-05-25,MANUAL,AAPL,BUY,1,100.0,100.0,notion_manual_execution,READY_FOR_PAPER_TRADE,manual_execution_import,,1,100.0,2026-05-25T21:46:03\n",
    )
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,currency,initial_cash,cash,positions_cost_value,total_equity_cost_basis,cash_ratio_cost_basis,position_count,symbols,applied_trade_count,valuation_method,source_execution_log,source_current_state,created_at,positions_market_value,total_equity_market_value,cash_ratio_market_value,unrealized_pnl,unrealized_pnl_pct,realized_pnl,realized_pnl_by_symbol,total_pnl,total_pnl_pct,market_valuation_status,market_valuation_error,valuation_price_date,valuation_price_dates,price_staleness_days,max_price_staleness_days\n"
        "2026-05-25,USD,100000.00,60244.67,39142.79,99387.46,0.6061597,4,AAPL|BRK-B|F|GEN,11,db_daily_price_close,log.csv,current.json,2026-05-25T21:46:03,39785.19,100029.86,0.6022669,642.40,0.0164117,-612.54,{},29.86,0.0002986,success,,2026-05-20,{}, {},5\n",
    )
    _write(
        root / "paper_position_snapshot.csv",
        "snapshot_date,symbol,shares,avg_price,cost_value,close_price,market_value,unrealized_pnl,unrealized_pnl_pct,realized_pnl,total_pnl,total_pnl_pct_on_current_cost,valuation_method,valuation_price_date,price_staleness_days,position_status,created_at\n"
        "2026-05-25,AAPL,1,100.00,100.00,302.25,302.25,202.25,2.0225000,0.00,202.25,2.0225000,db_daily_price_close,2026-05-20,5,OPEN,2026-05-25T21:46:03\n",
    )


def _seed_commit_report(root: Path) -> None:
    _write(
        root / "reports" / "manual_execution_import_commit_20260525.json",
        json.dumps(
            {
                "execution_date": "2026-05-25",
                "preview_json_path": str(root / "reports" / "manual_execution_import_preview_20260525.json"),
                "committed_rows": [
                    {
                        "canonical_key": "manual_execution:2026-05-25:AAPL:BUY:01",
                        "page_id": "page-aapl",
                        "symbol": "AAPL",
                        "side": "BUY",
                        "quantity": 1,
                        "actual_price": 100.0,
                        "commission": 0.0,
                        "currency": "USD",
                        "broker": None,
                        "validation_status": "WARNING",
                        "validation_issues": [
                            {
                                "severity": "WARNING",
                                "code": "missing_commission",
                                "message": "Commission is blank; normalized to 0.",
                            }
                        ],
                        "committed_trade_id": "trade-aapl",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
    )
    _write(
        root / "reports" / "manual_execution_import_preview_20260525.json",
        json.dumps(
            {
                "execution_date": "2026-05-25",
                "candidate_count": 1,
                "pass_count": 0,
                "warning_count": 1,
                "fail_count": 0,
                "commit_allowed": "true_with_warnings",
                "projected_cash_start": 60344.67,
                "projected_cash_end": 60244.67,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )


def test_daily_review_summary_external_key():
    assert build_daily_review_summary_external_key("2026-05-25") == "daily_review_summary:2026-05-25"


def test_daily_review_summary_uses_commit_report_as_primary_source(tmp_path):
    root = tmp_path / "paper_test"
    _seed_base(root)
    _seed_commit_report(root)
    summary = build_daily_review_summary(review_date="2026-05-25", paper_root=root)
    assert summary["availability_status"] == "AVAILABLE"
    assert summary["review_status"] == "PASS_WITH_WARNINGS"
    assert summary["committed_trade_count"] == 1
    assert summary["warning_count"] == 1
    assert summary["fail_count"] == 0
    assert summary["cash_start"] == 60344.67
    assert summary["cash_end"] == 60244.67
    assert summary["cash_impact"] == -100.0
    assert summary["position_impact_summary"] == "AAPL:+1"
    assert summary["committed_trade_items"][0]["trade_id"] == "trade-aapl"


def test_daily_review_summary_falls_back_when_commit_report_is_missing(tmp_path):
    root = tmp_path / "paper_test"
    _seed_base(root)
    summary = build_daily_review_summary(review_date="2026-05-25", paper_root=root)
    assert summary["availability_status"] == "NO_COMMIT_REPORT"
    assert summary["review_status"] == "PASS_WITH_WARNINGS"
    assert summary["committed_trade_count"] == 1
    assert summary["warning_count"] == 1
    assert "Commit report missing" in summary["warning_items"][0]


def test_daily_review_summary_handles_no_manual_activity(tmp_path):
    root = tmp_path / "paper_test"
    _write(
        root / "paper_execution_log.csv",
        "trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at\n",
    )
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,currency,initial_cash,cash\n2026-05-25,USD,100000.00,60344.67\n",
    )
    _write(
        root / "paper_position_snapshot.csv",
        "snapshot_date,symbol,shares\n",
    )
    summary = build_daily_review_summary(review_date="2026-05-25", paper_root=root)
    assert summary["availability_status"] == "NO_MANUAL_EXECUTIONS"
    assert summary["review_status"] == "NO_ACTIVITY"
    assert summary["committed_trade_count"] == 0
