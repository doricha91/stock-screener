from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.notion_exporters import (
    NotionExportError,
    build_account_snapshot_external_key,
    build_benchmark_report_external_key,
    build_daily_plan_external_key,
    build_weekly_report_external_key,
    build_account_snapshot_properties,
    build_benchmark_report_properties,
    build_daily_plan_properties,
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


def _seed_daily_plan(root: Path) -> None:
    _write(
        root / "daily_action_plan_20260520.md",
        "\n".join(
            [
                "# Daily Action Plan [2026-05-20]",
                "",
                "## 4. Confirmed Trades",
                "| Type | Symbol | Shares | Ref Price | Reason |",
                "| :--- | :--- | :--- | :--- | :--- |",
                "| BUY | **ABC** | 10 | $12.34 | ENTRY_SIGNAL |",
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
        root / "config_snapshots" / "paper_config_snapshot_20260520.json",
        json.dumps(
            {
                "schema_version": 1,
                "plan_date": "2026-05-20",
                "market_state": {"regime": "BULL"},
                "market_status_summary": {"regime": "BULL"},
            }
        ),
    )


def _mapping() -> dict[str, dict[str, str]]:
    return {
        "weekly_reports": {
            "name": "Name",
            "external_key": "External Key",
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
        },
    )


class FakeClient:
    def __init__(self):
        self.calls: list[dict] = []

    def upsert_page_by_external_key(self, **kwargs):
        self.calls.append(kwargs)
        class Result:
            action = "updated"
            page_id = "page-123"
            payload = {"id": "page-123"}

        return Result()


def test_weekly_external_key_is_generated():
    key = build_weekly_report_external_key({"period": {"actual_start": "2026-05-09", "actual_end": "2026-05-20"}})
    assert key == "weekly_report:2026-05-09:2026-05-20"


def test_benchmark_external_key_is_generated():
    key = build_benchmark_report_external_key({"latest_snapshot_date": "2026-05-20", "run_mode": "exploratory"})
    assert key == "benchmark:2026-05-20:exploratory"


def test_account_snapshot_external_key_is_generated():
    key = build_account_snapshot_external_key({"snapshot_date": "2026-05-20"})
    assert key == "account_snapshot:2026-05-20"


def test_daily_plan_external_key_is_generated():
    key = build_daily_plan_external_key("2026-05-20")
    assert key == "daily_plan:2026-05-20"


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
    assert props["Regime"]["select"]["name"] == "BULL"
    assert props["Confirmed Trade Count"]["number"] == 2


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
    assert result.external_key == "daily_plan:2026-05-20"
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
    assert client.calls[0]["data_source_id"] == "db-weekly"
    assert result.data_source_key == "weekly_reports"


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
    assert result.external_key == "account_snapshot:2026-05-20"
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
    assert result.external_key == "daily_plan:2026-05-20"
    assert result.data_source_key == "daily_plans"
    assert len(client.calls) == 1
    assert client.calls[0]["data_source_id"] == "db-daily-plan"


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


def test_export_selected_requires_target():
    with pytest.raises(NotionExportError):
        export_selected_paper_reports_to_notion(
            client=None,
            settings=_settings(),
            mapping_root=_mapping(),
            dry_run=True,
        )
