from __future__ import annotations

from core.notion_schema_validator import (
    FAIL,
    PASS,
    WARNING,
    build_expected_schema,
    validate_data_source_schema,
    validation_results_to_json,
)


def _mapping() -> dict[str, dict[str, str]]:
    return {
        "weekly_reports": {
            "name": "Name",
            "external_key": "External Key",
            "period.actual_start": "Period Start",
            "period.actual_end": "Period End",
            "latest_snapshot_date": "Latest Snapshot Date",
            "overall_status": "Overall Status",
            "period.coverage_status": "Coverage Status",
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


def _property(name: str, property_type: str, *, options: list[str] | None = None) -> dict:
    payload = {"id": f"id-{name}", "name": name, "type": property_type}
    if property_type == "select":
        payload["select"] = {
            "options": [{"name": option} for option in (options or [])]
        }
    else:
        payload[property_type] = {}
    return payload


def _weekly_schema(*, coverage_options=None, overall_options=None, sync_options=None) -> dict:
    return {
        "properties": {
            "Name": _property("Name", "title"),
            "External Key": _property("External Key", "rich_text"),
            "Period Start": _property("Period Start", "date"),
            "Period End": _property("Period End", "date"),
            "Latest Snapshot Date": _property("Latest Snapshot Date", "date"),
            "Coverage Status": _property("Coverage Status", "select", options=coverage_options or ["FULL", "PARTIAL", "EMPTY"]),
            "Overall Status": _property("Overall Status", "select", options=overall_options or ["PASS", "PASS_WITH_WARNINGS", "FAIL"]),
            "Snapshot Count": _property("Snapshot Count", "number"),
            "End Equity": _property("End Equity", "number"),
            "Equity Change %": _property("Equity Change %", "number"),
            "Cash Ratio": _property("Cash Ratio", "number"),
            "Trade Count": _property("Trade Count", "number"),
            "Gap Count": _property("Gap Count", "number"),
            "High Gap Count": _property("High Gap Count", "number"),
            "Markdown Path": _property("Markdown Path", "rich_text"),
            "JSON Path": _property("JSON Path", "rich_text"),
            "Schema Version": _property("Schema Version", "rich_text"),
            "Synced At": _property("Synced At", "rich_text"),
            "Sync Status": _property("Sync Status", "select", options=sync_options or ["SYNCED"]),
        }
    }


def _daily_plan_schema(*, sync_options=None) -> dict:
    return {
        "properties": {
            "Name": _property("Name", "title"),
            "External Key": _property("External Key", "rich_text"),
            "Plan Date": _property("Plan Date", "date"),
            "Regime": _property("Regime", "select", options=["BULL", "BEAR", "PANIC"]),
            "Confirmed Trade Count": _property("Confirmed Trade Count", "number"),
            "Review Item Count": _property("Review Item Count", "number"),
            "Warning Count": _property("Warning Count", "number"),
            "Markdown Path": _property("Markdown Path", "rich_text"),
            "JSON Path": _property("JSON Path", "rich_text"),
            "Schema Version": _property("Schema Version", "rich_text"),
            "Synced At": _property("Synced At", "rich_text"),
            "Sync Status": _property("Sync Status", "select", options=sync_options or ["SYNCED"]),
        }
    }


def test_expected_schema_is_built_for_all_targets():
    schema = build_expected_schema(_mapping())
    assert set(schema.keys()) == {"weekly_reports", "benchmark_reports", "account_snapshots", "daily_plans"}


def test_validate_schema_passes_when_all_required_properties_match():
    result = validate_data_source_schema(
        target="weekly_reports",
        data_source_id="ds-weekly",
        actual_schema=_weekly_schema(),
        mapping_root=_mapping(),
    )
    assert result.status == PASS
    assert result.issues == []


def test_missing_property_is_fail():
    schema = _weekly_schema()
    schema["properties"].pop("Official Run", None)
    schema["properties"].pop("Trade Count")
    result = validate_data_source_schema(
        target="weekly_reports",
        data_source_id="ds-weekly",
        actual_schema=schema,
        mapping_root=_mapping(),
    )
    assert result.status == FAIL
    assert any(issue.code == "missing_property" for issue in result.issues)


def test_type_mismatch_is_fail():
    schema = _weekly_schema()
    schema["properties"]["Synced At"] = _property("Synced At", "date")
    result = validate_data_source_schema(
        target="weekly_reports",
        data_source_id="ds-weekly",
        actual_schema=schema,
        mapping_root=_mapping(),
    )
    assert result.status == FAIL
    assert any(issue.code == "type_mismatch" for issue in result.issues)


def test_missing_select_options_is_warning():
    result = validate_data_source_schema(
        target="weekly_reports",
        data_source_id="ds-weekly",
        actual_schema=_weekly_schema(coverage_options=["PARTIAL"], overall_options=["PASS"], sync_options=[]),
        mapping_root=_mapping(),
    )
    assert result.status == WARNING
    assert all(issue.severity == WARNING for issue in result.issues)
    assert any(issue.code == "missing_select_options" for issue in result.issues)


def test_json_summary_structure_is_stable():
    result = validate_data_source_schema(
        target="weekly_reports",
        data_source_id="ds-weekly",
        actual_schema=_weekly_schema(),
        mapping_root=_mapping(),
    )
    payload = validation_results_to_json([result])
    assert payload["overall_status"] == PASS
    assert payload["results"][0]["target"] == "weekly_reports"
    assert "issues" in payload["results"][0]


def test_daily_plan_schema_passes_when_required_properties_match():
    result = validate_data_source_schema(
        target="daily_plans",
        data_source_id="ds-daily",
        actual_schema=_daily_plan_schema(),
        mapping_root=_mapping(),
    )
    assert result.status == PASS
    assert result.issues == []


def test_daily_plan_missing_property_is_fail():
    schema = _daily_plan_schema()
    schema["properties"].pop("JSON Path")
    result = validate_data_source_schema(
        target="daily_plans",
        data_source_id="ds-daily",
        actual_schema=schema,
        mapping_root=_mapping(),
    )
    assert result.status == FAIL
    assert any(issue.property_name == "JSON Path" for issue in result.issues)


def test_daily_plan_type_mismatch_is_fail():
    schema = _daily_plan_schema()
    schema["properties"]["Regime"] = _property("Regime", "rich_text")
    result = validate_data_source_schema(
        target="daily_plans",
        data_source_id="ds-daily",
        actual_schema=schema,
        mapping_root=_mapping(),
    )
    assert result.status == FAIL
    assert any(issue.code == "type_mismatch" for issue in result.issues)
