from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.execution_reconciliation import PARTIAL, build_manual_execution_key
from core.notion_account_keys import build_daily_plan_external_key
from core.paper_execution_intent import build_execution_intent
from scripts import runbook_gate_checker, runbook_state
from scripts.runbook_execution_reconciliation_preview import (
    run_execution_reconciliation_preview,
)
from tests.paper_account_test_support import ensure_initialized_account_paths


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-06-30"
TRADE_DATE = "2026-07-01"


def _manual_execution_mapping() -> dict[str, str]:
    return {
        "external_key": "External Key",
        "account_id": "Account ID",
        "execution_date": "Execution Date",
        "linked_daily_plan_key": "Linked Daily Plan Key",
        "symbol": "Symbol",
        "side": "Side",
        "quantity": "Quantity",
        "actual_price": "Actual Price",
        "execution_sequence": "Execution Sequence",
        "status": "Status",
        "import_status": "Import Status",
    }


def _draft_notion_page() -> dict[str, Any]:
    return {
        "id": "page-aapl",
        "properties": {
            "External Key": {
                "rich_text": [
                    {
                        "plain_text": build_manual_execution_key(
                            ACCOUNT_ID, TRADE_DATE, "AAPL", "BUY", 1
                        )
                    }
                ]
            },
            "Account ID": {"select": {"name": ACCOUNT_ID}},
            "Execution Date": {"date": {"start": TRADE_DATE}},
            "Linked Daily Plan Key": {
                "rich_text": [
                    {"plain_text": build_daily_plan_external_key(ACCOUNT_ID, TRADE_DATE)}
                ]
            },
            "Symbol": {"rich_text": [{"plain_text": "AAPL"}]},
            "Side": {"select": {"name": "BUY"}},
            "Quantity": {"type": "number", "number": 10},
            "Actual Price": {"type": "number", "number": None},
            "Execution Sequence": {"type": "number", "number": None},
            "Status": {"select": {"name": "DRAFT"}},
            "Import Status": {"select": {"name": "NOT_IMPORTED"}},
        },
    }


def test_v3_notion_row_keeps_sequence_through_gate1_and_reconciliation(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    account_root = tmp_path / "account"
    workspace.mkdir(parents=True, exist_ok=True)
    ensure_initialized_account_paths(account_root, account_id=ACCOUNT_ID, date_str=DATA_DATE)

    plan = {
        "schema_version": "paper_daily_plan.v1",
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "plan_date": TRADE_DATE,
        "run_mode": "official",
        "official_run": True,
        "generated_at": "2026-06-30T12:00:00Z",
        "items": [{"symbol": "AAPL", "action": "BUY", "quantity": 10, "price": 100.0}],
        "execution_intent": build_execution_intent(
            [{"symbol": "AAPL", "action": "BUY", "quantity": 10}]
        ),
        "fingerprints": {"generator_version": "paper_daily_plan.v1"},
    }
    plan_path = workspace / "daily_plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    state = runbook_state.complete_stage(
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        "A",
    )
    state = runbook_state.record_artifact(state, "daily_plan_json", str(plan_path), workspace)
    state_path = runbook_state.get_state_path_for_context(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE
    )
    runbook_state.save_state(state, state_path)

    page = _draft_notion_page()
    draft = runbook_gate_checker.normalize_notion_manual_execution_page(
        page, _manual_execution_mapping()
    )
    assert draft["status"] == "DRAFT"
    assert draft["execution_sequence"] is None

    properties = page["properties"]
    properties["Quantity"]["number"] = 4
    properties["Actual Price"]["number"] = 101.5
    properties["Execution Sequence"]["number"] = 3
    properties["Status"]["select"]["name"] = "READY"
    ready_row = runbook_gate_checker.normalize_notion_manual_execution_page(
        page, _manual_execution_mapping()
    )

    gate = runbook_gate_checker.check_gate1_execution_input(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [ready_row],
    )
    assert gate["runner_result"] == "PASS"

    reconciliation = run_execution_reconciliation_preview(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        daily_plan_path=plan_path,
        row_fetcher=lambda state: [ready_row],
        account_root=account_root,
    )
    payload = json.loads(Path(reconciliation["latest_preview_json"]).read_text(encoding="utf-8"))

    assert reconciliation["runner_result"] == "PASS"
    assert payload["schema_version"] == runbook_state.EXECUTION_CONTRACT_V3
    assert payload["rows"][0]["outcome"] == PARTIAL
    assert payload["rows"][0]["execution_sequence"] == 3
