from __future__ import annotations

import json

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
