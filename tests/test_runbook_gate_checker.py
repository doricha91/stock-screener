from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from scripts import runbook_gate_checker
from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-06-30"
TRADE_DATE = "2026-07-01"


def _save_state(tmp_path: Path, state: runbook_state.RunbookState) -> Path:
    path = runbook_state.get_state_path_for_context(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
    )
    runbook_state.save_state(state, path)
    return path


def _stage_a_pass_state() -> runbook_state.RunbookState:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
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
