from __future__ import annotations

import json

import pytest

from core.notion_daily_ops_status_exporter import NotionDailyOpsStatusExportError
from scripts import export_paper_to_notion


def test_daily_ops_status_cli_requires_dry_run(capsys):
    with pytest.raises(SystemExit) as excinfo:
        export_paper_to_notion.main(["--daily-ops-status"])
    assert excinfo.value.code == 2
    err = capsys.readouterr().err
    assert "--dry-run or --confirm-actual is required for --daily-ops-status" in err


def test_daily_ops_status_cli_prints_json_summary(monkeypatch, capsys):
    captured: dict[str, object] = {}

    def fake_load_settings(allow_missing=True):
        return object()

    def fake_load_mapping():
        return {"daily_ops_status": {}}

    def fake_export_daily_ops_status_dry_run(**kwargs):
        captured.update(kwargs)
        return {
            "target": "daily_ops_status",
            "dry_run": True,
            "would_write": False,
            "account_id": "paper_sandbox",
            "status_date": "2026-05-20",
            "external_key": "daily_ops_status:paper_sandbox:2026-05-20",
            "workflow_status": "REVIEW_PARTIAL",
            "review_progress_status": "PARTIAL",
            "data_source_key": "daily_ops_status",
            "data_source_id": "",
            "data_source_configured": False,
            "notion_properties": {
                "Workflow Status": {"select": {"name": "REVIEW_PARTIAL"}},
                "Review Progress Status": {"select": {"name": "PARTIAL"}},
                "Sync Status": {"select": {"name": "DRY_RUN"}},
            },
            "source_status": {"workflow_status": "REVIEW_PARTIAL"},
        }

    monkeypatch.setattr(export_paper_to_notion, "load_notion_settings", fake_load_settings)
    monkeypatch.setattr(export_paper_to_notion, "load_notion_property_mapping", fake_load_mapping)
    monkeypatch.setattr(export_paper_to_notion, "export_daily_ops_status_dry_run", fake_export_daily_ops_status_dry_run)

    rc = export_paper_to_notion.main(
        ["--daily-ops-status", "--account-id", "paper_sandbox", "--date", "20260520", "--dry-run", "--json"]
    )

    assert rc == 0
    assert captured["account_id"] == "paper_sandbox"
    assert captured["date_str"] == "20260520"
    output = capsys.readouterr().out
    assert "daily_ops_status: account_id=paper_sandbox" in output
    payload = json.loads(output[output.index("{") :])
    assert payload["target"] == "daily_ops_status"
    assert payload["workflow_status"] == "REVIEW_PARTIAL"
    assert payload["review_progress_status"] == "PARTIAL"
    assert payload["would_write"] is False


def test_daily_ops_status_cli_rejects_actual_without_paper_sandbox(monkeypatch):
    monkeypatch.setattr(export_paper_to_notion, "load_notion_settings", lambda allow_missing=True: object())
    monkeypatch.setattr(export_paper_to_notion, "load_notion_property_mapping", lambda: {"daily_ops_status": {}})
    monkeypatch.setattr(export_paper_to_notion, "get_notion_token", lambda settings: "token")
    monkeypatch.setattr(export_paper_to_notion, "NotionClient", lambda token: object())

    def fake_actual(**kwargs):
        raise NotionDailyOpsStatusExportError(
            "Daily Ops Status actual export is limited to account_id=paper_sandbox in this stage."
        )

    monkeypatch.setattr(export_paper_to_notion, "export_daily_ops_status_actual", fake_actual)
    rc = export_paper_to_notion.main(
        ["--daily-ops-status", "--account-id", "paper_default", "--confirm-actual", "--json"]
    )
    assert rc == 1


def test_daily_ops_status_cli_actual_prints_json_summary(monkeypatch, capsys):
    monkeypatch.setattr(export_paper_to_notion, "load_notion_settings", lambda allow_missing=True: object())
    monkeypatch.setattr(export_paper_to_notion, "load_notion_property_mapping", lambda: {"daily_ops_status": {}})
    monkeypatch.setattr(export_paper_to_notion, "get_notion_token", lambda settings: "token")
    monkeypatch.setattr(export_paper_to_notion, "NotionClient", lambda token: object())
    monkeypatch.setattr(
        export_paper_to_notion,
        "export_daily_ops_status_actual",
        lambda **kwargs: {
            "target": "daily_ops_status",
            "dry_run": False,
            "actual_export": True,
            "would_write": True,
            "account_id": "paper_sandbox",
            "status_date": "2026-05-20",
            "external_key": "daily_ops_status:paper_sandbox:2026-05-20",
            "action": "update",
            "page_id": "page-123",
            "workflow_status": "REVIEW_PARTIAL",
            "review_progress_status": "PARTIAL",
            "sync_status": "SYNCED",
            "synced_at": "2026-06-01T00:00:00+00:00",
            "data_source_configured": True,
            "notion_properties": {"Sync Status": {"select": {"name": "SYNCED"}}},
            "source_status": {"workflow_status": "REVIEW_PARTIAL"},
        },
    )

    rc = export_paper_to_notion.main(
        ["--daily-ops-status", "--account-id", "paper_sandbox", "--confirm-actual", "--json"]
    )

    assert rc == 0
    output = capsys.readouterr().out
    payload = json.loads(output[output.index("{") :])
    assert payload["actual_export"] is True
    assert payload["action"] == "update"
    assert payload["page_id"] == "page-123"
    assert payload["sync_status"] == "SYNCED"
