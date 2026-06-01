from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts import sync_notion_review_status as review_sync_script
from core.notion_client import NotionAPIError
from core.notion_manual_review_status_sync import (
    ManualReviewStatusSyncError,
    build_manual_review_status_properties,
    summarize_validation_warnings,
    sync_manual_review_status,
)


def _mapping_root() -> dict[str, dict[str, str]]:
    return {
        "manual_reviews": {
            "external_key": "External Key",
            "account_id": "Account ID",
            "validation_status": "Validation Status",
            "validation_message": "Validation Message",
            "import_status": "Import Status",
            "imported_at": "Imported At",
            "synced_at": "Synced At",
        }
    }


def _commit_report_row(
    *,
    page_id: str | None = "page-1",
    canonical_key: str | None = "manual_review:2026-05-25:AAPL:Q001",
    append_status: str = "APPENDED",
    account_id: str | None = None,
    validation_status: str = "WARNING",
    validation_warnings: list[dict] | None = None,
) -> dict:
    return {
        "canonical_key": canonical_key,
        "page_id": page_id,
        "review_date": "2026-05-25",
        "symbol": "AAPL",
        "question_id": "Q001",
        "validation_status": validation_status,
        "validation_warnings": validation_warnings
        or [
            {
                "severity": "WARNING",
                "code": "missing_source_template_key",
                "message": "Source Template Key is blank.",
            }
        ],
        "append_status": append_status,
        **({"account_id": account_id} if account_id is not None else {}),
    }


def _write_report(path: Path, rows: list[dict], *, review_date: str = "2026-05-25") -> None:
    path.write_text(
        json.dumps(
            {
                "review_date": review_date,
                "preview_json_path": "preview.json",
                "rows": rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


class FakeClient:
    def __init__(self, failure_page_ids: set[str] | None = None):
        self.failure_page_ids = failure_page_ids or set()
        self.calls: list[dict] = []

    def update_page(self, page_id: str, properties: dict) -> dict:
        self.calls.append({"page_id": page_id, "properties": properties})
        if page_id in self.failure_page_ids:
            raise NotionAPIError("boom_update")
        return {"id": page_id}


def test_summarize_validation_warnings_returns_ok_when_empty():
    assert summarize_validation_warnings([]) == "OK"


def test_build_manual_review_status_properties_matches_contract():
    props = build_manual_review_status_properties(
        mapping=_mapping_root()["manual_reviews"],
        account_id="paper_default",
        canonical_key="manual_review:paper_default:2026-05-25:AAPL:Q001",
        validation_status="WARNING",
        validation_warnings=[
            {"code": "missing_source_template_key", "message": "Source Template Key is blank."},
            {"code": "missing_review_tag", "message": "Review Tag is blank."},
        ],
        sync_timestamp="2026-05-26T21:00:00",
    )
    assert set(props.keys()) == {
        "External Key",
        "Account ID",
        "Validation Status",
        "Validation Message",
        "Import Status",
        "Imported At",
        "Synced At",
    }
    assert props["External Key"]["rich_text"][0]["text"]["content"] == "manual_review:paper_default:2026-05-25:AAPL:Q001"
    assert props["Account ID"]["select"]["name"] == "paper_default"
    assert props["Validation Status"]["select"]["name"] == "WARNING"
    assert props["Import Status"]["select"]["name"] == "COMMITTED"
    assert "missing_source_template_key" in props["Validation Message"]["rich_text"][0]["text"]["content"]


def test_dry_run_does_not_call_notion_update(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(report_path, [_commit_report_row()])
    client = FakeClient()
    result = sync_manual_review_status(
        client=client,
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=True,
        data_source_check="configured",
        now=datetime(2026, 5, 26, 21, 0, 0),
    )
    assert result.overall_status == "SUCCESS"
    assert result.account_id == "paper_default"
    assert result.updated_count == 1
    assert client.calls == []
    assert result.rows[0].status == "DRY_RUN"


def test_non_dry_run_updates_only_status_fields(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(report_path, [_commit_report_row()])
    client = FakeClient()
    result = sync_manual_review_status(
        client=client,
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=False,
        data_source_check="configured",
        now=datetime(2026, 5, 26, 21, 0, 0),
    )
    assert result.overall_status == "SUCCESS"
    assert len(client.calls) == 1
    props = client.calls[0]["properties"]
    assert set(props.keys()) == {
        "External Key",
        "Account ID",
        "Validation Status",
        "Validation Message",
        "Import Status",
        "Imported At",
        "Synced At",
    }
    assert "Review Status" not in props
    assert "Manual Answer" not in props
    assert "Review Tag" not in props


def test_missing_page_id_is_skipped_with_partial_success(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(report_path, [_commit_report_row(page_id=None)])
    client = FakeClient()
    result = sync_manual_review_status(
        client=client,
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=False,
        data_source_check="configured",
    )
    assert result.overall_status == "PARTIAL_SUCCESS"
    assert result.skipped_count == 1
    assert client.calls == []


def test_non_appended_row_is_skipped(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(report_path, [_commit_report_row(append_status="SKIPPED")])
    result = sync_manual_review_status(
        client=FakeClient(),
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=True,
        data_source_check="configured",
    )
    assert result.overall_status == "PARTIAL_SUCCESS"
    assert result.skipped_count == 1
    assert result.rows[0].status == "SKIPPED"


def test_partial_failure_is_reported_without_stopping_other_rows(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(
        report_path,
        [
            _commit_report_row(page_id="page-ok", canonical_key="manual_review:2026-05-25:AAPL:Q001"),
            _commit_report_row(page_id="page-fail", canonical_key="manual_review:2026-05-25:GEN:Q002"),
        ],
    )
    client = FakeClient(failure_page_ids={"page-fail"})
    result = sync_manual_review_status(
        client=client,
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=False,
        data_source_check="configured",
    )
    assert result.overall_status == "PARTIAL_SUCCESS"
    assert result.updated_count == 1
    assert result.failed_count == 1
    assert len(client.calls) == 2


def test_commit_report_date_mismatch_fails(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(report_path, [_commit_report_row()], review_date="2026-05-24")
    with pytest.raises(ManualReviewStatusSyncError, match="date mismatch"):
        sync_manual_review_status(
            client=FakeClient(),
            mapping_root=_mapping_root(),
            review_date="2026-05-25",
            commit_report_path=report_path,
            dry_run=True,
        )


def test_paper_default_legacy_review_commit_report_is_upgraded_to_account_aware_key(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(report_path, [_commit_report_row(canonical_key="manual_review:2026-05-25:AAPL:Q001")])
    result = sync_manual_review_status(
        client=FakeClient(),
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=True,
    )
    row = result.rows[0]
    assert row.account_id == "paper_default"
    assert row.canonical_key == "manual_review:paper_default:2026-05-25:AAPL:Q001"
    assert row.legacy_canonical_key == "manual_review:2026-05-25:AAPL:Q001"
    assert row.legacy_key_compatible is True


def test_non_default_legacy_only_review_key_fails(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(
        report_path,
        [_commit_report_row(canonical_key="manual_review:2026-05-25:AAPL:Q001", account_id="paper_growth")],
    )
    result = sync_manual_review_status(
        client=FakeClient(),
        mapping_root=_mapping_root(),
        review_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=True,
        account_id="paper_growth",
    )
    assert result.overall_status == "FAILED"
    assert result.rows[0].status == "FAILED"
    assert "Legacy canonical_key" in result.rows[0].message


def test_cli_account_id_mismatch_fails(monkeypatch, tmp_path, capsys):
    report_path = tmp_path / "commit.json"
    _write_report(report_path, [_commit_report_row(account_id="paper_growth")])
    monkeypatch.setattr(review_sync_script, "load_notion_property_mapping", lambda: _mapping_root())
    monkeypatch.setattr(review_sync_script, "load_notion_settings", lambda allow_missing=True: object())
    monkeypatch.setattr(review_sync_script, "get_notion_data_source_id", lambda *args, **kwargs: "ds-manual-reviews")
    exit_code = review_sync_script.main(
        [
            "--date",
            "2026-05-25",
            "--commit-report",
            str(report_path),
            "--account-id",
            "paper_default",
            "--dry-run",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "does not match commit report account_id" in captured.out
