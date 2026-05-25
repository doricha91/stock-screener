from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

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
        canonical_key="manual_execution:2026-05-25:AAPL:BUY:01",
        validation_status="WARNING",
        validation_issues=[
            {"code": "missing_commission", "message": "Commission is blank; normalized to 0."},
            {"code": "missing_currency", "message": "Currency is blank; normalized to USD."},
        ],
        sync_timestamp="2026-05-25T22:00:00",
    )
    assert set(props.keys()) == {
        "External Key",
        "Validation Status",
        "Validation Message",
        "Import Status",
        "Imported At",
        "Synced At",
        "Status",
    }
    assert props["External Key"]["rich_text"][0]["text"]["content"] == "manual_execution:2026-05-25:AAPL:BUY:01"
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
