from __future__ import annotations

import json
from pathlib import Path

from core.notion_account_keys import build_daily_plan_external_key
from scripts import runbook_execution_reconciliation_preview as preview_script
from core.execution_reconciliation import build_manual_execution_key


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-06-30"
TRADE_DATE = "2026-07-01"


def _write_daily_plan(path: Path) -> None:
    payload = {
        "schema_version": "paper_daily_plan.v1",
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "items": [
            {"symbol": "CCI", "action": "SELL", "quantity": 84, "price": 100.0},
            {"symbol": "TDY", "action": "BUY", "quantity": 9, "price": 200.0},
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_manual_executions(path: Path) -> None:
    rows = [
        _row("CCI", "SELL", 1, 84, 100.0),
        _row("TDY", "BUY", 1, 9, 200.0),
    ]
    path.write_text(json.dumps(rows), encoding="utf-8")


def _row(symbol: str, side: str, sequence: int, quantity: int, actual_price: float) -> dict[str, object]:
    return {
        "page_id": f"page-{symbol}",
        "external_key": build_manual_execution_key(ACCOUNT_ID, TRADE_DATE, symbol, side, sequence),
        "account_id": ACCOUNT_ID,
        "execution_date": TRADE_DATE,
        "linked_daily_plan_key": build_daily_plan_external_key(ACCOUNT_ID, TRADE_DATE),
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "actual_price": actual_price,
        "status": "READY",
        "import_status": "NOT_IMPORTED",
    }


def test_preview_writes_json_md_and_latest_artifacts(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "account"
    daily_plan_path = tmp_path / "daily_action_plan_20260701.json"
    executions_path = tmp_path / "manual_executions.json"
    _write_daily_plan(daily_plan_path)
    _write_manual_executions(executions_path)

    result = preview_script.run_execution_reconciliation_preview(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        daily_plan_path=daily_plan_path,
        manual_executions_path=executions_path,
        account_root=account_root,
    )

    assert result["runner_result"] == "PASS"
    assert result["planned_count"] == 2
    assert result["actual_count"] == 2
    assert Path(result["preview_json"]).exists()
    assert Path(result["preview_md"]).exists()
    assert Path(result["latest_preview_json"]).exists()
    assert Path(result["latest_preview_md"]).exists()
    assert Path(result["account_preview_json"]).exists()
    assert Path(result["account_preview_md"]).exists()
    assert result["runbook_day_id"] in result["preview_json"]

    payload = json.loads(Path(result["latest_preview_json"]).read_text(encoding="utf-8"))
    assert payload["schema_version"] == "execution_reconciliation_preview.v1"
    assert payload["matched_count"] == 2
    assert "Execution Reconciliation Preview" in Path(result["latest_preview_md"]).read_text(encoding="utf-8")


def test_preview_paths_are_separated_by_runbook_day_id(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    paths_a = preview_script.get_workspace_preview_paths(
        workspace,
        "paper_A_2026-06-30_2026-07-01",
        timestamp="20260701_010101000000",
    )
    paths_b = preview_script.get_workspace_preview_paths(
        workspace,
        "paper_B_2026-06-30_2026-07-01",
        timestamp="20260701_010101000000",
    )

    assert paths_a["json"].parent != paths_b["json"].parent
    assert "reconciliation_runs" in str(paths_a["json"])


def test_cli_reads_fixture_json_without_notion_or_ledger_writes(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "account"
    daily_plan_path = tmp_path / "daily_action_plan_20260701.json"
    executions_path = tmp_path / "manual_executions.json"
    _write_daily_plan(daily_plan_path)
    _write_manual_executions(executions_path)

    exit_code = preview_script.main(
        [
            "--workspace",
            str(workspace),
            "--account-id",
            ACCOUNT_ID,
            "--data-date",
            DATA_DATE,
            "--trade-date",
            TRADE_DATE,
            "--daily-plan-json",
            str(daily_plan_path),
            "--manual-executions-json",
            str(executions_path),
            "--account-root",
            str(account_root),
        ]
    )

    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["runner_result"] == "PASS"
    assert Path(output["latest_preview_json"]).exists()
