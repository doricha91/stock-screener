from __future__ import annotations

import json
from pathlib import Path

import pytest

import core.notion_manual_execution_importer as importer
from core.notion_manual_execution_importer import (
    FAIL,
    WARNING,
    build_manual_execution_preview,
    fetch_manual_execution_pages,
    normalize_manual_execution_pages,
)
from core.notion_settings import NotionSettings
from scripts import import_notion_executions as execution_script


def _settings() -> NotionSettings:
    return NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={"manual_executions": "ds-manual"},
    )


def _mapping_root() -> dict[str, dict[str, str]]:
    return {
        "manual_executions": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "execution_date": "Execution Date",
            "plan_date": "Plan Date",
            "symbol": "Symbol",
            "side": "Side",
            "quantity": "Quantity",
            "actual_price": "Actual Price",
            "commission": "Commission",
            "currency": "Currency",
            "broker": "Broker",
            "status": "Status",
            "linked_daily_plan_key": "Linked Daily Plan Key",
            "note": "Note",
            "validation_status": "Validation Status",
            "validation_message": "Validation Message",
            "import_status": "Import Status",
            "imported_at": "Imported At",
            "synced_at": "Synced At",
        }
    }


def _page(
    *,
    page_id: str,
    execution_date: str,
    symbol: str,
    side: str,
    quantity: int,
    actual_price: float,
    status: str = "READY",
    commission: float | None = None,
    currency: str | None = None,
    broker: str | None = None,
    plan_date: str | None = "2026-05-25",
    linked_daily_plan_key: str | None = "daily_plan:2026-05-25",
    account_id: str | None = "paper_default",
) -> dict:
    properties = {
        "Name": {"type": "title", "title": [{"plain_text": f"{symbol} {side}"}]},
        "Execution Date": {"type": "date", "date": {"start": execution_date}},
        "Symbol": {"type": "rich_text", "rich_text": [{"plain_text": symbol}]},
        "Side": {"type": "select", "select": {"name": side}},
        "Quantity": {"type": "number", "number": quantity},
        "Actual Price": {"type": "number", "number": actual_price},
        "Status": {"type": "select", "select": {"name": status}},
        "Note": {"type": "rich_text", "rich_text": []},
        "Broker": {"type": "rich_text", "rich_text": ([] if not broker else [{"plain_text": broker}])},
        "Linked Daily Plan Key": {
            "type": "rich_text",
            "rich_text": ([] if not linked_daily_plan_key else [{"plain_text": linked_daily_plan_key}]),
        },
        "Plan Date": {"type": "date", "date": None if not plan_date else {"start": plan_date}},
        "External Key": {"type": "rich_text", "rich_text": []},
        "Account ID": {"type": "select", "select": None if account_id is None else {"name": account_id}},
        "Validation Status": {"type": "select", "select": None},
        "Validation Message": {"type": "rich_text", "rich_text": []},
        "Import Status": {"type": "select", "select": None},
        "Imported At": {"type": "rich_text", "rich_text": []},
        "Synced At": {"type": "rich_text", "rich_text": []},
    }
    properties["Commission"] = {"type": "number", "number": commission}
    properties["Currency"] = {"type": "select", "select": None if not currency else {"name": currency}}
    return {
        "id": page_id,
        "created_time": f"2026-05-25T0{page_id[-1]}:00:00.000Z",
        "properties": properties,
    }


class FakeClient:
    def __init__(self, pages: list[dict]):
        self.pages = pages
        self.calls: list[dict] = []

    def query_data_source(self, data_source_id: str, *, filter_payload=None, sorts=None, page_size=100):
        self.calls.append(
            {
                "data_source_id": data_source_id,
                "filter_payload": filter_payload,
                "sorts": sorts,
                "page_size": page_size,
            }
        )
        return self.pages


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _seed_ledgers(tmp_path: Path) -> None:
    _write(
        tmp_path / "paper_account_snapshot.csv",
        "snapshot_date,cash\n"
        "2026-05-20,1000.00\n",
    )
    _write(
        tmp_path / "paper_position_snapshot.csv",
        "snapshot_date,symbol,shares\n"
        "2026-05-20,GEN,5\n"
        "2026-05-20,F,10\n",
    )
    _write(
        tmp_path / "paper_execution_log.csv",
        "trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at\n",
    )


def test_normalize_manual_execution_pages_applies_defaults_and_warnings():
    pages = [
        _page(
            page_id="page-1",
            execution_date="2026-05-25",
            symbol=" gen ",
            side="buy",
            quantity=3,
            actual_price=12.5,
            commission=None,
            currency=None,
            broker=None,
            plan_date=None,
            linked_daily_plan_key=None,
        )
    ]
    candidates = normalize_manual_execution_pages(
        pages=pages,
        mapping=_mapping_root()["manual_executions"],
    )
    candidate = candidates[0]
    assert candidate.account_id == "paper_default"
    assert candidate.symbol == "GEN"
    assert candidate.side == "BUY"
    assert candidate.commission == 0.0
    assert candidate.currency == "USD"
    assert {issue.code for issue in candidate.validation_issues} >= {
        "missing_commission",
        "missing_currency",
        "missing_broker",
        "missing_plan_date",
        "missing_linked_daily_plan_key",
    }


def test_preview_generates_reports_and_filters_ready_rows(monkeypatch, tmp_path):
    _seed_ledgers(tmp_path)
    monkeypatch.setattr(importer, "paper_account_snapshot_path", lambda: tmp_path / "paper_account_snapshot.csv")
    monkeypatch.setattr(importer, "paper_position_snapshot_path", lambda: tmp_path / "paper_position_snapshot.csv")
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")

    client = FakeClient(
        [
            _page(
                page_id="page-1",
                execution_date="2026-05-25",
                symbol="GEN",
                side="SELL",
                quantity=3,
                actual_price=25.0,
                commission=1.0,
                currency="USD",
                broker="IBKR",
            ),
            _page(
                page_id="page-2",
                execution_date="2026-05-25",
                symbol="F",
                side="BUY",
                quantity=2,
                actual_price=10.0,
                commission=0.5,
                currency="USD",
                broker="IBKR",
            ),
        ]
    )

    preview = build_manual_execution_preview(
        client=client,
        settings=_settings(),
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
    )
    assert preview.account_id == "paper_default"
    assert preview.candidate_count == 2
    assert preview.fail_count == 0
    assert preview.commit_allowed == "true"
    assert preview.projected_cash_start == 1000.0
    assert preview.projected_cash_end == pytest.approx(1053.5)
    assert preview.projected_position_impact == {"F": 2, "GEN": -3}
    payload = json.loads(Path(preview.json_path).read_text(encoding="utf-8"))
    assert payload["account_id"] == "paper_default"
    assert payload["candidate_count"] == 2
    assert payload["candidates"][0]["account_id"] == "paper_default"
    assert payload["candidates"][0]["legacy_canonical_key"]
    markdown = Path(preview.markdown_path).read_text(encoding="utf-8")
    assert "Manual Execution Import Preview" in markdown
    assert "Account ID: paper_default" in markdown
    assert "GEN SELL 3" in markdown
    assert "F BUY 2" in markdown


def test_preview_marks_sell_exceeding_holdings_as_fail(monkeypatch, tmp_path):
    _seed_ledgers(tmp_path)
    monkeypatch.setattr(importer, "paper_account_snapshot_path", lambda: tmp_path / "paper_account_snapshot.csv")
    monkeypatch.setattr(importer, "paper_position_snapshot_path", lambda: tmp_path / "paper_position_snapshot.csv")
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")
    client = FakeClient(
        [
            _page(
                page_id="page-1",
                execution_date="2026-05-25",
                symbol="GEN",
                side="SELL",
                quantity=8,
                actual_price=25.0,
                commission=0.0,
                currency="USD",
                broker="IBKR",
            )
        ]
    )
    preview = build_manual_execution_preview(
        client=client,
        settings=_settings(),
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
    )
    assert preview.fail_count == 1
    assert preview.commit_allowed == "false"
    assert preview.candidates[0].validation_status == FAIL


def test_preview_marks_cash_shortfall_as_fail(monkeypatch, tmp_path):
    _seed_ledgers(tmp_path)
    monkeypatch.setattr(importer, "paper_account_snapshot_path", lambda: tmp_path / "paper_account_snapshot.csv")
    monkeypatch.setattr(importer, "paper_position_snapshot_path", lambda: tmp_path / "paper_position_snapshot.csv")
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")
    client = FakeClient(
        [
            _page(
                page_id="page-1",
                execution_date="2026-05-25",
                symbol="BRK-B",
                side="BUY",
                quantity=10,
                actual_price=500.0,
                commission=1.0,
                currency="USD",
                broker="IBKR",
            )
        ]
    )
    preview = build_manual_execution_preview(
        client=client,
        settings=_settings(),
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
    )
    assert preview.fail_count == 1
    assert preview.candidates[0].validation_status == FAIL


def test_preview_only_queries_ready_rows_for_requested_date(monkeypatch, tmp_path):
    _seed_ledgers(tmp_path)
    monkeypatch.setattr(importer, "paper_account_snapshot_path", lambda: tmp_path / "paper_account_snapshot.csv")
    monkeypatch.setattr(importer, "paper_position_snapshot_path", lambda: tmp_path / "paper_position_snapshot.csv")
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")
    client = FakeClient([])
    preview = build_manual_execution_preview(
        client=client,
        settings=_settings(),
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
    )
    assert preview.candidate_count == 0
    filters = client.calls[0]["filter_payload"]["and"]
    assert filters[0]["date"]["equals"] == "2026-05-25"
    assert filters[1]["select"]["equals"] == "READY"
    assert filters[2]["or"][0]["select"]["equals"] == "paper_default"
    assert filters[2]["or"][1]["select"]["is_empty"] is True
    assert preview.commit_allowed == "true"
    assert preview.warning_count == 0


def test_missing_optional_fields_produce_warning_commit_state(monkeypatch, tmp_path):
    _seed_ledgers(tmp_path)
    monkeypatch.setattr(importer, "paper_account_snapshot_path", lambda: tmp_path / "paper_account_snapshot.csv")
    monkeypatch.setattr(importer, "paper_position_snapshot_path", lambda: tmp_path / "paper_position_snapshot.csv")
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")
    client = FakeClient(
        [
            _page(
                page_id="page-1",
                execution_date="2026-05-25",
                symbol="F",
                side="BUY",
                quantity=1,
                actual_price=10.0,
                commission=None,
                currency=None,
                broker=None,
                plan_date=None,
                linked_daily_plan_key=None,
            )
        ]
    )
    preview = build_manual_execution_preview(
        client=client,
        settings=_settings(),
        mapping_root=_mapping_root(),
        execution_date="2026-05-25",
    )
    assert preview.commit_allowed == "true_with_warnings"
    assert preview.warning_count == 1
    assert preview.candidates[0].validation_status == WARNING


def test_non_default_preview_filters_exact_account_id():
    client = FakeClient([])
    fetch_manual_execution_pages(
        client=client,
        data_source_id="ds-manual",
        mapping=_mapping_root()["manual_executions"],
        execution_date="2026-05-25",
        account_id="paper_growth",
    )
    filters = client.calls[0]["filter_payload"]["and"]
    assert filters[2]["property"] == "Account ID"
    assert filters[2]["select"]["equals"] == "paper_growth"


def test_account_aware_canonical_key_is_generated_for_non_default():
    pages = [
        _page(
            page_id="page-1",
            execution_date="2026-05-25",
            symbol="aapl",
            side="buy",
            quantity=1,
            actual_price=100.0,
            account_id="paper_growth",
        )
    ]
    candidates = normalize_manual_execution_pages(
        pages=pages,
        mapping=_mapping_root()["manual_executions"],
        account_id="paper_growth",
    )
    importer._assign_canonical_keys(candidates, account_id="paper_growth")
    assert candidates[0].canonical_key == "manual_execution:paper_growth:2026-05-25:AAPL:BUY:01"
    assert candidates[0].legacy_canonical_key is None
    assert candidates[0].legacy_key_compatible is False


def test_invalid_account_id_fails_for_preview(monkeypatch, tmp_path):
    _seed_ledgers(tmp_path)
    monkeypatch.setattr(importer, "paper_account_snapshot_path", lambda: tmp_path / "paper_account_snapshot.csv")
    monkeypatch.setattr(importer, "paper_position_snapshot_path", lambda: tmp_path / "paper_position_snapshot.csv")
    monkeypatch.setattr(importer, "paper_reports_dir", lambda: tmp_path / "reports")
    with pytest.raises(ValueError):
        build_manual_execution_preview(
            client=FakeClient([]),
            settings=_settings(),
            mapping_root=_mapping_root(),
            execution_date="2026-05-25",
            account_id="Paper Default",
        )


def test_cli_blocks_non_default_commit(capsys):
    exit_code = execution_script.main(
        [
            "--date",
            "2026-05-25",
            "--commit",
            "--preview-json",
            "missing.json",
            "--account-id",
            "paper_growth",
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "blocked" in captured.out.lower()
