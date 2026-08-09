from __future__ import annotations

from core.notion_schema_validator import (
    FAIL,
    PASS,
    WARNING,
    build_expected_schema,
    validate_data_source_schema,
    validate_selected_data_sources,
    validation_results_to_json,
)
from core.notion_settings import NotionSettings


def _mapping() -> dict[str, dict[str, str]]:
    return {
        "weekly_reports": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
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
        "manual_executions": {
            "name": "Name",
            "account_id": "Account ID",
            "execution_date": "Execution Date",
            "symbol": "Symbol",
            "side": "Side",
            "quantity": "Quantity",
            "actual_price": "Actual Price",
            "status": "Status",
            "external_key": "External Key",
            "plan_date": "Plan Date",
            "commission": "Commission",
            "currency": "Currency",
            "broker": "Broker",
            "note": "Note",
            "linked_daily_plan_key": "Linked Daily Plan Key",
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
        "daily_ops_status": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "status_date": "Status Date",
            "workflow_status": "Workflow Status",
            "review_progress_status": "Review Progress Status",
            "review_completion_ratio": "Review Completion Ratio",
            "next_recommended_command": "Next Recommended Command",
            "blocking_reason": "Blocking Reason",
            "plan_exists": "Plan Exists",
            "current_state_exists": "Current State Exists",
            "account_snapshot_exists": "Account Snapshot Exists",
            "position_snapshot_exists": "Position Snapshot Exists",
            "execution_log_rows_for_date": "Execution Log Rows For Date",
            "reports_ready": "Reports Ready",
            "daily_review_summary_exists": "Daily Review Summary Exists",
            "performance_summary_exists": "Performance Summary Exists",
            "review_template_exists": "Review Template Exists",
            "review_template_row_count": "Review Template Row Count",
            "review_validation_result": "Review Validation Result",
            "manual_review_log_exists": "Manual Review Log Exists",
            "manual_review_log_row_count": "Manual Review Log Row Count",
            "review_answered_row_count": "Review Answered Row Count",
            "review_pending_row_count": "Review Pending Row Count",
            "last_status_checked_at": "Last Status Checked At",
            "sync_status": "Sync Status",
            "synced_at": "Synced At",
            "schema_version": "Schema Version",
            "source_root": "Source Root",
        },
    }


def _property(name: str, property_type: str, *, options: list[str] | None = None) -> dict:
    payload = {"id": f"id-{name}", "name": name, "type": property_type}
    if property_type in {"select", "multi_select"}:
        payload[property_type] = {
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
            "Account ID": _property("Account ID", "select", options=["paper_default"]),
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
            "Account ID": _property("Account ID", "select", options=["paper_default"]),
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


def _manual_execution_schema(*, broker_type="select", currency_options=None) -> dict:
    broker_property = _property("Broker", broker_type)
    return {
        "properties": {
            "Name": _property("Name", "title"),
            "Account ID": _property("Account ID", "select", options=["paper_default"]),
            "Execution Date": _property("Execution Date", "date"),
            "Symbol": _property("Symbol", "rich_text"),
            "Side": _property("Side", "select", options=["BUY", "SELL"]),
            "Quantity": _property("Quantity", "number"),
            "Actual Price": _property("Actual Price", "number"),
            "Status": _property("Status", "select", options=["DRAFT", "READY", "IMPORTED", "REJECTED"]),
            "External Key": _property("External Key", "rich_text"),
            "Plan Date": _property("Plan Date", "date"),
            "Commission": _property("Commission", "number"),
            "Currency": _property("Currency", "select", options=currency_options or ["USD", "KRW"]),
            "Broker": broker_property,
            "Note": _property("Note", "rich_text"),
            "Linked Daily Plan Key": _property("Linked Daily Plan Key", "rich_text"),
            "Validation Status": _property("Validation Status", "select", options=["NOT_CHECKED", "PASS", "WARNING", "FAIL"]),
            "Validation Message": _property("Validation Message", "rich_text"),
            "Import Status": _property("Import Status", "select", options=["NOT_IMPORTED", "PREVIEWED", "COMMITTED", "SKIPPED"]),
            "Imported At": _property("Imported At", "rich_text"),
            "Synced At": _property("Synced At", "rich_text"),
        }
    }


def _daily_review_schema(*, review_options=None, availability_options=None, sync_options=None) -> dict:
    return {
        "properties": {
            "Name": _property("Name", "title"),
            "External Key": _property("External Key", "rich_text"),
            "Account ID": _property("Account ID", "select", options=["paper_default"]),
            "Review Date": _property("Review Date", "date"),
            "Review Status": _property("Review Status", "select", options=review_options or ["PASS", "PASS_WITH_WARNINGS", "FAIL", "NO_ACTIVITY"]),
            "Availability Status": _property("Availability Status", "select", options=availability_options or ["AVAILABLE", "NO_COMMIT_REPORT", "NO_MANUAL_EXECUTIONS", "PARTIAL", "UNKNOWN"]),
            "Committed Trade Count": _property("Committed Trade Count", "number"),
            "Warning Count": _property("Warning Count", "number"),
            "Fail Count": _property("Fail Count", "number"),
            "Cash Start": _property("Cash Start", "number"),
            "Cash End": _property("Cash End", "number"),
            "Cash Impact": _property("Cash Impact", "number"),
            "Position Impact Summary": _property("Position Impact Summary", "rich_text"),
            "Commit Report Path": _property("Commit Report Path", "rich_text"),
            "Preview Report Path": _property("Preview Report Path", "rich_text"),
            "Latest Snapshot Date": _property("Latest Snapshot Date", "date"),
            "Schema Version": _property("Schema Version", "rich_text"),
            "Synced At": _property("Synced At", "rich_text"),
            "Sync Status": _property("Sync Status", "select", options=sync_options or ["SYNCED"]),
        }
    }


def _manual_review_schema(*, follow_up_type="select", review_tag_type="multi_select", import_options=None) -> dict:
    follow_up_property = (
        _property("Follow-up Needed", "checkbox")
        if follow_up_type == "checkbox"
        else _property("Follow-up Needed", "select", options=["true", "false"])
    )
    review_tag_property = (
        _property(
            "Review Tag",
            "multi_select",
            options=[
                "exit_rule", "entry_rule", "position_sizing", "market_regime", "risk_management",
                "data_quality", "execution_quality", "signal_quality", "psychology", "other",
                "position_follow_up",
            ],
        )
        if review_tag_type == "multi_select"
        else _property("Review Tag", "select", options=["entry_rule", "other"])
    )
    return {
        "properties": {
            "Name": _property("Name", "title"),
            "External Key": _property("External Key", "rich_text"),
            "Account ID": _property("Account ID", "select", options=["paper_default"]),
            "Review Date": _property("Review Date", "date"),
            "Symbol": _property("Symbol", "rich_text"),
            "Question ID": _property("Question ID", "rich_text"),
            "Question": _property("Question", "rich_text"),
            "Manual Answer": _property("Manual Answer", "rich_text"),
            "Review Status": _property("Review Status", "select", options=["pending", "reviewed", "deferred", "not_applicable"]),
            "Follow-up Needed": follow_up_property,
            "Review Tag": review_tag_property,
            "Reviewer Note": _property("Reviewer Note", "rich_text"),
            "Source Template Key": _property("Source Template Key", "rich_text"),
            "Validation Status": _property("Validation Status", "select", options=["NOT_CHECKED", "PASS", "WARNING", "FAIL"]),
            "Validation Message": _property("Validation Message", "rich_text"),
            "Import Status": _property("Import Status", "select", options=import_options or ["DRAFT", "READY", "PREVIEWED", "COMMITTED", "SKIPPED"]),
            "Imported At": _property("Imported At", "rich_text"),
            "Synced At": _property("Synced At", "rich_text"),
        }
    }


def _daily_ops_status_schema(*, workflow_options=None, review_progress_options=None, sync_options=None) -> dict:
    return {
        "properties": {
            "Name": _property("Name", "title"),
            "External Key": _property("External Key", "rich_text"),
            "Account ID": _property("Account ID", "select", options=["paper_default"]),
            "Status Date": _property("Status Date", "date"),
            "Workflow Status": _property(
                "Workflow Status",
                "select",
                options=workflow_options or [
                    "NO_PLAN",
                    "PLAN_READY",
                    "COMMITTED",
                    "REVIEW_READY",
                    "REVIEW_PARTIAL",
                    "REVIEW_DONE",
                    "UNKNOWN_OR_INCOMPLETE",
                ],
            ),
            "Review Progress Status": _property(
                "Review Progress Status",
                "select",
                options=review_progress_options or [
                    "NOT_STARTED",
                    "READY",
                    "PARTIAL",
                    "DONE",
                    "UNKNOWN",
                    "NOT_APPLICABLE",
                ],
            ),
            "Review Completion Ratio": _property("Review Completion Ratio", "number"),
            "Next Recommended Command": _property("Next Recommended Command", "rich_text"),
            "Blocking Reason": _property("Blocking Reason", "rich_text"),
            "Plan Exists": _property("Plan Exists", "checkbox"),
            "Current State Exists": _property("Current State Exists", "checkbox"),
            "Account Snapshot Exists": _property("Account Snapshot Exists", "checkbox"),
            "Position Snapshot Exists": _property("Position Snapshot Exists", "checkbox"),
            "Execution Log Rows For Date": _property("Execution Log Rows For Date", "number"),
            "Reports Ready": _property("Reports Ready", "checkbox"),
            "Daily Review Summary Exists": _property("Daily Review Summary Exists", "checkbox"),
            "Performance Summary Exists": _property("Performance Summary Exists", "checkbox"),
            "Review Template Exists": _property("Review Template Exists", "checkbox"),
            "Review Template Row Count": _property("Review Template Row Count", "number"),
            "Review Validation Result": _property("Review Validation Result", "select", options=["PASS", "FAIL"]),
            "Manual Review Log Exists": _property("Manual Review Log Exists", "checkbox"),
            "Manual Review Log Row Count": _property("Manual Review Log Row Count", "number"),
            "Review Answered Row Count": _property("Review Answered Row Count", "number"),
            "Review Pending Row Count": _property("Review Pending Row Count", "number"),
            "Last Status Checked At": _property("Last Status Checked At", "date"),
            "Sync Status": _property("Sync Status", "select", options=sync_options or ["DRY_RUN", "SYNCED", "FAILED", "SKIPPED"]),
            "Synced At": _property("Synced At", "date"),
            "Schema Version": _property("Schema Version", "rich_text"),
            "Source Root": _property("Source Root", "rich_text"),
        }
    }


def test_expected_schema_is_built_for_all_targets():
    schema = build_expected_schema(_mapping())
    assert set(schema.keys()) == {
        "weekly_reports",
        "benchmark_reports",
        "account_snapshots",
        "daily_plans",
        "manual_executions",
        "manual_reviews",
        "daily_review_summaries",
        "daily_ops_status",
    }


def test_validate_schema_passes_when_all_required_properties_match():
    result = validate_data_source_schema(
        target="weekly_reports",
        data_source_id="ds-weekly",
        actual_schema=_weekly_schema(),
        mapping_root=_mapping(),
    )
    assert result.status == PASS
    assert result.issues == []


def test_account_id_missing_is_warning_for_weekly_reports():
    schema = _weekly_schema()
    schema["properties"].pop("Account ID")
    result = validate_data_source_schema(
        target="weekly_reports",
        data_source_id="ds-weekly",
        actual_schema=schema,
        mapping_root=_mapping(),
    )
    assert result.status == WARNING
    assert any(issue.property_name == "Account ID" for issue in result.issues)
    assert any(issue.code == "recommended_property_missing" for issue in result.issues)


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


def test_manual_execution_schema_passes_when_required_properties_match():
    result = validate_data_source_schema(
        target="manual_executions",
        data_source_id="ds-manual",
        actual_schema=_manual_execution_schema(),
        mapping_root=_mapping(),
    )
    assert result.status == PASS
    assert result.issues == []


def test_manual_execution_account_id_missing_is_warning():
    schema = _manual_execution_schema()
    schema["properties"].pop("Account ID")
    result = validate_data_source_schema(
        target="manual_executions",
        data_source_id="ds-manual",
        actual_schema=schema,
        mapping_root=_mapping(),
    )
    assert result.status == WARNING
    assert any(issue.property_name == "Account ID" for issue in result.issues)


def test_manual_execution_optional_broker_accepts_rich_text():
    result = validate_data_source_schema(
        target="manual_executions",
        data_source_id="ds-manual",
        actual_schema=_manual_execution_schema(broker_type="rich_text"),
        mapping_root=_mapping(),
    )
    assert result.status == PASS


def test_manual_execution_required_property_missing_is_fail():
    schema = _manual_execution_schema()
    schema["properties"].pop("Actual Price")
    result = validate_data_source_schema(
        target="manual_executions",
        data_source_id="ds-manual",
        actual_schema=schema,
        mapping_root=_mapping(),
    )
    assert result.status == FAIL
    assert any(issue.property_name == "Actual Price" for issue in result.issues)


def test_manual_execution_missing_select_options_is_warning():
    result = validate_data_source_schema(
        target="manual_executions",
        data_source_id="ds-manual",
        actual_schema=_manual_execution_schema(currency_options=["USD"]),
        mapping_root=_mapping(),
    )
    assert result.status == WARNING
    assert any(issue.code == "missing_select_options" for issue in result.issues)


def test_daily_review_schema_passes_when_required_properties_match():
    result = validate_data_source_schema(
        target="daily_review_summaries",
        data_source_id="ds-review",
        actual_schema=_daily_review_schema(),
        mapping_root=_mapping(),
    )
    assert result.status == PASS
    assert result.issues == []


def test_daily_review_missing_property_is_fail():
    schema = _daily_review_schema()
    schema["properties"].pop("Cash Impact")
    result = validate_data_source_schema(
        target="daily_review_summaries",
        data_source_id="ds-review",
        actual_schema=schema,
        mapping_root=_mapping(),
    )
    assert result.status == FAIL
    assert any(issue.property_name == "Cash Impact" for issue in result.issues)


def test_daily_review_missing_select_options_is_warning():
    result = validate_data_source_schema(
        target="daily_review_summaries",
        data_source_id="ds-review",
        actual_schema=_daily_review_schema(review_options=["PASS"], availability_options=["AVAILABLE"], sync_options=[]),
        mapping_root=_mapping(),
    )
    assert result.status == WARNING
    assert any(issue.code == "missing_select_options" for issue in result.issues)


def test_manual_review_schema_passes_when_required_properties_match():
    result = validate_data_source_schema(
        target="manual_reviews",
        data_source_id="ds-manual-review",
        actual_schema=_manual_review_schema(),
        mapping_root=_mapping(),
    )
    assert result.status == PASS
    assert result.issues == []


def test_manual_review_account_id_missing_is_warning():
    schema = _manual_review_schema()
    schema["properties"].pop("Account ID")
    result = validate_data_source_schema(
        target="manual_reviews",
        data_source_id="ds-manual-review",
        actual_schema=schema,
        mapping_root=_mapping(),
    )
    assert result.status == WARNING
    assert any(issue.property_name == "Account ID" for issue in result.issues)


def test_manual_review_follow_up_checkbox_is_rejected_but_multi_select_tag_is_accepted():
    result = validate_data_source_schema(
        target="manual_reviews",
        data_source_id="ds-manual-review",
        actual_schema=_manual_review_schema(follow_up_type="checkbox", review_tag_type="multi_select"),
        mapping_root=_mapping(),
    )
    assert result.status == FAIL
    assert any(issue.property_name == "Follow-up Needed" for issue in result.issues)


def test_manual_review_missing_required_property_is_fail():
    schema = _manual_review_schema()
    schema["properties"].pop("Manual Answer")
    result = validate_data_source_schema(
        target="manual_reviews",
        data_source_id="ds-manual-review",
        actual_schema=schema,
        mapping_root=_mapping(),
    )
    assert result.status == FAIL
    assert any(issue.property_name == "Manual Answer" for issue in result.issues)


def test_manual_review_missing_select_options_is_warning():
    result = validate_data_source_schema(
        target="manual_reviews",
        data_source_id="ds-manual-review",
        actual_schema=_manual_review_schema(import_options=["READY"]),
        mapping_root=_mapping(),
    )
    assert result.status == WARNING
    assert any(issue.code == "missing_select_options" for issue in result.issues)


def test_daily_ops_status_schema_passes_when_required_properties_match():
    result = validate_data_source_schema(
        target="daily_ops_status",
        data_source_id="ds-daily-ops",
        actual_schema=_daily_ops_status_schema(),
        mapping_root=_mapping(),
    )
    assert result.status == PASS
    assert result.issues == []


def test_daily_ops_status_missing_select_options_is_warning():
    result = validate_data_source_schema(
        target="daily_ops_status",
        data_source_id="ds-daily-ops",
        actual_schema=_daily_ops_status_schema(
            workflow_options=["REVIEW_DONE"],
            review_progress_options=["DONE"],
            sync_options=["SYNCED"],
        ),
        mapping_root=_mapping(),
    )
    assert result.status == WARNING
    assert any(issue.code == "missing_select_options" for issue in result.issues)


def test_daily_ops_status_missing_data_source_id_is_warning_and_skipped():
    class _FakeClient:
        def get_data_source_schema(self, data_source_id: str) -> dict:
            raise AssertionError(f"unexpected schema fetch for {data_source_id}")

    settings = NotionSettings(
        enabled=False,
        token_env="NOTION_TOKEN",
        data_sources={},
    )
    results = validate_selected_data_sources(
        client=_FakeClient(),
        settings=settings,
        mapping_root=_mapping(),
        targets=["daily_ops_status"],
        env={},
    )
    assert len(results) == 1
    assert results[0].target == "daily_ops_status"
    assert results[0].status == WARNING
    assert any(issue.code == "missing_data_source_id" for issue in results[0].issues)
