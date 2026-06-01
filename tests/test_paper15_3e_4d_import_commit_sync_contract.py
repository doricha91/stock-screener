from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

import core.notion_manual_execution_importer as execution_importer
import core.notion_manual_review_importer as review_importer
import core.paper_account_snapshot as paper_account_snapshot_module
import core.paper_current_state_storage as paper_current_state_storage_module
import core.paper_execution_log as paper_execution_log_module
import core.paper_manual_execution_commit as execution_commit_module
import core.paper_manual_review_log_append as paper_manual_review_log_append_module
import core.paper_manual_review_log_template as paper_manual_review_log_template_module
import core.paper_manual_review_log_validator as paper_manual_review_log_validator_module
import core.paper_manual_review_append_commit as review_commit_module
import core.paper_position_snapshot as paper_position_snapshot_module
from core.paper_account_paths import build_paper_account_paths
from core.notion_manual_execution_importer import build_manual_execution_preview
from core.notion_manual_execution_status_sync import (
    build_manual_execution_status_properties,
    sync_manual_execution_status,
)
from core.notion_manual_review_importer import build_manual_review_preview
from core.notion_manual_review_status_sync import (
    build_manual_review_status_properties,
    sync_manual_review_status,
)
from core.notion_settings import NotionSettings
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_manual_execution_commit import (
    ManualExecutionCommitError,
    commit_manual_execution_preview,
)
from core.paper_manual_review_append_commit import (
    ManualReviewAppendCommitError,
    commit_manual_review_preview,
)
from core.paper_market_valuation import PaperAccountValuation, PaperPositionValuation
from core.paths import OUTPUTS, PAPER_TEST_DIR


def _exec_settings() -> NotionSettings:
    return NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={"manual_executions": "ds-manual"},
    )


def _review_settings() -> NotionSettings:
    return NotionSettings(
        enabled=True,
        token_env="NOTION_TOKEN",
        data_sources={"manual_reviews": "ds-manual-reviews"},
    )


def _execution_mapping_root() -> dict[str, dict[str, str]]:
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


def _review_mapping_root() -> dict[str, dict[str, str]]:
    return {
        "manual_reviews": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "review_date": "Review Date",
            "symbol": "Symbol",
            "question_id": "Question ID",
            "question": "Question",
            "manual_answer": "Manual Answer",
            "review_status": "Review Status",
            "follow_up_needed": "Follow-up Needed",
            "review_tag": "Review Tag",
            "reviewer_note": "Reviewer Note",
            "source_template_key": "Source Template Key",
            "validation_status": "Validation Status",
            "validation_message": "Validation Message",
            "import_status": "Import Status",
            "imported_at": "Imported At",
            "synced_at": "Synced At",
        }
    }


def _execution_page(
    *,
    page_id: str = "page-1",
    execution_date: str = "2026-05-25",
    symbol: str = "AAPL",
    side: str = "BUY",
    quantity: int = 1,
    actual_price: float = 100.0,
    account_id: str | None = None,
) -> dict:
    return {
        "id": page_id,
        "created_time": "2026-05-25T09:00:00.000Z",
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": f"{symbol} {side}"}]},
            "Execution Date": {"type": "date", "date": {"start": execution_date}},
            "Symbol": {"type": "rich_text", "rich_text": [{"plain_text": symbol}]},
            "Side": {"type": "select", "select": {"name": side}},
            "Quantity": {"type": "number", "number": quantity},
            "Actual Price": {"type": "number", "number": actual_price},
            "Commission": {"type": "number", "number": 0.0},
            "Currency": {"type": "select", "select": {"name": "USD"}},
            "Broker": {"type": "rich_text", "rich_text": [{"plain_text": "IBKR"}]},
            "Status": {"type": "select", "select": {"name": "READY"}},
            "Plan Date": {"type": "date", "date": {"start": execution_date}},
            "Linked Daily Plan Key": {
                "type": "rich_text",
                "rich_text": [{"plain_text": f"daily_plan:{execution_date}"}],
            },
            "Note": {"type": "rich_text", "rich_text": []},
            "External Key": {"type": "rich_text", "rich_text": []},
            "Account ID": {"type": "select", "select": None if account_id is None else {"name": account_id}},
            "Validation Status": {"type": "select", "select": None},
            "Validation Message": {"type": "rich_text", "rich_text": []},
            "Import Status": {"type": "select", "select": None},
            "Imported At": {"type": "rich_text", "rich_text": []},
            "Synced At": {"type": "rich_text", "rich_text": []},
        },
    }


def _review_page(
    *,
    page_id: str = "page-1",
    review_date: str = "2026-05-25",
    symbol: str = "AAPL",
    question_id: str = "Q001",
    account_id: str | None = None,
) -> dict:
    return {
        "id": page_id,
        "created_time": "2026-05-25T09:00:00.000Z",
        "properties": {
            "Name": {"type": "title", "title": [{"plain_text": f"{symbol} {question_id}"}]},
            "External Key": {"type": "rich_text", "rich_text": []},
            "Account ID": {"type": "select", "select": None if account_id is None else {"name": account_id}},
            "Review Date": {"type": "date", "date": {"start": review_date}},
            "Symbol": {"type": "rich_text", "rich_text": [{"plain_text": symbol}]},
            "Question ID": {"type": "rich_text", "rich_text": [{"plain_text": question_id}]},
            "Question": {"type": "rich_text", "rich_text": [{"plain_text": "Question text"}]},
            "Manual Answer": {"type": "rich_text", "rich_text": [{"plain_text": "Reviewed"}]},
            "Review Status": {"type": "select", "select": {"name": "reviewed"}},
            "Follow-up Needed": {"type": "select", "select": {"name": "false"}},
            "Review Tag": {"type": "select", "select": {"name": "entry_rule"}},
            "Reviewer Note": {"type": "rich_text", "rich_text": [{"plain_text": "Looks good"}]},
            "Source Template Key": {"type": "rich_text", "rich_text": [{"plain_text": "template-key"}]},
            "Validation Status": {"type": "select", "select": None},
            "Validation Message": {"type": "rich_text", "rich_text": []},
            "Import Status": {"type": "select", "select": {"name": "READY"}},
            "Imported At": {"type": "rich_text", "rich_text": []},
            "Synced At": {"type": "rich_text", "rich_text": []},
        },
    }


class _FakeQueryClient:
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


class _FakeStatusClient:
    def __init__(self):
        self.calls: list[dict] = []

    def update_page(self, page_id: str, properties: dict) -> dict:
        self.calls.append({"page_id": page_id, "properties": properties})
        return {"id": page_id}


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _seed_execution_ledgers(root: Path) -> None:
    account_path = root / "paper_account_snapshot.csv"
    position_path = root / "paper_position_snapshot.csv"
    execution_path = root / "paper_execution_log.csv"
    _write_csv(
        account_path,
        ["snapshot_date", "currency", "initial_cash", "cash"],
        [{"snapshot_date": "2026-05-24", "currency": "USD", "initial_cash": "1000.00", "cash": "1000.00"}],
    )
    _write_csv(
        position_path,
        ["snapshot_date", "symbol", "shares"],
        [],
    )
    _write_csv(execution_path, PAPER_EXECUTION_LOG_COLUMNS, [])


def _seed_review_files(root: Path) -> None:
    _write_csv(
        root / "paper_manual_review_log.csv",
        [
            "review_date",
            "symbol",
            "review_bucket",
            "review_priority",
            "sample_size_flag",
            "symbol_status",
            "question_id",
            "question_text",
            "question_category",
            "is_actionable",
            "manual_answer",
            "review_status",
            "follow_up_needed",
            "review_tag",
            "reviewer_note",
            "source_worksheet_path",
            "created_at",
        ],
        [],
    )
    _write_csv(
        root / "paper_manual_review_log_template.csv",
        [
            "review_date",
            "symbol",
            "review_bucket",
            "review_priority",
            "sample_size_flag",
            "symbol_status",
            "question_id",
            "question_text",
            "question_category",
            "is_actionable",
            "manual_answer",
            "review_status",
            "follow_up_needed",
            "review_tag",
            "reviewer_note",
            "source_worksheet_path",
            "created_at",
        ],
        [
            {
                "review_date": "2026-05-25",
                "symbol": "AAPL",
                "review_bucket": "review_loss",
                "review_priority": "high",
                "sample_size_flag": "low_sample",
                "symbol_status": "realized_only",
                "question_id": "Q001",
                "question_text": "Question text",
                "question_category": "review_loss",
                "is_actionable": "false",
                "manual_answer": "",
                "review_status": "pending",
                "follow_up_needed": "false",
                "review_tag": "",
                "reviewer_note": "",
                "source_worksheet_path": "worksheet.csv",
                "created_at": "2026-05-25T09:00:00",
            }
        ],
    )


def _fake_valuation(state, snapshot_date: str, db_path: Path) -> PaperAccountValuation:
    positions = []
    valuation_price_dates: dict[str, str] = {}
    staleness: dict[str, int] = {}
    positions_cost_value = 0.0
    positions_market_value = 0.0
    for symbol, position in sorted(state.positions.items()):
        close_price = position.avg_price
        cost_value = position.shares * position.avg_price
        market_value = position.shares * close_price
        positions_cost_value += cost_value
        positions_market_value += market_value
        positions.append(
            PaperPositionValuation(
                symbol=symbol,
                shares=position.shares,
                avg_price=position.avg_price,
                close_price=close_price,
                market_value=market_value,
                cost_value=cost_value,
                unrealized_pnl=0.0,
                unrealized_pnl_pct=0.0 if cost_value else None,
                valuation_price_date=snapshot_date,
                price_staleness_days=0,
            )
        )
        valuation_price_dates[symbol] = snapshot_date
        staleness[symbol] = 0
    total_equity_cost_basis = float(state.cash) + positions_cost_value
    total_equity_market_value = float(state.cash) + positions_market_value
    return PaperAccountValuation(
        snapshot_date=snapshot_date,
        cash=float(state.cash),
        positions_cost_value=positions_cost_value,
        positions_market_value=positions_market_value,
        total_equity_cost_basis=total_equity_cost_basis,
        total_equity_market_value=total_equity_market_value,
        cash_ratio_market_value=1.0 if total_equity_market_value == 0 else float(state.cash) / total_equity_market_value,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=0.0 if positions_cost_value else None,
        valuation_method="db_daily_price_close",
        valuation_price_date=snapshot_date,
        valuation_price_dates=valuation_price_dates,
        price_staleness_days=staleness,
        positions=positions,
    )


@pytest.fixture
def execution_contract_env(monkeypatch, tmp_path: Path):
    root = tmp_path / "execution_contract"
    root.mkdir(parents=True, exist_ok=True)
    reports_dir = root / "reports"
    backups_dir = root / "dev_backups"
    current_state_path = root / "paper_current_state_20260525.json"
    reports_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    _seed_execution_ledgers(root)

    monkeypatch.setattr(execution_importer, "paper_account_snapshot_path", lambda: root / "paper_account_snapshot.csv")
    monkeypatch.setattr(execution_importer, "paper_position_snapshot_path", lambda: root / "paper_position_snapshot.csv")
    monkeypatch.setattr(execution_importer, "paper_reports_dir", lambda: reports_dir)

    monkeypatch.setattr(execution_commit_module, "paper_execution_log_path", lambda: root / "paper_execution_log.csv")
    monkeypatch.setattr(execution_commit_module, "paper_account_snapshot_path", lambda: root / "paper_account_snapshot.csv")
    monkeypatch.setattr(execution_commit_module, "paper_position_snapshot_path", lambda: root / "paper_position_snapshot.csv")
    monkeypatch.setattr(execution_commit_module, "paper_current_state_snapshot_path", lambda date: current_state_path)
    monkeypatch.setattr(execution_commit_module, "paper_reports_dir", lambda: reports_dir)
    monkeypatch.setattr(execution_commit_module, "dev_backups_dir", lambda: backups_dir)
    monkeypatch.setattr(execution_commit_module, "market_db_path", lambda: str(root / "unused_market.db"))
    monkeypatch.setattr(execution_commit_module, "value_paper_account_state", _fake_valuation)
    monkeypatch.setattr(paper_execution_log_module, "assert_paper_path", lambda path, paper_root: None)
    monkeypatch.setattr(paper_current_state_storage_module, "assert_paper_path", lambda path, paper_root: None)
    monkeypatch.setattr(paper_account_snapshot_module, "assert_paper_path", lambda path, paper_root: None)
    monkeypatch.setattr(paper_position_snapshot_module, "assert_paper_path", lambda path, paper_root: None)
    yield root
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def review_contract_env(monkeypatch, tmp_path: Path):
    root = tmp_path / "review_contract"
    root.mkdir(parents=True, exist_ok=True)
    reports_dir = root / "reports"
    backups_dir = root / "dev_backups"
    reports_dir.mkdir(parents=True, exist_ok=True)
    backups_dir.mkdir(parents=True, exist_ok=True)
    _seed_review_files(root)

    monkeypatch.setattr(review_importer, "paper_reviews_dir", lambda: root)
    monkeypatch.setattr(review_importer, "paper_reports_dir", lambda: reports_dir)
    monkeypatch.setattr(review_commit_module, "paper_reviews_dir", lambda: root)
    monkeypatch.setattr(review_commit_module, "paper_reports_dir", lambda: reports_dir)
    monkeypatch.setattr(review_commit_module, "dev_backups_dir", lambda: backups_dir)
    monkeypatch.setattr(paper_manual_review_log_append_module, "assert_paper_path", lambda path, paper_root: None)
    monkeypatch.setattr(paper_manual_review_log_template_module, "assert_paper_path", lambda path, paper_root: None)
    monkeypatch.setattr(paper_manual_review_log_validator_module, "assert_paper_path", lambda path, paper_root: None)
    yield root
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)


def test_execution_preview_commit_sync_contract_for_paper_default_legacy_row(execution_contract_env: Path):
    client = _FakeQueryClient([_execution_page(account_id=None)])
    preview = build_manual_execution_preview(
        client=client,
        settings=_exec_settings(),
        mapping_root=_execution_mapping_root(),
        execution_date="2026-05-25",
    )

    candidate = preview.candidates[0]
    assert candidate.account_id == "paper_default"
    assert candidate.canonical_key == "manual_execution:paper_default:2026-05-25:AAPL:BUY:01"
    assert candidate.legacy_canonical_key == "manual_execution:2026-05-25:AAPL:BUY:01"
    assert candidate.legacy_key_compatible is True

    commit_result = commit_manual_execution_preview(
        execution_date="2026-05-25",
        preview_json_path=Path(preview.json_path),
    )
    sidecar = json.loads(Path(commit_result.commit_json_path).read_text(encoding="utf-8"))
    row = sidecar["committed_rows"][0]
    assert sidecar["account_id"] == "paper_default"
    assert row["account_id"] == "paper_default"
    assert row["canonical_key"] == candidate.canonical_key
    assert row["legacy_canonical_key"] == candidate.legacy_canonical_key
    assert row["legacy_key_compatible"] is True

    props = build_manual_execution_status_properties(
        mapping=_execution_mapping_root()["manual_executions"],
        account_id=row["account_id"],
        canonical_key=row["canonical_key"],
        validation_status=row["validation_status"],
        validation_issues=row["validation_issues"],
        sync_timestamp="2026-05-25T22:00:00",
    )
    assert props["Account ID"]["select"]["name"] == "paper_default"
    assert props["External Key"]["rich_text"][0]["text"]["content"] == row["canonical_key"]

    sync_result = sync_manual_execution_status(
        client=_FakeStatusClient(),
        mapping_root=_execution_mapping_root(),
        execution_date="2026-05-25",
        commit_report_path=Path(commit_result.commit_json_path),
        dry_run=True,
    )
    assert sync_result.account_id == "paper_default"
    assert sync_result.rows[0].canonical_key == row["canonical_key"]
    assert sync_result.rows[0].legacy_canonical_key is None
    assert sync_result.rows[0].legacy_key_compatible is False


def test_review_preview_append_sync_contract_for_paper_default_legacy_row(review_contract_env: Path):
    client = _FakeQueryClient([_review_page(account_id=None)])
    preview = build_manual_review_preview(
        client=client,
        settings=_review_settings(),
        mapping_root=_review_mapping_root(),
        review_date="2026-05-25",
    )

    candidate = preview.candidates[0]
    assert candidate.account_id == "paper_default"
    assert candidate.canonical_key == "manual_review:paper_default:2026-05-25:AAPL:Q001"
    assert candidate.legacy_canonical_key == "manual_review:2026-05-25:AAPL:Q001"
    assert candidate.legacy_key_compatible is True

    append_result = commit_manual_review_preview(
        review_date="2026-05-25",
        preview_json_path=Path(preview.json_path),
    )
    sidecar = json.loads(Path(append_result.commit_json_path).read_text(encoding="utf-8"))
    row = sidecar["rows"][0]
    assert sidecar["account_id"] == "paper_default"
    assert row["account_id"] == "paper_default"
    assert row["canonical_key"] == candidate.canonical_key
    assert row["legacy_canonical_key"] == candidate.legacy_canonical_key
    assert row["legacy_key_compatible"] is True

    props = build_manual_review_status_properties(
        mapping=_review_mapping_root()["manual_reviews"],
        account_id=row["account_id"],
        canonical_key=row["canonical_key"],
        validation_status=row["validation_status"],
        validation_warnings=row["validation_warnings"],
        sync_timestamp="2026-05-26T21:00:00",
    )
    assert props["Account ID"]["select"]["name"] == "paper_default"
    assert props["External Key"]["rich_text"][0]["text"]["content"] == row["canonical_key"]

    sync_result = sync_manual_review_status(
        client=_FakeStatusClient(),
        mapping_root=_review_mapping_root(),
        review_date="2026-05-25",
        commit_report_path=Path(append_result.commit_json_path),
        dry_run=True,
    )
    assert sync_result.account_id == "paper_default"
    assert sync_result.rows[0].canonical_key == row["canonical_key"]
    assert sync_result.rows[0].legacy_canonical_key is None
    assert sync_result.rows[0].legacy_key_compatible is False


def test_non_default_execution_contract_keeps_account_namespace_and_syncs_from_account_root(execution_contract_env: Path):
    client = _FakeQueryClient([_execution_page(account_id="paper_growth")])
    preview = build_manual_execution_preview(
        client=client,
        settings=_exec_settings(),
        mapping_root=_execution_mapping_root(),
        execution_date="2026-05-25",
        account_id="paper_growth",
    )
    filters = client.calls[0]["filter_payload"]["and"]
    assert filters[2]["select"]["equals"] == "paper_growth"
    candidate = preview.candidates[0]
    assert candidate.account_id == "paper_growth"
    assert candidate.canonical_key == "manual_execution:paper_growth:2026-05-25:AAPL:BUY:01"
    assert candidate.legacy_canonical_key is None

    account_paths = build_paper_account_paths(
        "paper_growth",
        account_root=execution_contract_env,
        allow_legacy_default=False,
        create=True,
    )
    commit_result = commit_manual_execution_preview(
        execution_date="2026-05-25",
        preview_json_path=Path(preview.json_path),
        account_paths=account_paths,
    )
    sidecar = json.loads(Path(commit_result.commit_json_path).read_text(encoding="utf-8"))
    row = sidecar["committed_rows"][0]
    assert row["account_id"] == "paper_growth"
    assert row["canonical_key"] == candidate.canonical_key
    assert row["legacy_canonical_key"] is None
    assert row["legacy_key_compatible"] is False

    sync_result = sync_manual_execution_status(
        client=_FakeStatusClient(),
        mapping_root=_execution_mapping_root(),
        execution_date="2026-05-25",
        commit_report_path=Path(commit_result.commit_json_path),
        dry_run=True,
        account_id="paper_growth",
    )
    assert sync_result.overall_status == "SUCCESS"
    assert sync_result.rows[0].canonical_key == candidate.canonical_key

    legacy_report = execution_contract_env / "reports" / "legacy_only_execution_commit.json"
    legacy_report.write_text(
        json.dumps(
            {
                "execution_date": "2026-05-25",
                "account_id": "paper_growth",
                "committed_rows": [
                    {
                        "account_id": "paper_growth",
                        "canonical_key": "manual_execution:2026-05-25:AAPL:BUY:01",
                        "page_id": "page-1",
                        "symbol": "AAPL",
                        "side": "BUY",
                        "committed_trade_id": "trade-1",
                        "validation_status": "PASS",
                        "validation_issues": [],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    sync_result = sync_manual_execution_status(
        client=_FakeStatusClient(),
        mapping_root=_execution_mapping_root(),
        execution_date="2026-05-25",
        commit_report_path=legacy_report,
        dry_run=True,
        account_id="paper_growth",
    )
    assert sync_result.overall_status == "FAILED"
    assert "Legacy canonical_key" in sync_result.rows[0].message


def test_non_default_review_contract_keeps_account_namespace_and_syncs_from_account_root(review_contract_env: Path):
    client = _FakeQueryClient([_review_page(account_id="paper_growth")])
    preview = build_manual_review_preview(
        client=client,
        settings=_review_settings(),
        mapping_root=_review_mapping_root(),
        review_date="2026-05-25",
        account_id="paper_growth",
    )
    filters = client.calls[0]["filter_payload"]["and"]
    assert filters[2]["select"]["equals"] == "paper_growth"
    candidate = preview.candidates[0]
    assert candidate.account_id == "paper_growth"
    assert candidate.canonical_key == "manual_review:paper_growth:2026-05-25:AAPL:Q001"
    assert candidate.legacy_canonical_key is None

    account_paths = build_paper_account_paths(
        "paper_growth",
        account_root=review_contract_env,
        allow_legacy_default=False,
        create=True,
    )
    append_result = commit_manual_review_preview(
        review_date="2026-05-25",
        preview_json_path=Path(preview.json_path),
        account_paths=account_paths,
    )
    sidecar = json.loads(Path(append_result.commit_json_path).read_text(encoding="utf-8"))
    row = sidecar["rows"][0]
    assert row["account_id"] == "paper_growth"
    assert row["canonical_key"] == candidate.canonical_key
    assert row["legacy_canonical_key"] is None
    assert row["legacy_key_compatible"] is False

    sync_result = sync_manual_review_status(
        client=_FakeStatusClient(),
        mapping_root=_review_mapping_root(),
        review_date="2026-05-25",
        commit_report_path=Path(append_result.commit_json_path),
        dry_run=True,
        account_id="paper_growth",
    )
    assert sync_result.overall_status == "SUCCESS"
    assert sync_result.rows[0].canonical_key == candidate.canonical_key

    legacy_report = review_contract_env / "reports" / "legacy_only_review_commit.json"
    legacy_report.write_text(
        json.dumps(
            {
                "review_date": "2026-05-25",
                "account_id": "paper_growth",
                "rows": [
                    {
                        "account_id": "paper_growth",
                        "canonical_key": "manual_review:2026-05-25:AAPL:Q001",
                        "page_id": "page-1",
                        "review_date": "2026-05-25",
                        "symbol": "AAPL",
                        "question_id": "Q001",
                        "validation_status": "PASS",
                        "validation_warnings": [],
                        "append_status": "APPENDED",
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    sync_result = sync_manual_review_status(
        client=_FakeStatusClient(),
        mapping_root=_review_mapping_root(),
        review_date="2026-05-25",
        commit_report_path=legacy_report,
        dry_run=True,
        account_id="paper_growth",
    )
    assert sync_result.overall_status == "FAILED"
    assert "Legacy canonical_key" in sync_result.rows[0].message
