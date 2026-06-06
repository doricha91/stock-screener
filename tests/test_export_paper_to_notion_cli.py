from __future__ import annotations

import json

import pytest

from scripts import export_paper_to_notion


def test_cli_passes_account_id_and_prints_account_aware_summary(monkeypatch, capsys):
    captured: dict[str, object] = {}

    def fake_load_settings(allow_missing=True):
        return object()

    def fake_load_mapping():
        return {"daily_plans": {}}

    def fake_export_selected_paper_reports_to_notion(**kwargs):
        captured.update(kwargs)

        class Result:
            account_id = "paper_default"
            target = "daily_plans"
            external_key = "daily_plan:paper_default:2026-05-20"
            legacy_external_key = "daily_plan:2026-05-20"
            legacy_fallback_used = False
            action = "dry_run"
            page_id = None
            source_path = "outputs/paper_test/config_snapshots/paper_config_snapshot_20260520.json"
            data_source_key = "daily_plans"
            dry_run = True

        return [Result()]

    monkeypatch.setattr(export_paper_to_notion, "load_notion_settings", fake_load_settings)
    monkeypatch.setattr(export_paper_to_notion, "load_notion_property_mapping", fake_load_mapping)
    monkeypatch.setattr(
        export_paper_to_notion,
        "export_selected_paper_reports_to_notion",
        fake_export_selected_paper_reports_to_notion,
    )

    rc = export_paper_to_notion.main(
        ["--daily-plan", "--account-id", "paper_default", "--dry-run", "--json"]
    )

    assert rc == 0
    assert captured["account_id"] == "paper_default"
    output = capsys.readouterr().out
    assert "account_id=paper_default" in output
    json_payload = json.loads(output[output.index("[") :])
    assert json_payload[0]["account_id"] == "paper_default"
    assert json_payload[0]["external_key"] == "daily_plan:paper_default:2026-05-20"
    assert json_payload[0]["legacy_external_key"] == "daily_plan:2026-05-20"
    assert json_payload[0]["legacy_fallback_used"] is False
    assert captured["daily_plan_date"] is None


def test_cli_defaults_account_id_to_paper_default(monkeypatch):
    captured: dict[str, object] = {}

    def fake_load_settings(allow_missing=True):
        return object()

    def fake_load_mapping():
        return {"weekly_reports": {}}

    def fake_export_selected_paper_reports_to_notion(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(export_paper_to_notion, "load_notion_settings", fake_load_settings)
    monkeypatch.setattr(export_paper_to_notion, "load_notion_property_mapping", fake_load_mapping)
    monkeypatch.setattr(
        export_paper_to_notion,
        "export_selected_paper_reports_to_notion",
        fake_export_selected_paper_reports_to_notion,
    )

    rc = export_paper_to_notion.main(["--weekly", "--dry-run"])

    assert rc == 0
    assert captured["account_id"] is None


def test_cli_passes_date_to_daily_plan_export(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(export_paper_to_notion, "load_notion_settings", lambda allow_missing=True: object())
    monkeypatch.setattr(export_paper_to_notion, "load_notion_property_mapping", lambda: {"daily_plans": {}})

    def fake_export_selected_paper_reports_to_notion(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        export_paper_to_notion,
        "export_selected_paper_reports_to_notion",
        fake_export_selected_paper_reports_to_notion,
    )

    rc = export_paper_to_notion.main(
        ["--daily-plan", "--account-id", "paper_pilot_202606", "--date", "2026-06-05", "--dry-run"]
    )

    assert rc == 0
    assert captured["account_id"] == "paper_pilot_202606"
    assert captured["daily_plan_date"] == "2026-06-05"


def test_cli_manual_review_template_requires_dry_run_or_confirm_actual():
    with pytest.raises(SystemExit):
        export_paper_to_notion.main(
            [
                "--manual-review-template",
                "--account-id",
                "paper_pilot_202606",
                "--date",
                "2026-06-05",
            ]
        )


def test_cli_manual_execution_template_requires_date_account_and_guard():
    with pytest.raises(SystemExit):
        export_paper_to_notion.main(
            [
                "--manual-execution-template",
                "--account-id",
                "paper_pilot_202606",
                "--dry-run",
            ]
        )
    with pytest.raises(SystemExit):
        export_paper_to_notion.main(
            [
                "--manual-execution-template",
                "--date",
                "2026-06-08",
                "--dry-run",
            ]
        )
    with pytest.raises(SystemExit):
        export_paper_to_notion.main(
            [
                "--manual-execution-template",
                "--account-id",
                "paper_pilot_202606",
                "--date",
                "2026-06-08",
            ]
        )


def test_cli_manual_execution_template_dry_run_routes_to_exporter(monkeypatch, capsys):
    captured: dict[str, object] = {}

    monkeypatch.setattr(export_paper_to_notion, "load_notion_settings", lambda allow_missing=True: object())
    monkeypatch.setattr(export_paper_to_notion, "load_notion_property_mapping", lambda: {"manual_executions": {}})
    monkeypatch.setattr(export_paper_to_notion, "get_notion_token", lambda settings: "token")
    monkeypatch.setattr(export_paper_to_notion, "NotionClient", lambda token: object())

    def fake_export_manual_execution_template_to_notion(**kwargs):
        captured.update(kwargs)
        return {
            "target": "manual_execution_template",
            "account_id": "paper_pilot_202606",
            "execution_date": "2026-06-08",
            "plan_date": "2026-06-08",
            "candidate_count": 2,
            "create_count": 2,
            "update_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "skip_count": 0,
            "failed_count": 0,
            "source_plan_path": "outputs/paper_accounts/paper_pilot_202606/daily_action_plan_20260608.json",
            "dry_run": True,
            "would_write": False,
            "candidates": [],
            "failed": [],
        }

    monkeypatch.setattr(
        export_paper_to_notion,
        "export_manual_execution_template_to_notion",
        fake_export_manual_execution_template_to_notion,
    )

    rc = export_paper_to_notion.main(
        [
            "--manual-execution-template",
            "--account-id",
            "paper_pilot_202606",
            "--date",
            "2026-06-08",
            "--dry-run",
            "--json",
        ]
    )

    assert rc == 0
    assert captured["account_id"] == "paper_pilot_202606"
    assert captured["date_str"] == "2026-06-08"
    assert captured["dry_run"] is True
    output = capsys.readouterr().out
    assert "manual_execution_template" in output
    payload = json.loads(output[output.index("{") :])
    assert payload["candidate_count"] == 2


def test_cli_manual_review_template_dry_run_routes_to_exporter(monkeypatch, capsys):
    captured: dict[str, object] = {}

    monkeypatch.setattr(export_paper_to_notion, "load_notion_settings", lambda allow_missing=True: object())
    monkeypatch.setattr(export_paper_to_notion, "load_notion_property_mapping", lambda: {"manual_reviews": {}})
    monkeypatch.setattr(export_paper_to_notion, "get_notion_token", lambda settings: "token")
    monkeypatch.setattr(export_paper_to_notion, "NotionClient", lambda token: object())

    def fake_export_manual_review_template_to_notion(**kwargs):
        captured.update(kwargs)
        return {
            "target": "manual_review_template",
            "account_id": "paper_pilot_202606",
            "review_date": "2026-06-05",
            "candidate_count": 8,
            "create_count": 8,
            "update_count": 0,
            "created_count": 0,
            "updated_count": 0,
            "skip_count": 0,
            "failed_count": 0,
            "source_template_path": "outputs/paper_accounts/paper_pilot_202606/reviews/paper_manual_review_log_template.csv",
            "dry_run": True,
            "would_write": False,
            "candidates": [],
            "failed": [],
        }

    monkeypatch.setattr(
        export_paper_to_notion,
        "export_manual_review_template_to_notion",
        fake_export_manual_review_template_to_notion,
    )

    rc = export_paper_to_notion.main(
        [
            "--manual-review-template",
            "--account-id",
            "paper_pilot_202606",
            "--date",
            "2026-06-05",
            "--dry-run",
            "--json",
        ]
    )

    assert rc == 0
    assert captured["account_id"] == "paper_pilot_202606"
    assert captured["review_date"] == "2026-06-05"
    assert captured["dry_run"] is True
    output = capsys.readouterr().out
    assert "manual_review_template" in output
    payload = json.loads(output[output.index("{") :])
    assert payload["candidate_count"] == 8
