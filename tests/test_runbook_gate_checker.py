from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from scripts import runbook_gate_checker
from scripts import runbook_state
from core.paper_execution_intent import build_execution_intent


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-06-30"
TRADE_DATE = "2026-07-01"


def _save_state(tmp_path: Path, state: runbook_state.RunbookState) -> Path:
    if state.stage_status.get("A") == "PASS" and not state.artifacts.get("daily_plan_json"):
        items = [
            {"symbol": symbol, "action": action, "quantity": quantity}
            for symbol, action, quantity in (
                ("CCI", "SELL", 84),
                ("TDY", "BUY", 9),
                ("PLD", "SELL", 52),
                ("CMG", "BUY", 207),
            )
        ]
        plan_path = tmp_path / "daily_plan.json"
        plan_path.write_text(
            json.dumps(
                {
                    "schema_version": "paper_daily_plan.v1",
                    "account_id": state.frozen_context.account_id,
                    "data_date": state.frozen_context.data_date,
                    "trade_date": state.frozen_context.trade_date,
                    "plan_date": state.frozen_context.trade_date,
                    "run_mode": "official",
                    "official_run": True,
                    "generated_at": "2026-06-30T12:00:00Z",
                    "items": items,
                    "execution_intent": build_execution_intent(items),
                    "fingerprints": {"generator_version": "paper_daily_plan.v1"},
                }
            ),
            encoding="utf-8",
        )
        state = runbook_state.record_artifact(state, "daily_plan_json", str(plan_path), tmp_path)
    path = runbook_state.get_state_path_for_context(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
    )
    runbook_state.save_state(state, path)
    return path


def _save_no_action_state(tmp_path: Path) -> Path:
    state = _stage_a_pass_state()
    plan_path = tmp_path / "daily_plan_no_action.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "paper_daily_plan.v1",
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
                "plan_date": TRADE_DATE,
                "run_mode": "official",
                "official_run": True,
                "generated_at": "2026-06-30T12:00:00Z",
                "items": [],
                "execution_intent": build_execution_intent([]),
                "fingerprints": {"generator_version": "paper_daily_plan.v1"},
            }
        ),
        encoding="utf-8",
    )
    state = runbook_state.record_artifact(state, "daily_plan_json", str(plan_path), tmp_path)
    return _save_state(tmp_path, state)


def _stage_a_pass_state() -> runbook_state.RunbookState:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = replace(
        state,
        execution_contract={
            "version": runbook_state.EXECUTION_CONTRACT_V1,
            "input_finalized": False,
            "finalized_at": None,
        },
    )
    return runbook_state.complete_stage(state, "A")


def _ready_rows() -> list[dict[str, object]]:
    return [
        _row("CCI", "SELL", 84, 12.34),
        _row("TDY", "BUY", 9, 22.34),
        _row("PLD", "SELL", 52, 32.34),
        _row("CMG", "BUY", 207, 42.34),
    ]


def _row(
    symbol: str,
    side: str,
    quantity: int,
    actual_price: float | None,
    status: str = "READY",
    import_status: str = "NOT_IMPORTED",
    account_id: str = ACCOUNT_ID,
    execution_date: str = TRADE_DATE,
    linked_daily_plan_key: str | None = None,
    failed_count: int = 0,
) -> dict[str, object]:
    return {
        "page_id": f"page-{symbol}",
        "external_key": f"manual_execution:{ACCOUNT_ID}:{TRADE_DATE}:{symbol}:{side}:01",
        "account_id": account_id,
        "execution_date": execution_date,
        "linked_daily_plan_key": linked_daily_plan_key or f"daily_plan:{ACCOUNT_ID}:{TRADE_DATE}",
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "actual_price": actual_price,
        "status": status,
        "import_status": import_status,
        "failed_count": failed_count,
    }


def test_gate1_blocks_when_stage_a_not_pass(tmp_path: Path) -> None:
    _save_state(tmp_path, runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE))

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: _ready_rows(),
    )

    assert result["runner_result"] == "BLOCKED"
    latest = json.loads(Path(result["latest_gate_result_json"]).read_text(encoding="utf-8"))
    assert latest["summary"]["message"] == "Stage A must PASS before Gate 1 readiness check."


def test_gate1_blocks_when_stage_a_has_last_error(tmp_path: Path) -> None:
    state = _stage_a_pass_state()
    state = replace(state, last_error={"stage_id": "A", "reason": "old_stage_a_failure"})
    _save_state(tmp_path, state)

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: _ready_rows(),
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["next_required_action"] == "Fill Actual Price and set Status=READY in Notion."
    loaded = runbook_state.load_state(Path(result["latest_gate_result_json"]).parents[2] / "runbook_states" / f"{state.runbook_day_id}.json")
    assert loaded.current_status == "BLOCKED"


def test_gate1_passes_when_all_rows_ready(tmp_path: Path) -> None:
    state = _stage_a_pass_state()
    _save_state(tmp_path, state)

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: _ready_rows(),
    )

    assert result["runner_result"] == "PASS"
    assert result["ready_count"] == 4
    assert result["required_count"] == 4
    loaded = runbook_state.load_state(Path(result["state_path"]) if "state_path" in result else runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert loaded.stage_status["GATE1"] == "PASS"
    assert loaded.current_status == "PASS"


def test_new_v2_gate1_waits_until_execution_input_is_finalized(tmp_path: Path) -> None:
    state = runbook_state.complete_stage(
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        "A",
    )
    _save_state(tmp_path, state)

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: _ready_rows(),
    )

    assert result["runner_result"] == "WAIT"
    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert payload["ready_count"] == 0
    assert all("execution_input_not_finalized" in row["missing"] for row in payload["rows"])


def test_integrated_gate1_finalizes_v2_execution_then_passes(tmp_path: Path) -> None:
    state = runbook_state.complete_stage(
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        "A",
    )
    state_path = _save_state(tmp_path, state)

    result = runbook_gate_checker.check_gate1_execution_input(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: _ready_rows(),
    )

    loaded = runbook_state.load_state(state_path)
    assert result["runner_result"] == "PASS"
    assert loaded.execution_contract["input_finalized"] is True
    assert loaded.execution_contract["finalized_at"] is not None
    finalized_events = [
        event for event in loaded.history if event["event_type"] == "execution_input_finalized"
    ]
    assert len(finalized_events) == 1
    assert finalized_events[0]["created_at"] == loaded.execution_contract["finalized_at"]


def test_integrated_gate1_rerun_does_not_repeat_finalize(tmp_path: Path) -> None:
    state = runbook_state.complete_stage(
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        "A",
    )
    state_path = _save_state(tmp_path, state)

    first = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: _ready_rows()
    )
    first_state = runbook_state.load_state(state_path)
    finalized_at = first_state.execution_contract["finalized_at"]
    finalized_event_count = sum(
        event["event_type"] == "execution_input_finalized" for event in first_state.history
    )
    second = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: _ready_rows()
    )
    second_state = runbook_state.load_state(state_path)

    assert first["runner_result"] == second["runner_result"] == "PASS"
    assert second_state.execution_contract["finalized_at"] == finalized_at
    assert sum(
        event["event_type"] == "execution_input_finalized" for event in second_state.history
    ) == finalized_event_count


def test_integrated_gate1_preserves_finalize_across_wait_then_pass(tmp_path: Path) -> None:
    state = runbook_state.complete_stage(
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        "A",
    )
    state_path = _save_state(tmp_path, state)

    waiting = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )
    waiting_state = runbook_state.load_state(state_path)
    finalized_at = waiting_state.execution_contract["finalized_at"]
    passed = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: _ready_rows()
    )
    passed_state = runbook_state.load_state(state_path)

    assert waiting["runner_result"] == "WAIT"
    assert passed["runner_result"] == "PASS"
    assert passed_state.execution_contract["finalized_at"] == finalized_at
    assert sum(
        event["event_type"] == "execution_input_finalized" for event in passed_state.history
    ) == 1


def test_integrated_gate1_preconditions_do_not_finalize_or_query(tmp_path: Path) -> None:
    state_path = _save_state(
        tmp_path,
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
    )
    query_called = False

    def fetch_rows(state: runbook_state.RunbookState) -> list[dict[str, object]]:
        nonlocal query_called
        query_called = True
        return _ready_rows()

    result = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=fetch_rows
    )
    loaded = runbook_state.load_state(state_path)

    assert result["runner_result"] == "BLOCKED"
    assert loaded.execution_contract["input_finalized"] is False
    assert query_called is False


def test_integrated_gate1_missing_or_mismatched_state_does_not_query(tmp_path: Path) -> None:
    query_calls = 0

    def fetch_rows(state: runbook_state.RunbookState) -> list[dict[str, object]]:
        nonlocal query_calls
        query_calls += 1
        return _ready_rows()

    missing = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=fetch_rows
    )
    mismatched_state = runbook_state.create_initial_state("other_account", DATA_DATE, TRADE_DATE)
    state_path = runbook_state.get_state_path_for_context(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE
    )
    runbook_state.save_state(mismatched_state, state_path)
    mismatched = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=fetch_rows
    )
    loaded = runbook_state.load_state(state_path)

    assert missing["runner_result"] == "BLOCKED"
    assert mismatched["runner_result"] == "BLOCKED"
    assert loaded.execution_contract["input_finalized"] is False
    assert query_calls == 0


def test_integrated_gate1_no_action_skips_finalize_and_keeps_gate_contract(tmp_path: Path) -> None:
    state_path = _save_no_action_state(tmp_path)
    state = runbook_state.load_state(state_path)
    state = replace(
        state,
        execution_contract={
            "version": runbook_state.EXECUTION_CONTRACT_V2,
            "input_finalized": False,
            "finalized_at": None,
        },
    )
    runbook_state.save_state(state, state_path)

    passed = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )
    passed_state = runbook_state.load_state(state_path)

    assert passed["runner_result"] == "PASS"
    assert passed["action_mode"] == "NO_ACTION"
    assert passed_state.execution_contract["input_finalized"] is False


def test_integrated_gate1_no_action_blocks_unexpected_rows_without_finalize(tmp_path: Path) -> None:
    state_path = _save_no_action_state(tmp_path)
    state = runbook_state.load_state(state_path)
    state = replace(
        state,
        execution_contract={
            "version": runbook_state.EXECUTION_CONTRACT_V2,
            "input_finalized": False,
            "finalized_at": None,
        },
    )
    runbook_state.save_state(state, state_path)

    result = runbook_gate_checker.check_gate1_execution_input(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row("AAPL", "BUY", 1, 100.0)],
    )
    loaded = runbook_state.load_state(state_path)

    assert result["runner_result"] == "BLOCKED"
    assert loaded.execution_contract["input_finalized"] is False


def test_integrated_gate1_legacy_v1_skips_finalize_and_preserves_price_rule(
    tmp_path: Path,
) -> None:
    state_path = _save_state(tmp_path, _stage_a_pass_state())

    result = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: _ready_rows()
    )
    loaded = runbook_state.load_state(state_path)

    assert result["runner_result"] == "PASS"
    assert loaded.execution_contract["version"] == runbook_state.EXECUTION_CONTRACT_V1
    assert loaded.execution_contract["input_finalized"] is False

    rows = _ready_rows()
    rows[0]["actual_price"] = None
    waiting = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: rows
    )

    assert waiting["runner_result"] == "WAIT"


def test_integrated_gate1_finalize_failure_does_not_query(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state = runbook_state.complete_stage(
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        "A",
    )
    state_path = _save_state(tmp_path, state)
    query_called = False

    def fail_finalize(state: runbook_state.RunbookState) -> runbook_state.RunbookState:
        raise ValueError("finalize failed")

    def fetch_rows(state: runbook_state.RunbookState) -> list[dict[str, object]]:
        nonlocal query_called
        query_called = True
        return _ready_rows()

    monkeypatch.setattr(runbook_state, "finalize_execution_input", fail_finalize)
    result = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=fetch_rows
    )
    loaded = runbook_state.load_state(state_path)

    assert result["runner_result"] == "BLOCKED"
    assert "Finalize failed" in result["message"]
    assert loaded.execution_contract["input_finalized"] is False
    assert loaded.last_error["reason"] == "execution_input_finalize_failed"
    assert query_called is False


def test_integrated_gate1_query_failure_keeps_single_finalize_for_retry(tmp_path: Path) -> None:
    state = runbook_state.complete_stage(
        runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE),
        "A",
    )
    state_path = _save_state(tmp_path, state)

    def fail_query(state: runbook_state.RunbookState) -> list[dict[str, object]]:
        raise RuntimeError("query unavailable")

    blocked = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=fail_query
    )
    blocked_state = runbook_state.load_state(state_path)
    finalized_at = blocked_state.execution_contract["finalized_at"]
    passed = runbook_gate_checker.check_gate1_execution_input(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: _ready_rows()
    )
    passed_state = runbook_state.load_state(state_path)

    assert blocked["runner_result"] == "BLOCKED"
    assert passed["runner_result"] == "PASS"
    assert passed_state.execution_contract["finalized_at"] == finalized_at
    assert sum(
        event["event_type"] == "execution_input_finalized" for event in passed_state.history
    ) == 1


def test_gate1_waits_when_actual_price_missing(tmp_path: Path) -> None:
    state = _stage_a_pass_state()
    _save_state(tmp_path, state)
    rows = _ready_rows()
    rows[0]["actual_price"] = None

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: rows,
    )

    assert result["runner_result"] == "WAIT"
    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert payload["ready_count"] == 3
    assert payload["missing_count"] == 1
    assert payload["rows"][0]["missing"] == ["actual_price"]


def test_gate1_execution_waits_when_rows_are_missing(tmp_path: Path) -> None:
    _save_state(tmp_path, _stage_a_pass_state())

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "WAIT"
    assert result["action_mode"] == "EXECUTION"


def test_gate1_waits_when_status_is_draft(tmp_path: Path) -> None:
    state = _stage_a_pass_state()
    _save_state(tmp_path, state)
    rows = _ready_rows()
    rows[1]["status"] = "DRAFT"

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: rows,
    )

    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert result["runner_result"] == "WAIT"
    assert payload["rows"][1]["symbol"] == "TDY"
    assert "status_READY" in payload["rows"][1]["missing"]


def test_gate1_waits_when_import_status_is_not_not_imported(tmp_path: Path) -> None:
    state = _stage_a_pass_state()
    _save_state(tmp_path, state)
    rows = _ready_rows()
    rows[2]["import_status"] = "IMPORTED"

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: rows,
    )

    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert result["runner_result"] == "WAIT"
    assert "import_status_NOT_IMPORTED" in payload["rows"][2]["missing"]


def test_gate1_blocks_when_notion_query_fails(tmp_path: Path) -> None:
    state = _stage_a_pass_state()
    _save_state(tmp_path, state)

    def failing_fetcher(state: runbook_state.RunbookState) -> list[dict[str, object]]:
        raise RuntimeError("query failed")

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=failing_fetcher,
    )

    assert result["runner_result"] == "BLOCKED"
    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert "Notion manual execution query failed" in payload["summary"]["message"]


def test_gate1_no_action_passes_without_manual_execution_rows(tmp_path: Path) -> None:
    state_path = _save_no_action_state(tmp_path)

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [],
    )

    assert result["runner_result"] == "PASS"
    assert result["action_mode"] == "NO_ACTION"
    assert result["execution_required"] is False
    assert result["candidate_execution_count"] == 0
    assert result["manual_execution_row_count"] == 0
    assert result["message"] == "No execution input is required for this runbook day."
    loaded = runbook_state.load_state(state_path)
    assert loaded.stage_status["GATE1"] == "PASS"
    assert "gate1_readiness_json" in loaded.artifacts


def test_gate1_no_action_blocks_unexpected_manual_execution_rows(tmp_path: Path) -> None:
    _save_no_action_state(tmp_path)

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row("AAPL", "BUY", 1, 100.0)],
    )

    assert result["runner_result"] == "BLOCKED"
    state = runbook_state.load_state(
        runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    )
    assert state.last_error["reason"] == "unexpected_manual_execution_rows_for_no_action"


def test_gate1_no_action_blocks_when_notion_query_fails(tmp_path: Path) -> None:
    _save_no_action_state(tmp_path)

    def fail_query(state: runbook_state.RunbookState) -> list[dict]:
        raise RuntimeError("query unavailable")

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=fail_query
    )

    assert result["runner_result"] == "BLOCKED"
    state = runbook_state.load_state(
        runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    )
    assert state.last_error["reason"] == "notion_manual_execution_query_failed"


def test_gate1_blocks_missing_daily_plan_json(tmp_path: Path) -> None:
    state = _stage_a_pass_state()
    path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, path)

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["message"] == "daily_plan_json is not pinned in runbook state"


def test_gate1_blocks_malformed_execution_intent(tmp_path: Path) -> None:
    state_path = _save_no_action_state(tmp_path)
    state = runbook_state.load_state(state_path)
    plan_path = tmp_path / state.artifacts["daily_plan_json"]
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["execution_intent"]["action_mode"] = "EXECUTION"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "BLOCKED"
    loaded = runbook_state.load_state(state_path)
    assert loaded.last_error["reason"] == "daily_plan_execution_intent_invalid"


def test_gate1_blocks_daily_plan_context_mismatch(tmp_path: Path) -> None:
    state_path = _save_no_action_state(tmp_path)
    state = runbook_state.load_state(state_path)
    plan_path = tmp_path / state.artifacts["daily_plan_json"]
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["account_id"] = "paper_other"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, row_fetcher=lambda state: []
    )

    assert result["runner_result"] == "BLOCKED"
    loaded = runbook_state.load_state(state_path)
    assert loaded.last_error["reason"] == "daily_plan_context_mismatch"


def test_gate1_query_uses_env_compatible_notion_settings(monkeypatch) -> None:
    state = _stage_a_pass_state()
    calls: dict[str, object] = {}

    class FakeClient:
        def __init__(self, token: str) -> None:
            calls["token"] = token

        def query_data_source(
            self,
            data_source_id: str,
            *,
            filter_payload: dict[str, object],
            page_size: int,
        ) -> list[dict[str, object]]:
            calls["data_source_id"] = data_source_id
            calls["filter_payload"] = filter_payload
            calls["page_size"] = page_size
            return []

    def fake_load_settings(*, allow_missing: bool = False):
        calls["allow_missing"] = allow_missing
        return object()

    def fake_data_source_id(settings, key: str, *, env_override: str | None = None) -> str:
        calls["data_source_key"] = key
        calls["env_override"] = env_override
        return "manual-executions-source"

    monkeypatch.setattr(runbook_gate_checker, "_load_dotenv_if_available", lambda: None)
    monkeypatch.setattr(runbook_gate_checker, "load_notion_settings", fake_load_settings)
    monkeypatch.setattr(
        runbook_gate_checker,
        "load_notion_property_mapping",
        lambda: {
            "manual_executions": {
                "account_id": "Account ID",
                "execution_date": "Execution Date",
                "linked_daily_plan_key": "Linked Daily Plan Key",
                "external_key": "External Key",
                "symbol": "Symbol",
                "side": "Side",
                "quantity": "Quantity",
                "actual_price": "Actual Price",
                "status": "Status",
                "import_status": "Import Status",
            }
        },
    )
    monkeypatch.setattr(runbook_gate_checker, "get_notion_data_source_id", fake_data_source_id)
    monkeypatch.setattr(runbook_gate_checker, "get_notion_token", lambda settings: "fake-token")
    monkeypatch.setattr(runbook_gate_checker, "NotionClient", FakeClient)

    rows = runbook_gate_checker.query_manual_execution_rows(state)

    assert rows == []
    assert calls["allow_missing"] is True
    assert calls["data_source_key"] == "manual_executions"
    assert calls["env_override"] == "NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID"
    assert calls["token"] == "fake-token"
    assert calls["data_source_id"] == "manual-executions-source"
    assert calls["page_size"] == 100


def test_gate1_writes_json_txt_and_latest(tmp_path: Path) -> None:
    state = _stage_a_pass_state()
    _save_state(tmp_path, state)

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: _ready_rows(),
    )

    assert Path(result["gate_result_json"]).exists()
    assert Path(result["gate_result_txt"]).exists()
    assert Path(result["latest_gate_result_json"]).exists()
    assert Path(result["latest_gate_result_txt"]).exists()
    assert "[PASS] GATE1 readiness" in Path(result["latest_gate_result_txt"]).read_text(encoding="utf-8")


def test_gate1_blocks_on_frozen_context_mismatch(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state("other_account", DATA_DATE, TRADE_DATE)
    path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, path)

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: _ready_rows(),
    )

    assert result["runner_result"] == "BLOCKED"
    payload = json.loads(Path(result["gate_result_json"]).read_text(encoding="utf-8"))
    assert "context_mismatch_existing_runbook_state" in payload["summary"]["message"]


def test_gate1_cli_outputs_wait_json(tmp_path: Path, monkeypatch) -> None:
    state = _stage_a_pass_state()
    _save_state(tmp_path, state)

    monkeypatch.setattr(
        runbook_gate_checker,
        "query_manual_execution_rows",
        lambda state: [_row("CCI", "SELL", 84, None)],
    )

    result = runbook_gate_checker.check_gate1_readiness(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        row_fetcher=lambda state: [_row("CCI", "SELL", 84, None)],
    )

    assert result["runner_result"] == "WAIT"


def test_integrated_gate1_cli_prints_only_final_gate_result(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    expected = {
        "runner_result": "WAIT",
        "gate_id": "GATE1",
        "message": "Fill Actual Price and set Status=READY in Notion.",
    }
    monkeypatch.setattr(
        runbook_gate_checker,
        "check_gate1_execution_input",
        lambda **kwargs: expected,
    )

    exit_code = runbook_gate_checker.main(
        [
            "gate1-execution-input",
            "--workspace",
            str(tmp_path),
            "--account-id",
            ACCOUNT_ID,
            "--data-date",
            DATA_DATE,
            "--trade-date",
            TRADE_DATE,
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == expected


def test_gate1_cli_smoke_with_missing_state_returns_blocked(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_gate_checker.py",
            "gate1",
            "--workspace",
            str(tmp_path),
            "--account-id",
            ACCOUNT_ID,
            "--data-date",
            DATA_DATE,
            "--trade-date",
            TRADE_DATE,
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    assert completed.returncode == 1
    payload = json.loads(completed.stdout)
    assert payload["runner_result"] == "BLOCKED"
