from __future__ import annotations

from core.notion_mapping import get_mapping_section, load_notion_property_mapping, resolve_notion_property_name


def test_daily_ops_status_mapping_contains_required_keys():
    mapping = load_notion_property_mapping(fallback_to_example=True)
    section = get_mapping_section(mapping, "daily_ops_status")

    expected_keys = {
        "name",
        "external_key",
        "account_id",
        "status_date",
        "workflow_status",
        "review_progress_status",
        "review_completion_ratio",
        "next_recommended_command",
        "blocking_reason",
        "plan_exists",
        "current_state_exists",
        "account_snapshot_exists",
        "position_snapshot_exists",
        "execution_log_rows_for_date",
        "reports_ready",
        "daily_review_summary_exists",
        "performance_summary_exists",
        "review_template_exists",
        "review_template_row_count",
        "review_validation_result",
        "manual_review_log_exists",
        "manual_review_log_row_count",
        "review_answered_row_count",
        "review_pending_row_count",
        "last_status_checked_at",
        "sync_status",
        "synced_at",
        "schema_version",
        "source_root",
    }

    assert expected_keys.issubset(set(section.keys()))


def test_daily_ops_status_mapping_resolves_core_property_names():
    mapping = load_notion_property_mapping(fallback_to_example=True)
    section = get_mapping_section(mapping, "daily_ops_status")

    assert resolve_notion_property_name(section, "external_key") == "External Key"
    assert resolve_notion_property_name(section, "account_id") == "Account ID"
    assert resolve_notion_property_name(section, "workflow_status") == "Workflow Status"
    assert resolve_notion_property_name(section, "review_progress_status") == "Review Progress Status"
    assert resolve_notion_property_name(section, "sync_status") == "Sync Status"
