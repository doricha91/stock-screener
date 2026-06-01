from __future__ import annotations

from pathlib import Path

import pytest

from core.notion_daily_ops_status_exporter import (
    DAILY_OPS_STATUS_ACTUAL_ALLOWED_ACCOUNT_ID,
    NotionDailyOpsStatusExportError,
    build_daily_ops_status_external_key,
    build_daily_ops_status_payload,
    export_daily_ops_status_actual,
    export_daily_ops_status_dry_run,
)
from core.notion_settings import NotionSettings, NotionSettingsError


def _mapping_root() -> dict[str, dict[str, str]]:
    return {
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
        }
    }


def _status_fixture() -> dict[str, object]:
    return {
        "account_id": "paper_sandbox",
        "account_root": "D:/python/StockScreener/outputs/paper_accounts/paper_sandbox",
        "date": "2026-05-20",
        "workflow_status": "REVIEW_PARTIAL",
        "review_progress_status": "PARTIAL",
        "review_completion_ratio": 0.25,
        "next_recommended_command": "complete pending review rows then paper.py review-append",
        "plan_exists": True,
        "current_state_exists": True,
        "account_snapshot_exists": True,
        "position_snapshot_exists": True,
        "execution_log_rows_for_date": 1,
        "reports_ready": True,
        "paper_daily_review_summary_exists": True,
        "paper_performance_summary_exists": True,
        "review_template_exists": True,
        "review_template_row_count": 4,
        "review_validation_result": "PASS",
        "manual_review_log_exists": True,
        "manual_review_log_row_count": 1,
        "review_answered_row_count": 1,
        "review_pending_row_count": 3,
        "paths": {
            "paper_root": "D:/python/StockScreener/outputs/paper_accounts/paper_sandbox",
        },
    }


def test_daily_ops_status_external_key_is_account_aware():
    assert (
        build_daily_ops_status_external_key("paper_sandbox", "2026-05-20")
        == "daily_ops_status:paper_sandbox:2026-05-20"
    )


def test_build_daily_ops_status_payload_maps_review_partial_status():
    payload = build_daily_ops_status_payload(
        _status_fixture(),
        "paper_sandbox",
        _mapping_root()["daily_ops_status"],
        dry_run=True,
        checked_at="2026-06-01T00:00:00+00:00",
    )
    assert payload["External Key"]["rich_text"][0]["text"]["content"] == "daily_ops_status:paper_sandbox:2026-05-20"
    assert payload["Account ID"]["select"]["name"] == "paper_sandbox"
    assert payload["Workflow Status"]["select"]["name"] == "REVIEW_PARTIAL"
    assert payload["Review Progress Status"]["select"]["name"] == "PARTIAL"
    assert payload["Review Completion Ratio"]["number"] == 0.25
    assert payload["Sync Status"]["select"]["name"] == "DRY_RUN"
    assert payload["Blocking Reason"]["rich_text"][0]["text"]["content"] == "pending review rows remain"
    assert payload["Synced At"]["date"]["start"] == "2026-06-01T00:00:00+00:00"


def test_build_daily_ops_status_payload_requires_resolved_status_date():
    status = _status_fixture()
    status["date"] = None
    with pytest.raises(NotionDailyOpsStatusExportError):
        build_daily_ops_status_payload(
            status,
            "paper_sandbox",
            _mapping_root()["daily_ops_status"],
            dry_run=True,
        )


def test_export_daily_ops_status_dry_run_summary_uses_configured_data_source(monkeypatch, tmp_path: Path):
    class _AccountPaths:
        account_id = "paper_sandbox"
        root = tmp_path / "outputs" / "paper_accounts" / "paper_sandbox"
        legacy_default_used = False

    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.build_paper_account_paths",
        lambda *args, **kwargs: _AccountPaths(),
    )
    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.run_paper_status",
        lambda date_str, account_paths=None: _status_fixture(),
    )
    settings = NotionSettings(
        enabled=False,
        token_env="NOTION_TOKEN",
        data_sources={"daily_ops_status": "ds-daily-ops"},
    )
    summary = export_daily_ops_status_dry_run(
        settings=settings,
        mapping_root=_mapping_root(),
        account_id="paper_sandbox",
        date_str="20260520",
    )
    assert summary["target"] == "daily_ops_status"
    assert summary["dry_run"] is True
    assert summary["would_write"] is False
    assert summary["data_source_configured"] is True
    assert summary["workflow_status"] == "REVIEW_PARTIAL"
    assert summary["review_progress_status"] == "PARTIAL"


def test_export_daily_ops_status_dry_run_defaults_account_id_to_paper_default(monkeypatch, tmp_path: Path):
    class _AccountPaths:
        account_id = "paper_default"
        root = tmp_path / "outputs" / "paper_test"
        legacy_default_used = True

    def fake_status(date_str, account_paths=None):
        status = _status_fixture()
        status["account_id"] = "paper_default"
        status["date"] = "2026-05-21"
        status["workflow_status"] = "PLAN_READY"
        status["review_progress_status"] = "NOT_STARTED"
        status["review_completion_ratio"] = 0.0
        status["manual_review_log_exists"] = False
        status["manual_review_log_row_count"] = 0
        status["review_answered_row_count"] = 0
        status["review_pending_row_count"] = 0
        status["paths"]["paper_root"] = str(_AccountPaths.root)
        return status

    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.build_paper_account_paths",
        lambda *args, **kwargs: _AccountPaths(),
    )
    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.run_paper_status",
        fake_status,
    )
    settings = NotionSettings(enabled=False, token_env="NOTION_TOKEN", data_sources={})
    summary = export_daily_ops_status_dry_run(
        settings=settings,
        mapping_root=_mapping_root(),
        account_id=None,
    )
    assert summary["account_id"] == "paper_default"
    assert summary["external_key"] == "daily_ops_status:paper_default:2026-05-21"
    assert summary["data_source_configured"] is False


def test_export_daily_ops_status_actual_creates_page(monkeypatch, tmp_path: Path):
    class _AccountPaths:
        account_id = DAILY_OPS_STATUS_ACTUAL_ALLOWED_ACCOUNT_ID
        root = tmp_path / "outputs" / "paper_accounts" / DAILY_OPS_STATUS_ACTUAL_ALLOWED_ACCOUNT_ID
        legacy_default_used = False

    class _Client:
        def __init__(self):
            self.schema_reads = 0
            self.upsert_calls: list[dict[str, object]] = []

        def get_data_source_schema(self, data_source_id: str):
            self.schema_reads += 1
            return {
                "properties": {
                    "Name": {"type": "title"},
                    "External Key": {"type": "rich_text"},
                    "Account ID": {"type": "select", "select": {"options": [{"name": "paper_default"}]}},
                    "Status Date": {"type": "date"},
                    "Workflow Status": {"type": "select", "select": {"options": [{"name": "REVIEW_PARTIAL"}]}},
                    "Review Progress Status": {"type": "select", "select": {"options": [{"name": "PARTIAL"}]}},
                    "Review Completion Ratio": {"type": "number"},
                    "Next Recommended Command": {"type": "rich_text"},
                    "Blocking Reason": {"type": "rich_text"},
                    "Plan Exists": {"type": "checkbox"},
                    "Current State Exists": {"type": "checkbox"},
                    "Account Snapshot Exists": {"type": "checkbox"},
                    "Position Snapshot Exists": {"type": "checkbox"},
                    "Execution Log Rows For Date": {"type": "number"},
                    "Reports Ready": {"type": "checkbox"},
                    "Daily Review Summary Exists": {"type": "checkbox"},
                    "Performance Summary Exists": {"type": "checkbox"},
                    "Review Template Exists": {"type": "checkbox"},
                    "Review Template Row Count": {"type": "number"},
                    "Review Validation Result": {"type": "select", "select": {"options": [{"name": "PASS"}]}},
                    "Manual Review Log Exists": {"type": "checkbox"},
                    "Manual Review Log Row Count": {"type": "number"},
                    "Review Answered Row Count": {"type": "number"},
                    "Review Pending Row Count": {"type": "number"},
                    "Last Status Checked At": {"type": "date"},
                    "Sync Status": {"type": "select", "select": {"options": [{"name": "SYNCED"}]}},
                    "Synced At": {"type": "date"},
                    "Schema Version": {"type": "rich_text"},
                    "Source Root": {"type": "rich_text"},
                }
            }

        def upsert_page_by_external_key(self, **kwargs):
            self.upsert_calls.append(kwargs)
            class _Result:
                action = "created"
                page_id = "page-create-1"
                payload = {}
            return _Result()

    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.build_paper_account_paths",
        lambda *args, **kwargs: _AccountPaths(),
    )
    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.run_paper_status",
        lambda date_str, account_paths=None: _status_fixture(),
    )
    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.validate_data_source_schema",
        lambda **kwargs: type("_Validation", (), {"status": "PASS"})(),
    )
    settings = NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={"daily_ops_status": "ds-daily-ops"},
    )
    client = _Client()
    summary = export_daily_ops_status_actual(
        client=client,
        settings=settings,
        mapping_root=_mapping_root(),
        account_id=DAILY_OPS_STATUS_ACTUAL_ALLOWED_ACCOUNT_ID,
        date_str="20260520",
    )
    assert summary["actual_export"] is True
    assert summary["dry_run"] is False
    assert summary["action"] == "create"
    assert summary["page_id"] == "page-create-1"
    assert summary["sync_status"] == "SYNCED"
    assert client.schema_reads == 1
    assert client.upsert_calls[0]["external_key"] == "daily_ops_status:paper_sandbox:2026-05-20"
    properties = client.upsert_calls[0]["properties"]
    assert properties["Sync Status"]["select"]["name"] == "SYNCED"


def test_export_daily_ops_status_actual_updates_existing_page(monkeypatch, tmp_path: Path):
    class _AccountPaths:
        account_id = DAILY_OPS_STATUS_ACTUAL_ALLOWED_ACCOUNT_ID
        root = tmp_path / "outputs" / "paper_accounts" / DAILY_OPS_STATUS_ACTUAL_ALLOWED_ACCOUNT_ID
        legacy_default_used = False

    class _Client:
        def get_data_source_schema(self, data_source_id: str):
            return {
                "properties": {
                    "Name": {"type": "title"},
                    "External Key": {"type": "rich_text"},
                    "Account ID": {"type": "select", "select": {"options": [{"name": "paper_default"}]}},
                    "Status Date": {"type": "date"},
                    "Workflow Status": {"type": "select", "select": {"options": [{"name": "REVIEW_PARTIAL"}]}},
                    "Review Progress Status": {"type": "select", "select": {"options": [{"name": "PARTIAL"}]}},
                    "Review Completion Ratio": {"type": "number"},
                    "Next Recommended Command": {"type": "rich_text"},
                    "Plan Exists": {"type": "checkbox"},
                    "Current State Exists": {"type": "checkbox"},
                    "Account Snapshot Exists": {"type": "checkbox"},
                    "Position Snapshot Exists": {"type": "checkbox"},
                    "Execution Log Rows For Date": {"type": "number"},
                    "Reports Ready": {"type": "checkbox"},
                    "Daily Review Summary Exists": {"type": "checkbox"},
                    "Performance Summary Exists": {"type": "checkbox"},
                    "Review Template Exists": {"type": "checkbox"},
                    "Review Template Row Count": {"type": "number"},
                    "Manual Review Log Exists": {"type": "checkbox"},
                    "Manual Review Log Row Count": {"type": "number"},
                    "Review Answered Row Count": {"type": "number"},
                    "Review Pending Row Count": {"type": "number"},
                    "Last Status Checked At": {"type": "date"},
                    "Schema Version": {"type": "rich_text"},
                    "Source Root": {"type": "rich_text"},
                    "Blocking Reason": {"type": "rich_text"},
                    "Review Validation Result": {"type": "select", "select": {"options": [{"name": "PASS"}]}},
                    "Sync Status": {"type": "select", "select": {"options": [{"name": "SYNCED"}]}},
                    "Synced At": {"type": "date"},
                }
            }

        def upsert_page_by_external_key(self, **kwargs):
            class _Result:
                action = "updated"
                page_id = "page-update-1"
                payload = {}
            return _Result()

    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.build_paper_account_paths",
        lambda *args, **kwargs: _AccountPaths(),
    )
    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.run_paper_status",
        lambda date_str, account_paths=None: _status_fixture(),
    )
    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.validate_data_source_schema",
        lambda **kwargs: type("_Validation", (), {"status": "PASS"})(),
    )
    summary = export_daily_ops_status_actual(
        client=_Client(),
        settings=NotionSettings(enabled=True, token_env="NOTION_TOKEN", data_sources={"daily_ops_status": "ds-daily-ops"}),
        mapping_root=_mapping_root(),
        account_id=DAILY_OPS_STATUS_ACTUAL_ALLOWED_ACCOUNT_ID,
    )
    assert summary["action"] == "update"
    assert summary["page_id"] == "page-update-1"


def test_export_daily_ops_status_actual_rejects_non_sandbox_account(monkeypatch):
    with pytest.raises(NotionDailyOpsStatusExportError):
        export_daily_ops_status_actual(
            client=object(),  # type: ignore[arg-type]
            settings=NotionSettings(enabled=True, token_env="NOTION_TOKEN", data_sources={"daily_ops_status": "ds-daily-ops"}),
            mapping_root=_mapping_root(),
            account_id="paper_default",
        )


def test_export_daily_ops_status_actual_fails_without_configured_data_source(monkeypatch):
    monkeypatch.setattr(
        "core.notion_daily_ops_status_exporter.validate_data_source_schema",
        lambda **kwargs: type("_Validation", (), {"status": "PASS"})(),
    )
    with pytest.raises(NotionSettingsError):
        export_daily_ops_status_actual(
            client=object(),  # type: ignore[arg-type]
            settings=NotionSettings(enabled=True, token_env="NOTION_TOKEN", data_sources={}),
            mapping_root=_mapping_root(),
            account_id=DAILY_OPS_STATUS_ACTUAL_ALLOWED_ACCOUNT_ID,
        )
