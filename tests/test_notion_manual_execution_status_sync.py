from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from scripts import sync_notion_execution_status as execution_sync_script
from core.notion_client import NotionAPIError
from core.notion_manual_execution_status_sync import (
    ManualExecutionStatusSyncError,
    build_manual_execution_status_properties,
    summarize_validation_issues,
    sync_manual_execution_status,
)


def _mapping_root() -> dict[str, dict[str, str]]:
    return {
        "manual_executions": {
            "external_key": "External Key",
            "account_id": "Account ID",
            "validation_status": "Validation Status",
            "validation_message": "Validation Message",
            "import_status": "Import Status",
            "imported_at": "Imported At",
            "synced_at": "Synced At",
            "status": "Status",
        }
    }


def _commit_report_row(
    *,
    page_id: str | None = "page-1",
    canonical_key: str | None = "manual_execution:2026-05-25:AAPL:BUY:01",
    committed_trade_id: str | None = "trade-1",
    account_id: str | None = None,
    validation_status: str = "WARNING",
    validation_issues: list[dict] | None = None,
) -> dict:
    return {
        "canonical_key": canonical_key,
        "page_id": page_id,
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": 1,
        "actual_price": 100.0,
        "commission": 0.0,
        "currency": "USD",
        "broker": None,
        "validation_status": validation_status,
        "validation_issues": validation_issues
        or [
            {
                "severity": "WARNING",
                "code": "missing_commission",
                "message": "Commission is blank; normalized to 0.",
            }
        ],
        "committed_trade_id": committed_trade_id,
        **({"account_id": account_id} if account_id is not None else {}),
    }


def _write_report(path: Path, rows: list[dict], *, execution_date: str = "2026-05-25") -> None:
    path.write_text(
        json.dumps(
            {
                "execution_date": execution_date,
                "preview_json_path": "preview.json",
                "committed_rows": rows,
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


def test_summarize_validation_issues_returns_ok_when_empty():
    assert summarize_validation_issues([]) == "OK"


def test_build_manual_execution_status_properties_matches_contract():
    props = build_manual_execution_status_properties(
        mapping=_mapping_root()["manual_executions"],
        account_id="paper_default",
        canonical_key="manual_execution:paper_default:2026-05-25:AAPL:BUY:01",
        validation_status="WARNING",
        validation_issues=[
            {"code": "missing_commission", "message": "Commission is blank; normalized to 0."},
            {"code": "missing_currency", "message": "Currency is blank; normalized to USD."},
        ],
        sync_timestamp="2026-05-25T22:00:00",
    )
    assert set(props.keys()) == {
        "External Key",
        "Account ID",
        "Validation Status",
        "Validation Message",
        "Import Status",
        "Imported At",
        "Synced At",
        "Status",
    }
    assert props["External Key"]["rich_text"][0]["text"]["content"] == "manual_execution:paper_default:2026-05-25:AAPL:BUY:01"
    assert props["Account ID"]["select"]["name"] == "paper_default"
    assert props["Validation Status"]["select"]["name"] == "WARNING"
    assert props["Import Status"]["select"]["name"] == "COMMITTED"
    assert props["Status"]["select"]["name"] == "IMPORTED"
    assert "missing_commission" in props["Validation Message"]["rich_text"][0]["text"]["content"]


def test_dry_run_does_not_call_notion_update(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(report_path, [_commit_report_row()])
    client = FakeClient()
    result = sync_manual_execution_status(
        client=client,
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=True,
        data_source_check="configured",
        now=datetime(2026, 5, 25, 22, 0, 0),
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
    result = sync_manual_execution_status(
        client=client,
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=False,
        data_source_check="configured",
        now=datetime(2026, 5, 25, 22, 0, 0),
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
        "Status",
    }
    assert "Execution Date" not in props
    assert "Symbol" not in props
    assert "Quantity" not in props


def test_missing_page_id_is_skipped_with_partial_success(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(report_path, [_commit_report_row(page_id=None)])
    client = FakeClient()
    result = sync_manual_execution_status(
        client=client,
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=False,
        data_source_check="configured",
    )
    assert result.overall_status == "PARTIAL_SUCCESS"
    assert result.skipped_count == 1
    assert client.calls == []


def test_partial_failure_is_reported_without_stopping_other_rows(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(
        report_path,
        [
            _commit_report_row(page_id="page-ok", committed_trade_id="trade-ok", canonical_key="manual_execution:2026-05-25:AAPL:BUY:01"),
            _commit_report_row(page_id="page-fail", committed_trade_id="trade-fail", canonical_key="manual_execution:2026-05-25:GEN:SELL:01"),
        ],
    )
    client = FakeClient(failure_page_ids={"page-fail"})
    result = sync_manual_execution_status(
        client=client,
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
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
    _write_report(report_path, [_commit_report_row()], execution_date="2026-05-24")
    with pytest.raises(ManualExecutionStatusSyncError, match="date mismatch"):
        sync_manual_execution_status(
            client=FakeClient(),
            mapping_root=_mapping_root(),
            execution_date="2026-05-25",
            commit_report_path=report_path,
            dry_run=True,
        )


def test_paper_default_legacy_commit_report_is_upgraded_to_account_aware_key(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(report_path, [_commit_report_row(canonical_key="manual_execution:2026-05-25:AAPL:BUY:01")])
    result = sync_manual_execution_status(
        client=FakeClient(),
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
        commit_report_path=report_path,
        dry_run=True,
    )
    row = result.rows[0]
    assert row.account_id == "paper_default"
    assert row.canonical_key == "manual_execution:paper_default:2026-05-25:AAPL:BUY:01"
    assert row.legacy_canonical_key == "manual_execution:2026-05-25:AAPL:BUY:01"
    assert row.legacy_key_compatible is True


def test_non_default_legacy_only_canonical_key_fails(tmp_path):
    report_path = tmp_path / "commit.json"
    _write_report(
        report_path,
        [_commit_report_row(canonical_key="manual_execution:2026-05-25:AAPL:BUY:01", account_id="paper_growth")],
    )
    result = sync_manual_execution_status(
        client=FakeClient(),
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
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
    monkeypatch.setattr(execution_sync_script, "load_notion_property_mapping", lambda: _mapping_root())
    monkeypatch.setattr(execution_sync_script, "load_notion_settings", lambda allow_missing=True: object())
    monkeypatch.setattr(execution_sync_script, "get_notion_data_source_id", lambda *args, **kwargs: "ds-manual")
    exit_code = execution_sync_script.main(
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


def test_status_sync_report_writer_creates_json_and_markdown(monkeypatch, tmp_path):
    class FakeAccountPaths:
        reports_dir = tmp_path / "reports"

    monkeypatch.setattr(execution_sync_script, "build_paper_account_paths", lambda account_id, create=True: FakeAccountPaths())
    payload = {
        "account_id": "paper_growth",
        "execution_date": "2026-05-25",
        "overall_status": "SUCCESS",
        "candidate_count": 1,
        "updated_count": 1,
        "skipped_count": 0,
        "failed_count": 0,
        "dry_run": False,
        "commit_report_path": "commit.json",
        "rows": [{"canonical_key": "manual_execution:paper_growth:2026-05-25:AAPL:BUY:01", "status": "UPDATED", "committed_trade_id": "trade-1"}],
    }

    json_path, markdown_path = execution_sync_script.write_status_sync_report(
        payload,
        "paper_growth",
        "2026-05-25",
    )

    assert json_path.exists()
    assert markdown_path.exists()
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["sync_json_path"] == str(json_path)
    assert loaded["sync_markdown_path"] == str(markdown_path)
    assert "overall_status: SUCCESS" in markdown_path.read_text(encoding="utf-8")
