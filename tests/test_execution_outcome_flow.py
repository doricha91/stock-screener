from __future__ import annotations

import json
from dataclasses import replace

import pytest

from core.execution_outcome_flow import (
    RECONCILIATION_CONTRACT_V1,
    RECONCILIATION_CONTRACT_V2,
    build_execution_commit_plan,
    derive_execution_preview,
)
from core.execution_reconciliation import BLOCKED, EXECUTED, NOT_EXECUTED, PARTIAL, PASS, WAIT, build_manual_execution_key
from core.notion_account_keys import build_daily_plan_external_key
from core.notion_manual_execution_importer import normalize_manual_execution_pages
from core.paper_manual_execution_commit import commit_manual_execution_preview
from core.paper_daily_review_scope import sha256_file
from scripts.runbook_state import (
    EXECUTION_CONTRACT_V1,
    activate_execution_outcome_v2,
    create_initial_state,
    finalize_execution_input,
    get_state_path_for_context,
    save_state,
)
from scripts.runbook_execution_reconciliation_preview import run_execution_reconciliation_preview


ACCOUNT = "paper_pilot_202606"
DATA_DATE = "2026-06-30"
TRADE_DATE = "2026-07-01"


def _plan(quantity: int = 10) -> list[dict[str, object]]:
    return [{"symbol": "AAPL", "action": "BUY", "quantity": quantity, "price": 100.0}]


def _execution(quantity: object, price: object) -> dict[str, object]:
    return {
        "page_id": "page-aapl",
        "external_key": build_manual_execution_key(ACCOUNT, TRADE_DATE, "AAPL", "BUY", 1),
        "account_id": ACCOUNT,
        "execution_date": TRADE_DATE,
        "linked_daily_plan_key": build_daily_plan_external_key(ACCOUNT, TRADE_DATE),
        "symbol": "AAPL",
        "side": "BUY",
        "quantity": quantity,
        "actual_price": price,
        "status": "READY",
        "import_status": "NOT_IMPORTED",
    }


def _v2(quantity: object, price: object, *, finalized: bool) -> dict[str, object]:
    return derive_execution_preview(
        _plan(),
        [_execution(quantity, price)],
        account_id=ACCOUNT,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        contract_version=RECONCILIATION_CONTRACT_V2,
        input_finalized=finalized,
    )


def _notion_mapping() -> dict[str, str]:
    return {
        "name": "Name",
        "execution_date": "Execution Date",
        "symbol": "Symbol",
        "side": "Side",
        "quantity": "Quantity",
        "actual_price": "Actual Price",
        "status": "Status",
    }


def _notion_page() -> dict[str, object]:
    return {
        "id": "page-aapl",
        "properties": {
            "Name": {"title": [{"plain_text": "AAPL BUY"}]},
            "Execution Date": {"date": {"start": TRADE_DATE}},
            "Symbol": {"rich_text": [{"plain_text": "AAPL"}]},
            "Side": {"select": {"name": "BUY"}},
            "Quantity": {"number": None},
            "Actual Price": {"number": None},
            "Status": {"select": {"name": "READY"}},
        },
    }


def test_raw_blank_quantity_and_price_are_not_coerced_to_zero() -> None:
    candidate = normalize_manual_execution_pages(
        pages=[_notion_page()], mapping=_notion_mapping(), account_id=ACCOUNT
    )[0]
    assert candidate.quantity is None
    assert candidate.actual_price is None


def test_blank_before_finalize_waits() -> None:
    result = _v2(None, None, finalized=False)
    assert result["runner_result"] == WAIT
    assert result["rows"][0]["status"] == WAIT


def test_blank_after_finalize_is_not_executed() -> None:
    result = _v2(None, None, finalized=True)
    assert result["runner_result"] == PASS
    assert result["rows"][0]["outcome"] == NOT_EXECUTED


def test_full_quantity_and_valid_price_is_executed() -> None:
    assert _v2(10, 101.5, finalized=True)["rows"][0]["outcome"] == EXECUTED


def test_partial_quantity_and_valid_price_is_partial() -> None:
    assert _v2(4, 101.5, finalized=True)["rows"][0]["outcome"] == PARTIAL


@pytest.mark.parametrize(
    ("quantity", "price", "reason"),
    [(5, None, "quantity_without_price"), (None, 101.5, "price_without_quantity")],
)
def test_one_sided_quantity_or_price_is_blocked(quantity: object, price: object, reason: str) -> None:
    result = _v2(quantity, price, finalized=True)
    assert result["runner_result"] == BLOCKED
    assert result["rows"][0]["reason_code"] == reason


@pytest.mark.parametrize(
    ("quantity", "price"),
    [(0, 100), (-1, 100), ("-", 100), ("NaN", 100), ("Inf", 100), (11, 100), (5, 0), (5, -1), (5, "-")],
)
def test_explicit_invalid_or_excess_input_is_blocked(quantity: object, price: object) -> None:
    assert _v2(quantity, price, finalized=True)["runner_result"] == BLOCKED


def test_finalize_first_call_succeeds_and_second_is_exact_no_op() -> None:
    state = activate_execution_outcome_v2(create_initial_state(ACCOUNT, DATA_DATE, TRADE_DATE))
    finalized = finalize_execution_input(state)
    assert finalized.execution_contract["input_finalized"] is True
    assert finalize_execution_input(finalized) is finalized


def test_runbook_preview_reads_persisted_finalize_state(tmp_path) -> None:
    workspace = tmp_path / "workspace"
    state = finalize_execution_input(
        activate_execution_outcome_v2(create_initial_state(ACCOUNT, DATA_DATE, TRADE_DATE))
    )
    save_state(
        state,
        get_state_path_for_context(workspace, ACCOUNT, DATA_DATE, TRADE_DATE),
    )
    plan_path = tmp_path / "daily_plan.json"
    rows_path = tmp_path / "execution_rows.json"
    plan_path.write_text(json.dumps(_plan()), encoding="utf-8")
    rows_path.write_text(json.dumps([_execution(None, None)]), encoding="utf-8")

    result = run_execution_reconciliation_preview(
        workspace,
        ACCOUNT,
        DATA_DATE,
        TRADE_DATE,
        daily_plan_path=plan_path,
        manual_executions_path=rows_path,
        account_root=tmp_path / "paper_account",
    )

    assert result["runner_result"] == PASS
    preview = json.loads((workspace / "reconciliation_runs" / state.runbook_day_id / "latest_execution_reconciliation_preview.json").read_text(encoding="utf-8"))
    assert preview["input_finalized"] is True
    assert preview["not_executed_count"] == 1


def test_mixed_commit_plan_contains_only_executed_and_partial() -> None:
    plan = [
        {"symbol": "AAPL", "action": "BUY", "quantity": 10, "price": 100},
        {"symbol": "MSFT", "action": "BUY", "quantity": 8, "price": 200},
        {"symbol": "NVDA", "action": "BUY", "quantity": 6, "price": 300},
    ]
    rows = [
        {**_execution(10, 101), "external_key": build_manual_execution_key(ACCOUNT, TRADE_DATE, "AAPL", "BUY", 1)},
        {**_execution(3, 202), "symbol": "MSFT", "page_id": "page-msft", "external_key": build_manual_execution_key(ACCOUNT, TRADE_DATE, "MSFT", "BUY", 1)},
        {**_execution(None, None), "symbol": "NVDA", "page_id": "page-nvda", "external_key": build_manual_execution_key(ACCOUNT, TRADE_DATE, "NVDA", "BUY", 1)},
    ]
    preview = derive_execution_preview(
        plan, rows, account_id=ACCOUNT, data_date=DATA_DATE, trade_date=TRADE_DATE,
        contract_version=RECONCILIATION_CONTRACT_V2, input_finalized=True,
    )
    commit_plan = build_execution_commit_plan(preview)
    assert commit_plan["committed_trade_count"] == 2
    assert commit_plan["not_executed_count"] == 1


def test_all_not_executed_commit_is_complete_zero_write(tmp_path) -> None:
    preview = _v2(None, None, finalized=True)
    commit_plan = build_execution_commit_plan(preview)
    input_preview = tmp_path / "input.json"
    input_preview.write_text(
        json.dumps({"account_id": ACCOUNT, "execution_date": TRADE_DATE, "candidates": [], "fail_count": 0, "commit_allowed": "true"}),
        encoding="utf-8",
    )
    reconciliation_preview = tmp_path / "reconciliation.json"
    reconciliation_preview.write_text(json.dumps(preview), encoding="utf-8")
    result = commit_manual_execution_preview(
        execution_date=TRADE_DATE,
        preview_json_path=input_preview,
        eligible_candidate_keys=set(commit_plan["candidate_keys"]),
        expected_outcome_rows=list(commit_plan["rows"]),
        allow_zero_write=True,
        data_date=DATA_DATE,
        reconciliation_preview_json_path=reconciliation_preview,
        reconciliation_preview_sha256=sha256_file(reconciliation_preview),
    )
    assert result.committed_row_count == 0
    assert result.committed_trade_ids == []
    assert not result.current_state_written
    assert result.commit_json_path
    sidecar_before = (tmp_path / "manual_execution_import_commit_20260701.json").read_bytes()
    rerun = commit_manual_execution_preview(
        execution_date=TRADE_DATE,
        preview_json_path=input_preview,
        eligible_candidate_keys=set(commit_plan["candidate_keys"]),
        expected_outcome_rows=list(commit_plan["rows"]),
        allow_zero_write=True,
        data_date=DATA_DATE,
        reconciliation_preview_json_path=reconciliation_preview,
        reconciliation_preview_sha256=sha256_file(reconciliation_preview),
    )
    assert rerun.committed_row_count == 0
    assert (tmp_path / "manual_execution_import_commit_20260701.json").read_bytes() == sidecar_before
    assert {path.name for path in tmp_path.iterdir()} == {
        "input.json",
        "reconciliation.json",
        "manual_execution_import_commit_20260701.json",
        "manual_execution_import_commit_20260701.md",
    }


def test_any_blocked_row_makes_batch_zero_write() -> None:
    commit_plan = build_execution_commit_plan(_v2(5, None, finalized=True))
    assert commit_plan["runner_result"] == BLOCKED
    assert commit_plan["persistent_write"] is False
    assert commit_plan["rows"] == []


def test_commit_plan_requires_latest_state_and_hard_cap_revalidation() -> None:
    commit_plan = build_execution_commit_plan(_v2(5, 100, finalized=True))
    assert commit_plan["requires_latest_state_revalidation"] is True


def test_completed_v1_dispatch_stays_on_v1() -> None:
    result = derive_execution_preview(
        _plan(), [_execution(10, 100)], account_id=ACCOUNT, data_date=DATA_DATE,
        trade_date=TRADE_DATE, contract_version=RECONCILIATION_CONTRACT_V1, input_finalized=False,
    )
    assert result["schema_version"] == RECONCILIATION_CONTRACT_V1
    assert result["runner_result"] == PASS


def test_completed_v1_runbook_cannot_be_upgraded() -> None:
    state = create_initial_state(ACCOUNT, DATA_DATE, TRADE_DATE)
    state = replace(
        state,
        last_completed_step=8,
        stage_status={**state.stage_status, "B": "PASS"},
        execution_contract={
            "version": EXECUTION_CONTRACT_V1,
            "input_finalized": False,
            "finalized_at": None,
        },
    )
    with pytest.raises(ValueError, match="immutable"):
        activate_execution_outcome_v2(state)


def test_unsupported_contract_version_fails_closed() -> None:
    preview = derive_execution_preview(
        _plan(), [_execution(10, 100)], account_id=ACCOUNT, data_date=DATA_DATE,
        trade_date=TRADE_DATE, contract_version="execution_reconciliation_preview.v999",
        input_finalized=True,
    )
    assert preview["runner_result"] == BLOCKED
    assert build_execution_commit_plan(preview)["runner_result"] == BLOCKED
