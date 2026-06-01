from __future__ import annotations

import pytest

from core.notion_mapping import (
    NotionMappingError,
    get_mapping_section,
    load_notion_property_mapping,
    resolve_notion_property_name,
)


def test_mapping_loader_reads_mapping(tmp_path):
    path = tmp_path / "mapping.json"
    path.write_text('{"smoke_test": {"name": "Name", "external_key": "External Key"}}', encoding="utf-8")
    mapping = load_notion_property_mapping(path, fallback_to_example=False)
    assert mapping["smoke_test"]["name"] == "Name"


def test_missing_mapping_key_raises_error(tmp_path):
    path = tmp_path / "mapping.json"
    path.write_text('{"smoke_test": {"name": "Name"}}', encoding="utf-8")
    mapping = load_notion_property_mapping(path, fallback_to_example=False)
    section = get_mapping_section(mapping, "smoke_test")
    with pytest.raises(NotionMappingError):
        resolve_notion_property_name(section, "external_key")


def test_missing_mapping_section_raises_error(tmp_path):
    path = tmp_path / "mapping.json"
    path.write_text('{"weekly_reports": {"a": "b"}}', encoding="utf-8")
    mapping = load_notion_property_mapping(path, fallback_to_example=False)
    with pytest.raises(NotionMappingError):
        get_mapping_section(mapping, "smoke_test")


def test_example_mapping_contains_account_id_for_multi_account_targets():
    mapping = load_notion_property_mapping(fallback_to_example=True)
    for section in (
        "daily_plans",
        "manual_executions",
        "account_snapshots",
        "weekly_reports",
        "benchmark_reports",
        "daily_review_summaries",
        "manual_reviews",
    ):
        section_mapping = get_mapping_section(mapping, section)
        assert resolve_notion_property_name(section_mapping, "account_id") == "Account ID"


def test_example_mapping_contains_daily_ops_status_section():
    mapping = load_notion_property_mapping(fallback_to_example=True)
    section = get_mapping_section(mapping, "daily_ops_status")
    assert resolve_notion_property_name(section, "external_key") == "External Key"
    assert resolve_notion_property_name(section, "account_id") == "Account ID"
    assert resolve_notion_property_name(section, "workflow_status") == "Workflow Status"
    assert resolve_notion_property_name(section, "review_progress_status") == "Review Progress Status"
