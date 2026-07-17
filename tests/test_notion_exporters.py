from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.notion_exporters as notion_exporters
from core.notion_exporters import (
    NotionExportError,
    build_manual_execution_template_properties,
    build_account_snapshot_external_key,
    build_benchmark_report_external_key,
    build_daily_plan_external_key,
    build_daily_review_summary_properties,
    build_weekly_report_external_key,
    build_account_snapshot_properties,
    build_benchmark_report_properties,
    build_daily_plan_properties,
    export_daily_review_summary_to_notion,
    export_manual_execution_template_to_notion,
    export_manual_review_template_to_notion,
    build_weekly_report_properties,
    export_daily_plan_to_notion,
    export_latest_account_snapshot_to_notion,
    export_selected_paper_reports_to_notion,
    summarize_daily_plan_artifacts,
    export_weekly_report_to_notion,
)
from core.notion_settings import NotionSettings


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_weekly(root: Path) -> None:
    _write(
        root / "reports" / "paper_weekly_status_summary.json",
        json.dumps(
            {
                "schema_version": "paper_weekly_status.v1",
                "latest_snapshot_date": "2026-05-20",
                "overall_status": "PASS_WITH_WARNINGS",
                "period": {
                    "actual_start": "2026-05-09",
                    "actual_end": "2026-05-20",
                    "snapshot_count": 4,
                    "coverage_status": "PARTIAL",
                },
                "account_summary": {
                    "end_equity_market_value": 99827.61,
                    "equity_change_pct": -0.0017239,
                    "end_cash_ratio_market_value": 0.6044888,
                },
                "trade_summary": {"trade_count": 10},
                "operation_gaps": [
                    {"severity": "MEDIUM"},
                    {"severity": "HIGH"},
                ],
            }
        ),
    )
    _write(root / "reports" / "paper_weekly_status_summary.md", "# weekly\n")


def _seed_benchmark(root: Path) -> None:
    _write(
        root / "reports" / "paper_benchmark_comparison.json",
        json.dumps(
            {
                "schema_version": "paper_benchmark_comparison.v1",
                "run_mode": "exploratory",
                "official_run": False,
                "latest_snapshot_date": "2026-05-20",
                "availability_status": "AVAILABLE",
                "summary": {
                    "paper": {
                        "paper_return": -0.0017239,
                        "paper_max_drawdown": -0.0052739,
                    },
                    "benchmarks": {
                        "SPY": {
                            "benchmark_return": 0.0049212,
                            "benchmark_max_drawdown": -0.001428,
                            "excess_return": -0.0066451,
                        },
                        "QQQ": {
                            "benchmark_return": 0.0026996,
                            "benchmark_max_drawdown": -0.00561,
                            "excess_return": -0.0044235,
                        },
                        "CASH": {
                            "benchmark_return": 0.0,
                            "excess_return": -0.0017239,
                        },
                    },
                },
            }
        ),
    )
    _write(root / "reports" / "paper_benchmark_comparison.md", "# benchmark\n")


def _seed_account(root: Path) -> None:
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,initial_cash,cash,total_equity_market_value,total_equity_cost_basis,unrealized_pnl,cash_ratio_market_value,cash_ratio_cost_basis,position_count,symbols,market_valuation_status,valuation_price_date\n"
        "2026-05-19,100000,60000,99000,98900,100,0.60,0.61,3,A|B|C,success,2026-05-19\n"
        "2026-05-20,100000,60344.67,99827.61,99387.46,440.15,0.6044888,0.6071658,3,BRK-B|F|GEN,success,2026-05-20\n",
    )


def _seed_daily_plan(root: Path, *, date: str = "2026-05-20", symbol: str = "ABC") -> None:
    compact_date = date.replace("-", "")
    _write(
        root / f"daily_action_plan_{compact_date}.md",
        "\n".join(
            [
                f"# Daily Action Plan [{date}]",
                "",
                "## 1. Market Summary",
                "- Current Regime: `BULL`",
                "- Target Cash Ratio: `5%`",
                "",
                "## 4. Confirmed Trades",
                "| Type | Symbol | Shares | Ref Price | Reason |",
                "| :--- | :--- | :--- | :--- | :--- |",
                f"| BUY | **{symbol}** | 10 | $12.34 | ENTRY_SIGNAL |",
                "| SELL | **XYZ** | 5 | $20.00 | EXIT_SIGNAL |",
                "",
                "## 4-0. Review Items",
                "| Symbol | Shares | Ref Price | Reason | Note |",
                "| :--- | ---: | ---: | :--- | :--- |",
                "| **BRK-B** | 20 | $480.90 | REVIEW_EXIT | manual check |",
                "",
                "## 4-0-1. Warnings",
                "| Symbol | Severity | Reason | Note |",
                "| :--- | :--- | :--- | :--- |",
                "| GEN | HIGH | WARNING_HIGHEST_PRICE_INCONSISTENT | highest mismatch |",
                "| - | MEDIUM | WARNING_LOW_BUYING_POWER | low buying power |",
                "",
                "## 4-1. Candidate Diagnostics",
                "| Symbol | Latest Date | Stale Days | Score | RS | Entry | Result | Reason |",
                "| :--- | :--- | :---: | ---: | ---: | :---: | :--- | :--- |",
                "| AMT | 2026-05-20 | 0 | 2.00 | -0.05 | N | fail | entry_signal_false |",
            ]
        ),
    )
    _write(
        root / "config_snapshots" / f"paper_config_snapshot_{compact_date}.json",
        json.dumps(
            {
                "schema_version": 1,
                "plan_date": date,
                "market_state": {"regime": "BULL"},
                "market_status_summary": {"regime": "BULL"},
            }
        ),
    )


def _seed_daily_review(root: Path) -> None:
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
            }
        ),
    )
    _write(
        root / "reports" / "manual_execution_import_preview_20260525.json",
        json.dumps(
            {
                "execution_date": "2026-05-25",
                "candidate_count": 1,
                "warning_count": 1,
                "fail_count": 0,
                "projected_cash_start": 60344.67,
                "projected_cash_end": 60244.67,
            }
        ),
    )
    _write(
        root / "paper_execution_log.csv",
        "trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at\n"
        "trade-aapl,2026-05-25,MANUAL,AAPL,BUY,1,100.0,100.0,notion_manual_execution,READY_FOR_PAPER_TRADE,manual_execution_import,,1,100.0,2026-05-25T21:46:03\n",
    )
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,initial_cash,cash,total_equity_market_value,total_equity_cost_basis,unrealized_pnl,cash_ratio_market_value,cash_ratio_cost_basis,position_count,symbols,market_valuation_status,valuation_price_date\n"
        "2026-05-25,100000,60244.67,100029.86,99387.46,642.40,0.6022669,0.6061597,4,AAPL|BRK-B|F|GEN,success,2026-05-20\n",
    )
    _write(
        root / "paper_position_snapshot.csv",
        "snapshot_date,symbol,shares,avg_price,cost_value,close_price,market_value,unrealized_pnl,unrealized_pnl_pct,realized_pnl,total_pnl,total_pnl_pct_on_current_cost,valuation_method,valuation_price_date,price_staleness_days,position_status,created_at\n"
        "2026-05-25,AAPL,1,100.00,100.00,302.25,302.25,202.25,2.0225000,0.00,202.25,2.0225000,db_daily_price_close,2026-05-20,5,OPEN,2026-05-25T21:46:03\n",
    )


def _seed_manual_review_template(root: Path, *, date: str = "2026-06-05", count: int = 8) -> None:
    symbols = ["MAA", "SW"]
    lines = [
        "review_date,symbol,review_bucket,review_priority,sample_size_flag,symbol_status,question_id,question_text,question_category,is_actionable,manual_answer,review_status,follow_up_needed,review_tag,reviewer_note,source_worksheet_path,created_at"
    ]
    for index in range(1, count + 1):
        symbol = symbols[(index - 1) % len(symbols)]
        lines.append(
            f"{date},{symbol},daily_review,normal,normal,open,Q{index:03d},Question {index},daily,false,,pending,false,,,template:{date}:{symbol}:Q{index:03d},{date}T12:00:00"
        )
    _write(root / "reviews" / "paper_manual_review_log_template.csv", "\n".join(lines) + "\n")


def _seed_daily_plan_sidecar(
    root: Path,
    *,
    account_id: str = "paper_pilot_202606",
    plan_date: str = "2026-06-08",
    items: list[dict] | None = None,
) -> Path:
    compact = plan_date.replace("-", "")
    payload = {
        "schema_version": "paper_daily_plan.v1",
        "account_id": account_id,
        "data_date": "2026-06-05",
        "trade_date": plan_date,
        "plan_date": plan_date,
        "run_mode": "official",
        "official_run": True,
        "items": items
        if items is not None
        else [
            {
                "symbol": "MAA",
                "action": "BUY",
                "quantity": 73,
                "price": 135.37,
                "reason": "STRATEGY_ENTRY",
            },
            {
                "symbol": "BRK-B",
                "action": "SELL",
                "quantity": 20,
                "price": 512.34,
                "reason": "SWITCH_OUT",
            },
            {
                "symbol": "GEN",
                "action": "REVIEW_EXIT",
                "quantity": 1,
                "price": 30.0,
                "reason": "REVIEW_ONLY",
            },
        ],
        "fingerprints": {},
    }
    path = root / f"daily_action_plan_{compact}.json"
    _write(path, json.dumps(payload))
    return path


def _mapping() -> dict[str, dict[str, str]]:
    return {
        "weekly_reports": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "period.actual_start": "Period Start",
            "period.actual_end": "Period End",
            "latest_snapshot_date": "Latest Snapshot Date",
            "period.coverage_status": "Coverage Status",
            "overall_status": "Overall Status",
            "period.snapshot_count": "Snapshot Count",
            "account_summary.end_equity_market_value": "End Equity",
            "account_summary.equity_change_pct": "Equity Change %",
            "account_summary.end_cash_ratio_market_value": "Cash Ratio",
            "trade_summary.trade_count": "Trade Count",
            "operation_gaps.count": "Gap Count",
            "operation_gaps.high_count": "High Gap Count",
            "markdown_path": "Markdown Path",
            "json_path": "JSON Path",
            "schema_version": "Schema Version",
            "synced_at": "Synced At",
            "sync_status": "Sync Status",
        },
        "benchmark_reports": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "latest_snapshot_date": "Latest Snapshot Date",
            "run_mode": "Run Mode",
            "official_run": "Official Run",
            "availability_status": "Availability Status",
            "summary.paper.paper_return": "Paper Return",
            "summary.benchmarks.SPY.benchmark_return": "SPY Return",
            "summary.benchmarks.QQQ.benchmark_return": "QQQ Return",
            "summary.benchmarks.CASH.benchmark_return": "CASH Return",
            "summary.benchmarks.SPY.excess_return": "Excess vs SPY",
            "summary.benchmarks.QQQ.excess_return": "Excess vs QQQ",
            "summary.benchmarks.CASH.excess_return": "Excess vs CASH",
            "summary.paper.paper_max_drawdown": "Paper MDD",
            "summary.benchmarks.SPY.benchmark_max_drawdown": "SPY MDD",
            "summary.benchmarks.QQQ.benchmark_max_drawdown": "QQQ MDD",
            "markdown_path": "Markdown Path",
            "json_path": "JSON Path",
            "schema_version": "Schema Version",
            "synced_at": "Synced At",
            "sync_status": "Sync Status",
        },
        "account_snapshots": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "snapshot_date": "Snapshot Date",
            "initial_cash": "Initial Cash",
            "cash": "Cash",
            "total_equity_market_value": "Total Equity Market Value",
            "total_equity_cost_basis": "Total Equity Cost Basis",
            "unrealized_pnl": "Unrealized PnL",
            "cash_ratio_market_value": "Cash Ratio Market Value",
            "cash_ratio_cost_basis": "Cash Ratio Cost Basis",
            "position_count": "Position Count",
            "symbols": "Symbols",
            "market_valuation_status": "Valuation Status",
            "valuation_price_date": "Valuation Price Date",
            "synced_at": "Synced At",
            "sync_status": "Sync Status",
        },
        "daily_plans": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "plan_date": "Plan Date",
            "regime": "Regime",
            "confirmed_trade_count": "Confirmed Trade Count",
            "review_item_count": "Review Item Count",
            "warning_count": "Warning Count",
            "markdown_path": "Markdown Path",
            "json_path": "JSON Path",
            "schema_version": "Schema Version",
            "synced_at": "Synced At",
            "sync_status": "Sync Status",
        },
        "daily_review_summaries": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "review_date": "Review Date",
            "review_status": "Review Status",
            "availability_status": "Availability Status",
            "committed_trade_count": "Committed Trade Count",
            "warning_count": "Warning Count",
            "fail_count": "Fail Count",
            "cash_start": "Cash Start",
            "cash_end": "Cash End",
            "cash_impact": "Cash Impact",
            "position_impact_summary": "Position Impact Summary",
            "commit_report_path": "Commit Report Path",
            "preview_report_path": "Preview Report Path",
            "latest_snapshot_date": "Latest Snapshot Date",
            "schema_version": "Schema Version",
            "synced_at": "Synced At",
            "sync_status": "Sync Status",
        },
        "manual_executions": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "execution_date": "Execution Date",
            "plan_date": "Plan Date",
            "symbol": "Symbol",
            "side": "Side",
            "quantity": "Quantity",
            "actual_price": "Actual Price",
            "commission": "Commission",
            "currency": "Currency",
            "broker": "Broker",
            "status": "Status",
            "linked_daily_plan_key": "Linked Daily Plan Key",
            "note": "Note",
            "validation_status": "Validation Status",
            "validation_message": "Validation Message",
            "import_status": "Import Status",
            "imported_at": "Imported At",
            "synced_at": "Synced At",
        },
        "manual_reviews": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "review_date": "Review Date",
            "symbol": "Symbol",
            "question_id": "Question ID",
            "question": "Question",
            "manual_answer": "Manual Answer",
            "review_status": "Review Status",
            "follow_up_needed": "Follow-up Needed",
            "review_tag": "Review Tag",
            "reviewer_note": "Reviewer Note",
            "source_template_key": "Source Template Key",
            "validation_status": "Validation Status",
            "validation_message": "Validation Message",
            "import_status": "Import Status",
            "imported_at": "Imported At",
            "synced_at": "Synced At",
        },
    }


def _settings() -> NotionSettings:
    return NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={
            "weekly_reports": "db-weekly",
            "benchmark_reports": "db-benchmark",
            "account_snapshots": "db-account",
            "daily_plans": "db-daily-plan",
            "daily_review_summaries": "db-daily-review",
            "manual_executions": "db-manual-executions",
            "manual_reviews": "db-manual-reviews",
        },
    )


class FakeClient:
    def __init__(self):
        self.calls: list[dict] = []

    def query_by_external_key(self, data_source_id, external_key, external_key_property_name):
        return []

    def upsert_page_by_external_key(self, **kwargs):
        self.calls.append(kwargs)
        class Result:
            action = "updated"
            page_id = "page-123"
            payload = {"id": "page-123"}

        return Result()


class FakeFallbackClient:
    def __init__(self, *, new_hits: list[dict] | None = None, legacy_hits: list[dict] | None = None):
        self.new_hits = new_hits or []
        self.legacy_hits = legacy_hits or []
        self.query_calls: list[str] = []
        self.update_calls: list[tuple[str, dict]] = []

    def query_by_external_key(self, data_source_id, external_key, external_key_property_name):
        self.query_calls.append(external_key)
        if ":paper_" in external_key:
            return list(self.new_hits)
        return list(self.legacy_hits)

    def update_page(self, page_id, properties):
        self.update_calls.append((page_id, properties))
        return {"id": page_id}

    def replace_page_children(self, page_id, children):
        return {"id": page_id, "children": children}

    def upsert_page_by_external_key(self, **kwargs):
        raise AssertionError("upsert_page_by_external_key should not be used when legacy fallback updates an existing page")


class FakeManualReviewTemplateClient:
    def __init__(self, existing_keys: dict[str, str] | None = None, schema: dict | None = None):
        self.existing_keys = existing_keys or {}
        self.schema = schema
        self.query_calls: list[str] = []
        self.create_calls: list[tuple[str, dict]] = []
        self.update_calls: list[tuple[str, dict]] = []

    def query_by_external_key(self, data_source_id, external_key, external_key_property_name):
        self.query_calls.append(external_key)
        page_id = self.existing_keys.get(external_key)
        return [{"id": page_id}] if page_id else []

    def create_page(self, data_source_id, properties):
        self.create_calls.append((data_source_id, properties))
        return {"id": f"created-{len(self.create_calls)}"}

    def update_page(self, page_id, properties):
        self.update_calls.append((page_id, properties))
        return {"id": page_id}

    def get_data_source_schema(self, data_source_id):
        return self.schema or {}


def test_weekly_external_key_is_generated():
    key = build_weekly_report_external_key({"period": {"actual_start": "2026-05-09", "actual_end": "2026-05-20"}})
    assert key == "weekly_report:paper_default:2026-05-09:2026-05-20"


def test_benchmark_external_key_is_generated():
    key = build_benchmark_report_external_key({"latest_snapshot_date": "2026-05-20", "run_mode": "exploratory"})
    assert key == "benchmark:paper_default:2026-05-20:exploratory"


def test_account_snapshot_external_key_is_generated():
    key = build_account_snapshot_external_key({"snapshot_date": "2026-05-20"})
    assert key == "account_snapshot:paper_default:2026-05-20"


def test_daily_plan_external_key_is_generated():
    key = build_daily_plan_external_key("2026-05-20")
    assert key == "daily_plan:paper_default:2026-05-20"


def test_weekly_property_payload_is_built(tmp_path):
    root = tmp_path / "paper_test"
    _seed_weekly(root)
    summary = json.loads((root / "reports" / "paper_weekly_status_summary.json").read_text(encoding="utf-8"))
    props = build_weekly_report_properties(
        summary,
        _mapping()["weekly_reports"],
        markdown_path=root / "reports" / "paper_weekly_status_summary.md",
        json_path=root / "reports" / "paper_weekly_status_summary.json",
        synced_at="2026-05-23T00:00:00+00:00",
    )
    assert props["Name"]["title"][0]["text"]["content"].startswith("Weekly Report")
    assert props["Account ID"]["select"]["name"] == "paper_default"
    assert props["Gap Count"]["number"] == 2
    assert props["High Gap Count"]["number"] == 1


def test_benchmark_property_payload_is_built(tmp_path):
    root = tmp_path / "paper_test"
    _seed_benchmark(root)
    summary = json.loads((root / "reports" / "paper_benchmark_comparison.json").read_text(encoding="utf-8"))
    props = build_benchmark_report_properties(
        summary,
        _mapping()["benchmark_reports"],
        markdown_path=root / "reports" / "paper_benchmark_comparison.md",
        json_path=root / "reports" / "paper_benchmark_comparison.json",
        synced_at="2026-05-23T00:00:00+00:00",
    )
    assert props["Run Mode"]["select"]["name"] == "EXPLORATORY"
    assert props["Account ID"]["select"]["name"] == "paper_default"
    assert props["SPY Return"]["number"] == 0.0049212


def test_account_snapshot_property_payload_is_built():
    row = {
        "snapshot_date": "2026-05-20",
        "initial_cash": "100000.00",
        "cash": "60344.67",
        "total_equity_market_value": "99827.61",
        "total_equity_cost_basis": "99387.46",
        "unrealized_pnl": "440.15",
        "cash_ratio_market_value": "0.6044888",
        "cash_ratio_cost_basis": "0.6071658",
        "position_count": "3",
        "symbols": "BRK-B|F|GEN",
        "market_valuation_status": "success",
        "valuation_price_date": "2026-05-20",
    }
    props = build_account_snapshot_properties(
        row,
        _mapping()["account_snapshots"],
        synced_at="2026-05-23T00:00:00+00:00",
    )
    assert props["Snapshot Date"]["date"]["start"] == "2026-05-20"
    assert props["Account ID"]["select"]["name"] == "paper_default"
    assert props["Position Count"]["number"] == 3


def test_daily_plan_summary_is_built_from_markdown_and_config_snapshot(tmp_path):
    root = tmp_path / "paper_test"
    _seed_daily_plan(root)
    summary = summarize_daily_plan_artifacts(
        markdown_path=root / "daily_action_plan_20260520.md",
        config_snapshot_path=root / "config_snapshots" / "paper_config_snapshot_20260520.json",
    )
    assert summary["plan_date"] == "2026-05-20"
    assert summary["regime"] == "BULL"
    assert summary["confirmed_trade_count"] == 2
    assert summary["review_item_count"] == 1
    assert summary["warning_count"] == 2


def test_daily_plan_property_payload_is_built(tmp_path):
    root = tmp_path / "paper_test"
    _seed_daily_plan(root)
    summary = summarize_daily_plan_artifacts(
        markdown_path=root / "daily_action_plan_20260520.md",
        config_snapshot_path=root / "config_snapshots" / "paper_config_snapshot_20260520.json",
    )
    props = build_daily_plan_properties(
        summary,
        _mapping()["daily_plans"],
        markdown_path=root / "daily_action_plan_20260520.md",
        json_path=root / "config_snapshots" / "paper_config_snapshot_20260520.json",
        synced_at="2026-05-23T00:00:00+00:00",
    )
    assert props["Name"]["title"][0]["text"]["content"] == "Daily Plan 2026-05-20"
    assert props["Account ID"]["select"]["name"] == "paper_default"
    assert props["Regime"]["select"]["name"] == "BULL"
    assert props["Confirmed Trade Count"]["number"] == 2


def test_daily_review_property_payload_is_built():
    summary = {
        "review_date": "2026-05-25",
        "review_status": "PASS_WITH_WARNINGS",
        "availability_status": "AVAILABLE",
        "committed_trade_count": 1,
        "warning_count": 1,
        "fail_count": 0,
        "cash_start": 60344.67,
        "cash_end": 60244.67,
        "cash_impact": -100.0,
        "position_impact_summary": "AAPL:+1",
        "commit_report_path": "outputs/paper_test/reports/manual_execution_import_commit_20260525.json",
        "preview_report_path": "outputs/paper_test/reports/manual_execution_import_preview_20260525.json",
        "latest_snapshot_date": "2026-05-25",
        "schema_version": "daily_review_summary.v1",
    }
    props = build_daily_review_summary_properties(
        summary,
        _mapping()["daily_review_summaries"],
        synced_at="2026-05-25T00:00:00+00:00",
    )
    assert props["Review Status"]["select"]["name"] == "PASS_WITH_WARNINGS"
    assert props["Account ID"]["select"]["name"] == "paper_default"
    assert props["Cash Impact"]["number"] == -100.0
    assert props["Position Impact Summary"]["rich_text"][0]["text"]["content"] == "AAPL:+1"


def test_missing_source_file_raises_error(tmp_path):
    with pytest.raises(NotionExportError):
        export_weekly_report_to_notion(
            client=None,
            settings=_settings(),
            mapping_root=_mapping(),
            paper_root=tmp_path / "paper_test",
            dry_run=True,
        )


def test_missing_mapping_raises_error(tmp_path):
    root = tmp_path / "paper_test"
    _seed_weekly(root)
    with pytest.raises(Exception):
        export_weekly_report_to_notion(
            client=None,
            settings=_settings(),
            mapping_root={"benchmark_reports": {}},
            paper_root=root,
            dry_run=True,
        )


def test_dry_run_does_not_call_client(tmp_path):
    root = tmp_path / "paper_test"
    _seed_weekly(root)
    client = FakeClient()
    result = export_weekly_report_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        paper_root=root,
        dry_run=True,
    )
    assert result.action == "dry_run"
    assert result.account_id == "paper_default"
    assert result.legacy_external_key == "weekly_report:2026-05-09:2026-05-20"
    assert result.legacy_fallback_used is False
    assert client.calls == []


def test_daily_plan_dry_run_does_not_call_client(tmp_path):
    root = tmp_path / "paper_test"
    _seed_daily_plan(root)
    client = FakeClient()
    result = export_daily_plan_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        paper_root=root,
        dry_run=True,
    )
    assert result.action == "dry_run"
    assert result.external_key == "daily_plan:paper_default:2026-05-20"
    assert result.legacy_external_key == "daily_plan:2026-05-20"
    assert client.calls == []


def test_daily_review_dry_run_does_not_call_client(tmp_path):
    root = tmp_path / "paper_test"
    _seed_daily_review(root)
    client = FakeClient()
    result = export_daily_review_summary_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        review_date="2026-05-25",
        paper_root=root,
        dry_run=True,
    )
    assert result.action == "dry_run"
    assert result.external_key == "daily_review_summary:paper_default:2026-05-25"
    assert result.legacy_external_key == "daily_review_summary:2026-05-25"
    assert client.calls == []


def test_upsert_helper_is_called_in_export_path(tmp_path):
    root = tmp_path / "paper_test"
    _seed_weekly(root)
    client = FakeClient()
    result = export_weekly_report_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        paper_root=root,
        dry_run=False,
    )
    assert result.action == "updated"
    assert len(client.calls) == 1
    assert client.calls[0]["data_source_id"]
    assert result.data_source_key == "weekly_reports"
    assert client.calls[0]["refresh_children_on_update"] is False


def test_account_snapshot_default_export_uses_latest_row(tmp_path):
    root = tmp_path / "paper_test"
    _seed_account(root)
    client = FakeClient()
    result = export_latest_account_snapshot_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        paper_root=root,
        dry_run=False,
    )
    assert result.external_key == "account_snapshot:paper_default:2026-05-20"
    assert len(client.calls) == 1


def test_daily_plan_export_uses_latest_artifacts(tmp_path):
    root = tmp_path / "paper_test"
    _seed_daily_plan(root)
    client = FakeClient()
    result = export_daily_plan_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        paper_root=root,
        dry_run=False,
    )
    assert result.external_key == "daily_plan:paper_default:2026-05-20"
    assert result.data_source_key == "daily_plans"
    assert len(client.calls) == 1
    assert client.calls[0]["data_source_id"]
    assert client.calls[0]["refresh_children_on_update"] is True
    children = client.calls[0]["children"]
    texts = [
        block[block["type"]]["rich_text"][0]["text"]["content"]
        for block in children
    ]
    assert "오늘의 운영 요약" in texts
    assert "확정 거래" in texts
    assert "검토 필요 항목" in texts
    assert "경고" in texts
    assert "원천 파일" in texts
    assert any("BUY ABC 10 @ $12.34 - ENTRY_SIGNAL" in text for text in texts)
    assert any("BRK-B 20 @ $480.90 - REVIEW_EXIT" in text for text in texts)
    assert any("GEN [HIGH] WARNING_HIGHEST_PRICE_INCONSISTENT" in text for text in texts)
    assert any("Markdown Path: " in text for text in texts)
    assert any("JSON Path: " in text for text in texts)


def test_daily_plan_export_requires_matching_artifacts(tmp_path):
    root = tmp_path / "paper_test"
    _write(root / "daily_action_plan_20260520.md", "# Daily Action Plan\n")
    with pytest.raises(NotionExportError, match="No daily plan artifacts found"):
        export_daily_plan_to_notion(
            client=None,
            settings=_settings(),
            mapping_root=_mapping(),
            paper_root=root,
            dry_run=True,
        )


def test_daily_plan_export_falls_back_when_sections_are_missing(tmp_path):
    root = tmp_path / "paper_test"
    _write(
        root / "daily_action_plan_20260520.md",
        "\n".join(
            [
                "# Daily Action Plan [2026-05-20]",
                "",
                "## 1. Market Summary",
                "- Current Regime: `BULL`",
            ]
        ),
    )
    _write(
        root / "config_snapshots" / "paper_config_snapshot_20260520.json",
        json.dumps(
            {
                "schema_version": 1,
                "plan_date": "2026-05-20",
                "market_state": {"regime": "BULL"},
            }
        ),
    )
    client = FakeClient()
    result = export_daily_plan_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        paper_root=root,
        dry_run=False,
    )
    assert result.action == "updated"
    texts = [
        block[block["type"]]["rich_text"][0]["text"]["content"]
        for block in client.calls[0]["children"]
    ]
    assert any("Section ## 4. could not be parsed." in text for text in texts)
    assert any("Section ## 4-0. could not be parsed." in text for text in texts)
    assert any("Section ## 4-0-1. could not be parsed." in text for text in texts)


def test_daily_review_export_uses_commit_report(tmp_path):
    root = tmp_path / "paper_test"
    _seed_daily_review(root)
    client = FakeClient()
    result = export_daily_review_summary_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        review_date="2026-05-25",
        paper_root=root,
        dry_run=False,
    )
    assert result.external_key == "daily_review_summary:paper_default:2026-05-25"
    assert result.data_source_key == "daily_review_summaries"
    assert client.calls[0]["data_source_id"]
    texts = [block[block["type"]]["rich_text"][0]["text"]["content"] for block in client.calls[0]["children"]]
    assert "오늘의 리뷰 요약" in texts
    assert any("AAPL BUY 1 @ 100.0 - trade-aapl" in text for text in texts)
    assert any("AAPL: +1 shares" in text or "AAPL: +1 shares (ending 1)" in text for text in texts)


def test_daily_plan_dry_run_does_not_request_body_refresh(tmp_path):
    root = tmp_path / "paper_test"
    _seed_daily_plan(root)
    client = FakeClient()
    result = export_daily_plan_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        paper_root=root,
        dry_run=True,
    )
    assert result.action == "dry_run"
    assert client.calls == []


def test_export_selected_requires_target():
    with pytest.raises(NotionExportError):
        export_selected_paper_reports_to_notion(
            client=None,
            settings=_settings(),
            mapping_root=_mapping(),
            dry_run=True,
        )


def test_export_selected_supports_daily_review_summary(tmp_path):
    root = tmp_path / "paper_test"
    _seed_daily_review(root)
    results = export_selected_paper_reports_to_notion(
        client=None,
        settings=_settings(),
        mapping_root=_mapping(),
        export_daily_review_summary=True,
        review_date="2026-05-25",
        paper_root=root,
        dry_run=True,
    )
    assert len(results) == 1
    assert results[0].target == "daily_review_summaries"
    assert results[0].account_id == "paper_default"


def test_non_default_account_has_no_legacy_fallback(tmp_path):
    root = tmp_path / "paper_test"
    _seed_daily_plan(root)
    result = export_daily_plan_to_notion(
        client=None,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_growth",
        paper_root=root,
        dry_run=True,
    )
    assert result.account_id == "paper_growth"
    assert result.external_key == "daily_plan:paper_growth:2026-05-20"
    assert result.legacy_external_key is None
    assert result.legacy_fallback_used is False


def test_non_default_daily_plan_export_uses_account_root_not_default_root(tmp_path, monkeypatch):
    default_root = tmp_path / "paper_test"
    account_root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_daily_plan(default_root, date="2026-05-20", symbol="OLD")
    _seed_daily_plan(account_root, date="2026-06-05", symbol="MAA")

    monkeypatch.setattr(
        notion_exporters,
        "paper_daily_action_plan_path",
        lambda date_str: default_root / f"daily_action_plan_{str(date_str).replace('-', '')}.md",
    )
    monkeypatch.setattr(
        notion_exporters,
        "build_paper_account_paths",
        lambda *args, **kwargs: SimpleNamespace(root=account_root),
    )

    result = export_daily_plan_to_notion(
        client=None,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_pilot_202606",
        dry_run=True,
    )

    assert result.account_id == "paper_pilot_202606"
    assert result.external_key == "daily_plan:paper_pilot_202606:2026-06-05"
    assert "paper_pilot_202606" in result.source_path
    assert "paper_test" not in result.source_path
    assert result.source_path.endswith("paper_config_snapshot_20260605.json")


def test_non_default_daily_plan_export_date_uses_requested_account_artifact(tmp_path):
    account_root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_daily_plan(account_root, date="2026-06-04", symbol="OLD")
    _seed_daily_plan(account_root, date="2026-06-05", symbol="MAA")

    result = export_daily_plan_to_notion(
        client=None,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_pilot_202606",
        paper_root=account_root,
        plan_date="2026-06-05",
        dry_run=True,
    )

    assert result.external_key == "daily_plan:paper_pilot_202606:2026-06-05"
    assert result.source_path.endswith("paper_config_snapshot_20260605.json")


def test_non_default_daily_plan_export_missing_account_artifact_does_not_fallback(tmp_path, monkeypatch):
    default_root = tmp_path / "paper_test"
    account_root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_daily_plan(default_root, date="2026-05-20", symbol="OLD")
    account_root.mkdir(parents=True)

    monkeypatch.setattr(
        notion_exporters,
        "paper_daily_action_plan_path",
        lambda date_str: default_root / f"daily_action_plan_{str(date_str).replace('-', '')}.md",
    )
    monkeypatch.setattr(
        notion_exporters,
        "build_paper_account_paths",
        lambda *args, **kwargs: SimpleNamespace(root=account_root),
    )

    with pytest.raises(NotionExportError, match="No daily plan artifacts found"):
        export_daily_plan_to_notion(
            client=None,
            settings=_settings(),
            mapping_root=_mapping(),
            account_id="paper_pilot_202606",
            dry_run=True,
        )


def test_non_default_manual_review_template_export_uses_account_root_not_default_root(tmp_path, monkeypatch):
    default_root = tmp_path / "paper_test"
    account_root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_manual_review_template(default_root, date="2026-05-20")
    _seed_manual_review_template(account_root, date="2026-06-05")

    monkeypatch.setattr(
        notion_exporters,
        "build_paper_account_paths",
        lambda *args, **kwargs: SimpleNamespace(root=account_root),
    )

    summary = export_manual_review_template_to_notion(
        client=None,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_pilot_202606",
        review_date="2026-06-05",
        dry_run=True,
    )

    assert summary["account_id"] == "paper_pilot_202606"
    assert summary["review_date"] == "2026-06-05"
    assert summary["candidate_count"] == 8
    assert summary["create_count"] == 8
    assert "paper_pilot_202606" in summary["source_template_path"]
    assert "paper_test" not in summary["source_template_path"]
    assert summary["candidates"][0]["external_key"].startswith(
        "manual_review:paper_pilot_202606:2026-06-05:"
    )


def test_manual_review_template_export_dry_run_does_not_write(tmp_path):
    root = tmp_path / "paper_test"
    _seed_manual_review_template(root, date="2026-06-05")
    client = FakeManualReviewTemplateClient()

    summary = export_manual_review_template_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_default",
        paper_root=root,
        review_date="2026-06-05",
        dry_run=True,
    )

    assert summary["candidate_count"] == 8
    assert summary["would_write"] is False
    assert client.query_calls
    assert client.create_calls == []
    assert client.update_calls == []


def test_empty_manual_review_template_export_is_successful_no_op(tmp_path):
    root = tmp_path / "paper_test"
    _seed_manual_review_template(root, date="2026-06-15", count=0)
    client = FakeManualReviewTemplateClient()

    summary = export_manual_review_template_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_default",
        paper_root=root,
        review_date="2026-06-15",
        dry_run=True,
    )

    assert summary["candidate_count"] == 0
    assert summary["failed_count"] == 0
    assert summary["would_write"] is False
    assert client.query_calls == []
    assert client.create_calls == []
    assert client.update_calls == []


def test_manual_review_template_with_only_other_dates_is_not_empty_no_op(tmp_path):
    root = tmp_path / "paper_test"
    _seed_manual_review_template(root, date="2026-06-12", count=1)

    with pytest.raises(NotionExportError, match="No manual review template rows found for 2026-06-15"):
        export_manual_review_template_to_notion(
            client=FakeManualReviewTemplateClient(),
            settings=_settings(),
            mapping_root=_mapping(),
            account_id="paper_default",
            paper_root=root,
            review_date="2026-06-15",
            dry_run=True,
        )


def test_empty_manual_review_template_still_validates_review_date(tmp_path):
    root = tmp_path / "paper_test"
    _seed_manual_review_template(root, date="2026-06-15", count=0)

    with pytest.raises(NotionExportError, match="Invalid date"):
        export_manual_review_template_to_notion(
            client=FakeManualReviewTemplateClient(),
            settings=_settings(),
            mapping_root=_mapping(),
            account_id="paper_default",
            paper_root=root,
            review_date="invalid",
            dry_run=True,
        )


def test_header_only_manual_review_template_with_missing_columns_is_blocked(tmp_path):
    root = tmp_path / "paper_test"
    template = root / "reviews" / "paper_manual_review_log_template.csv"
    _write(template, "review_date,symbol\n")
    client = FakeManualReviewTemplateClient()

    with pytest.raises(NotionExportError, match="Missing paper manual review log columns"):
        export_manual_review_template_to_notion(
            client=client,
            settings=_settings(),
            mapping_root=_mapping(),
            account_id="paper_default",
            paper_root=root,
            review_date="2026-06-15",
            dry_run=True,
        )

    assert client.query_calls == []
    assert client.create_calls == []
    assert client.update_calls == []


def test_manual_review_template_export_marks_existing_external_key_as_update(tmp_path):
    root = tmp_path / "paper_test"
    _seed_manual_review_template(root, date="2026-06-05")
    existing_key = "manual_review:paper_default:2026-06-05:MAA:Q001"
    client = FakeManualReviewTemplateClient(existing_keys={existing_key: "page-existing"})

    summary = export_manual_review_template_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_default",
        paper_root=root,
        review_date="2026-06-05",
        dry_run=True,
    )

    assert summary["candidate_count"] == 8
    assert summary["update_count"] == 1
    assert summary["create_count"] == 7
    update_candidate = [item for item in summary["candidates"] if item["action"] == "update"][0]
    assert update_candidate["external_key"] == existing_key
    assert update_candidate["page_id"] == "page-existing"


def test_non_default_manual_review_template_missing_account_template_does_not_fallback(tmp_path, monkeypatch):
    default_root = tmp_path / "paper_test"
    account_root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_manual_review_template(default_root, date="2026-06-05")
    account_root.mkdir(parents=True)
    monkeypatch.setattr(
        notion_exporters,
        "build_paper_account_paths",
        lambda *args, **kwargs: SimpleNamespace(root=account_root),
    )

    with pytest.raises(NotionExportError, match="Manual review template not found"):
        export_manual_review_template_to_notion(
            client=None,
            settings=_settings(),
            mapping_root=_mapping(),
            account_id="paper_pilot_202606",
            review_date="2026-06-05",
            dry_run=True,
        )


def test_manual_execution_template_export_builds_draft_candidates_from_daily_plan(tmp_path):
    root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_daily_plan_sidecar(root)
    client = FakeManualReviewTemplateClient()

    summary = export_manual_execution_template_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_pilot_202606",
        paper_root=root,
        date_str="2026-06-08",
        dry_run=True,
    )

    assert summary["target"] == "manual_execution_template"
    assert summary["account_id"] == "paper_pilot_202606"
    assert summary["execution_date"] == "2026-06-08"
    assert summary["linked_daily_plan_key"] == "daily_plan:paper_pilot_202606:2026-06-08"
    assert summary["candidate_count"] == 2
    assert summary["create_count"] == 2
    assert summary["would_write"] is False
    first = summary["candidates"][0]
    assert first["external_key"] == "manual_execution:paper_pilot_202606:2026-06-08:MAA:BUY:01"
    assert first["account_id"] == "paper_pilot_202606"
    assert first["status"] == "DRAFT"
    assert first["import_status"] == "DRAFT"
    assert first["actual_price"] is None
    assert first["commission"] == 0
    assert first["currency"] == "USD"
    assert first["broker"] == "PAPER"
    assert "plan_price=135.37" in first["note"]
    assert "STRATEGY_ENTRY" in first["note"]
    assert client.create_calls == []
    assert client.update_calls == []


def test_manual_execution_template_properties_leave_actual_price_blank(tmp_path):
    root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_daily_plan_sidecar(root)
    summary = export_manual_execution_template_to_notion(
        client=FakeManualReviewTemplateClient(),
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_pilot_202606",
        paper_root=root,
        date_str="2026-06-08",
        dry_run=True,
    )
    candidate = notion_exporters.ManualExecutionTemplateExportCandidate(
        external_key=summary["candidates"][0]["external_key"],
        action="create",
        page_id=None,
        account_id="paper_pilot_202606",
        execution_date="2026-06-08",
        plan_date="2026-06-08",
        symbol="MAA",
        side="BUY",
        quantity=73,
        plan_price=135.37,
        note=summary["candidates"][0]["note"],
    )
    properties = build_manual_execution_template_properties(candidate, _mapping()["manual_executions"])

    assert "Actual Price" not in properties
    assert properties["Status"]["select"]["name"] == "DRAFT"
    assert properties["Import Status"]["select"]["name"] == "DRAFT"
    assert properties["Linked Daily Plan Key"]["rich_text"][0]["text"]["content"] == (
        "daily_plan:paper_pilot_202606:2026-06-08"
    )


def test_manual_execution_template_actual_export_uses_schema_compatible_import_status_and_broker(tmp_path):
    root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_daily_plan_sidecar(root, items=[{"symbol": "MAA", "action": "BUY", "quantity": 73, "price": 135.37}])
    schema = {
        "properties": {
            "Import Status": {
                "type": "select",
                "select": {
                    "options": [
                        {"name": "NOT_IMPORTED"},
                        {"name": "PREVIEWED"},
                        {"name": "COMMITTED"},
                        {"name": "SKIPPED"},
                    ]
                },
            },
            "Broker": {"type": "rich_text", "rich_text": {}},
        }
    }
    client = FakeManualReviewTemplateClient(schema=schema)

    summary = export_manual_execution_template_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_pilot_202606",
        paper_root=root,
        date_str="2026-06-08",
        dry_run=False,
    )

    assert summary["initial_import_status"] == "NOT_IMPORTED"
    assert summary["created_count"] == 1
    properties = client.create_calls[0][1]
    assert properties["Status"]["select"]["name"] == "DRAFT"
    assert properties["Import Status"]["select"]["name"] == "NOT_IMPORTED"
    assert properties["Broker"]["rich_text"][0]["text"]["content"] == "PAPER"


def test_manual_execution_template_export_rejects_account_mismatch(tmp_path):
    root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_daily_plan_sidecar(root, account_id="paper_other")

    with pytest.raises(NotionExportError, match="account_id mismatch"):
        export_manual_execution_template_to_notion(
            client=FakeManualReviewTemplateClient(),
            settings=_settings(),
            mapping_root=_mapping(),
            account_id="paper_pilot_202606",
            paper_root=root,
            date_str="2026-06-08",
            dry_run=True,
        )


def test_manual_execution_template_export_rejects_missing_sidecar_account_id(tmp_path):
    root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    path = _seed_daily_plan_sidecar(root)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("account_id")
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(NotionExportError, match="account_id is required"):
        export_manual_execution_template_to_notion(
            client=FakeManualReviewTemplateClient(),
            settings=_settings(),
            mapping_root=_mapping(),
            account_id="paper_pilot_202606",
            paper_root=root,
            date_str="2026-06-08",
            dry_run=True,
        )


def test_manual_execution_template_export_marks_existing_external_key_as_update(tmp_path):
    root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_daily_plan_sidecar(root)
    existing_key = "manual_execution:paper_pilot_202606:2026-06-08:MAA:BUY:01"
    client = FakeManualReviewTemplateClient(existing_keys={existing_key: "page-existing"})

    summary = export_manual_execution_template_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_pilot_202606",
        paper_root=root,
        date_str="2026-06-08",
        dry_run=True,
    )

    assert summary["candidate_count"] == 2
    assert summary["update_count"] == 1
    update_candidate = [item for item in summary["candidates"] if item["action"] == "update"][0]
    assert update_candidate["external_key"] == existing_key
    assert update_candidate["page_id"] == "page-existing"


def test_manual_execution_template_export_empty_items_returns_zero_candidates(tmp_path):
    root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_daily_plan_sidecar(root, items=[])

    summary = export_manual_execution_template_to_notion(
        client=FakeManualReviewTemplateClient(),
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_pilot_202606",
        paper_root=root,
        date_str="2026-06-08",
        dry_run=True,
    )

    assert summary["candidate_count"] == 0
    assert summary["failed_count"] == 0


def test_manual_execution_template_export_uses_official_candidate_schema(tmp_path):
    root = tmp_path / "paper_accounts" / "paper_pilot_202606"
    _seed_daily_plan_sidecar(
        root,
        items=[
            {"symbol": "AAPL", "action": "BUY", "quantity": 10, "price": 100.0},
            {"symbol": "MSFT", "action": "SELL", "quantity": 2, "price": 200.0},
            {"symbol": "NVDA", "type": "BUY", "shares": 1, "price": 300.0},
            {"symbol": "TSLA", "action": "EXECUTE", "status": "PENDING", "side": "BUY", "quantity": 3},
            {"symbol": "GOOG", "action": "BUY", "quantity": 0},
        ],
    )

    summary = export_manual_execution_template_to_notion(
        client=FakeManualReviewTemplateClient(),
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_pilot_202606",
        paper_root=root,
        date_str="2026-06-08",
        dry_run=True,
    )

    assert summary["candidate_count"] == 2
    assert [item["symbol"] for item in summary["candidates"]] == ["AAPL", "MSFT"]
    assert summary["failed_count"] == 1


def test_paper_default_legacy_page_can_be_reused(tmp_path):
    root = tmp_path / "paper_test"
    _seed_daily_plan(root)
    client = FakeFallbackClient(legacy_hits=[{"id": "legacy-page-1"}])
    result = export_daily_plan_to_notion(
        client=client,
        settings=_settings(),
        mapping_root=_mapping(),
        account_id="paper_default",
        paper_root=root,
        dry_run=False,
    )
    assert result.action == "updated"
    assert result.page_id == "legacy-page-1"
    assert result.legacy_fallback_used is True
    assert client.query_calls == [
        "daily_plan:paper_default:2026-05-20",
        "daily_plan:2026-05-20",
    ]
