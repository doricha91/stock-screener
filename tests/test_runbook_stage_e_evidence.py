from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from core import runbook_day_rollover as rollover_core
from core.paper_daily_ops_evidence import (
    EVIDENCE_DAILY_PLAN_NOTION_EXPORT,
    EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC,
    EVIDENCE_MANUAL_EXECUTION_TEMPLATE,
    EVIDENCE_MANUAL_REVIEW_STATUS_SYNC,
    EVIDENCE_MANUAL_REVIEW_TEMPLATE,
    notion_evidence_path,
)
from core.paper_daily_ops_orchestrator import build_daily_ops_status
from core.runbook_calendar import load_market_calendar
from core.runbook_day_rollover import preview_rollover
from scripts import paper_daily_ops
from scripts import runbook_command_registry
from scripts import runbook_result
from scripts import runbook_stage_e_evidence
from scripts import runbook_state
from tests import test_runbook_day_rollover as rollover_fixtures


ACCOUNT_ID = "paper_ops"
DATA_DATE = "2026-06-05"
TRADE_DATE = "2026-06-08"
_MISSING = object()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: object) -> Path:
    _write(path, json.dumps(payload, ensure_ascii=False))
    return path


def _write_notion_evidence(root: Path, evidence_type: str) -> None:
    operation = "sync" if evidence_type.endswith("STATUS_SYNC") else "export"
    _write_json(
        notion_evidence_path(root, evidence_type, TRADE_DATE),
        {
            "schema_version": "paper_notion_evidence.v1",
            "evidence_type": evidence_type,
            "account_id": ACCOUNT_ID,
            "trade_date": TRADE_DATE,
            "data_date": DATA_DATE,
            "source_command": "python scripts\\example.py --json",
            "source_artifacts": [],
            "target_system": "notion",
            "operation": operation,
            "dry_run": False,
            "actual_executed": True,
            "notion_api_called": True,
            "write_executed": True,
            "status": "PASS",
            "page_count": 1,
            "created_count": 0,
            "updated_count": 1,
            "skipped_count": 0,
            "failed_count": 0,
            "warnings": [],
            "errors": [],
            "created_at": "2026-06-08T09:00:00+09:00",
            "producer": "test",
        },
    )


def _build_terminal_account(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "paper_accounts" / ACCOUNT_ID
    legacy = tmp_path / "paper_test"
    for base in (root, legacy):
        (base / "reports").mkdir(parents=True)
        (base / "reviews").mkdir()
        (base / "config_snapshots").mkdir()

    _write(root / "daily_action_plan_20260608.md", "# plan\n")
    _write_json(
        root / "daily_action_plan_20260608.json",
        {
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "plan_date": TRADE_DATE,
        },
    )
    _write_json(root / "config_snapshots" / "paper_config_snapshot_20260608.json", {"ok": True})
    _write_notion_evidence(root, EVIDENCE_DAILY_PLAN_NOTION_EXPORT)
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_TEMPLATE)
    _write_json(
        root / "reports" / "manual_execution_import_preview_20260608.json",
        {
            "account_id": ACCOUNT_ID,
            "execution_date": TRADE_DATE,
            "candidate_count": 1,
            "fail_count": 0,
            "commit_allowed": "true",
            "candidates": [],
        },
    )
    _write_json(
        root / "reports" / "manual_execution_import_commit_20260608.json",
        {"account_id": ACCOUNT_ID, "execution_date": TRADE_DATE, "committed_rows": []},
    )
    _write(root / "paper_current_state_20260608.json", "{}\n")
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,cash,total_equity_market_value,unrealized_pnl,position_count,symbols\n"
        "2026-06-08,100,100,0,0,\n",
    )
    _write(root / "paper_position_snapshot.csv", "snapshot_date,symbol\n2026-06-08,AAPL\n")
    _write(root / "paper_execution_log.csv", "date,source,symbol\n2026-06-08,notion_manual_execution,AAPL\n")
    _write_notion_evidence(root, EVIDENCE_MANUAL_EXECUTION_STATUS_SYNC)
    _write(root / "reports" / "paper_daily_review_summary.md", "# summary\nLatest snapshot date: 2026-06-08\n")
    _write(root / "reports" / "paper_performance_summary.md", "# perf\nLatest Snapshot Date: 2026-06-08\n")
    _write(
        root / "reviews" / "paper_manual_review_log_template.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n2026-06-08,AAPL,Q1,,pending\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log_validation_report.md",
        "# validation\n\n- Validation result: PASS\n",
    )
    _write_notion_evidence(root, EVIDENCE_MANUAL_REVIEW_TEMPLATE)
    _write_json(
        root / "reports" / "manual_review_import_preview_20260608.json",
        {
            "account_id": ACCOUNT_ID,
            "review_date": TRADE_DATE,
            "candidate_count": 1,
            "fail_count": 0,
            "append_allowed": "true",
            "duplicate_candidates": [],
            "candidates": [],
        },
    )
    _write_json(
        root / "reports" / "manual_review_import_commit_20260608.json",
        {"account_id": ACCOUNT_ID, "review_date": TRADE_DATE, "rows": []},
    )
    _write(
        root / "reviews" / "paper_manual_review_log.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n2026-06-08,AAPL,Q1,done,reviewed\n",
    )
    _write_notion_evidence(root, EVIDENCE_MANUAL_REVIEW_STATUS_SYNC)
    return root, legacy


@pytest.fixture(scope="module")
def actual_payload(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root, legacy = _build_terminal_account(tmp_path_factory.mktemp("stage_e_contract"))
    payload = build_daily_ops_status(
        account_id=ACCOUNT_ID,
        data_date=DATA_DATE,
        trade_date=TRADE_DATE,
        account_root=root,
        legacy_root=legacy,
    )
    assert payload["overall_status"] == "PASS"
    assert payload["workflow_status"] == "REVIEW_DONE"
    assert payload["blockers"] == []
    assert payload["warnings"] == []
    assert "unresolved_error_count" not in payload
    return payload


def _state() -> runbook_state.RunbookState:
    return runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)


def _store_wrapper(workspace: Path, payload: dict[str, object]) -> runbook_state.RunbookState:
    state = _state()
    wrapper = runbook_result.create_command_result(
        state,
        runbook_command_registry.get_command("final_status"),
        "PASS",
        "Final status is PASS.",
        raw_payload=payload,
        process={"executed": True, "exit_code": 0, "duration_ms": 1},
        workspace=workspace,
    )
    path = _write_json(workspace / "command_runs" / state.runbook_day_id / "final_status.json", wrapper)
    return runbook_state.record_artifact(state, "final_status_report_json", str(path), workspace)


def test_actual_producer_payload_and_stored_wrapper_satisfy_validator(
    tmp_path: Path,
    actual_payload: dict[str, object],
) -> None:
    assert set(runbook_stage_e_evidence.FINAL_STATUS_REQUIRED_FIELDS) <= set(actual_payload)
    assert runbook_stage_e_evidence.validate_final_status_payload(actual_payload, _state()) == []

    state = _store_wrapper(tmp_path / "workspace", actual_payload)
    assert runbook_stage_e_evidence.validate_stored_final_status(tmp_path / "workspace", state) == {
        "valid": True,
        "blockers": [],
    }


def test_registry_cli_producer_wrapper_validator_contract(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root, legacy = _build_terminal_account(tmp_path)
    command = runbook_command_registry.get_command("final_status")
    assert command.step_id == 18
    assert command.stage_id == "E"
    assert command.argv_template[:2] == ("scripts\\paper_daily_ops.py", "status")
    assert "--include-notion-read" not in command.argv_template

    exit_code = paper_daily_ops.main(
        [
            "status",
            "--account-id",
            ACCOUNT_ID,
            "--data-date",
            DATA_DATE,
            "--trade-date",
            TRADE_DATE,
            "--account-root",
            str(root),
            "--legacy-root",
            str(legacy),
            "--json",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert runbook_stage_e_evidence.validate_final_status_payload(payload, _state()) == []
    state = _store_wrapper(tmp_path / "workspace", payload)
    assert runbook_stage_e_evidence.validate_stored_final_status(tmp_path / "workspace", state)["valid"] is True


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("account_id", _MISSING),
        ("account_id", "paper_other"),
        ("account_id", 7),
        ("data_date", _MISSING),
        ("data_date", "2026-06-04"),
        ("data_date", 20260605),
        ("trade_date", _MISSING),
        ("trade_date", "2026-06-09"),
        ("trade_date", True),
        ("overall_status", _MISSING),
        ("overall_status", None),
        ("overall_status", "WARNING"),
        ("overall_status", "UNKNOWN"),
        ("overall_status", "BLOCKED"),
        ("overall_status", "FAILED"),
        ("overall_status", "ERROR"),
        ("workflow_status", _MISSING),
        ("workflow_status", "DONE"),
        ("blockers", _MISSING),
        ("blockers", {}),
        ("blockers", ["unresolved blocker"]),
        ("warnings", _MISSING),
        ("warnings", {}),
        ("warnings", ["unexpected warning"]),
        ("read_only", _MISSING),
        ("read_only", False),
        ("read_only", 1),
        ("read_only", "true"),
        ("write_executed", _MISSING),
        ("write_executed", True),
        ("write_executed", 0),
        ("write_executed", "false"),
        ("operation_write_executed", _MISSING),
        ("operation_write_executed", True),
        ("commit_append_executed", _MISSING),
        ("commit_append_executed", True),
        ("notion_api_called", _MISSING),
        ("notion_api_called", True),
        ("notion_api_called", 0),
        ("notion_live_read_enabled", _MISSING),
        ("notion_live_read_enabled", True),
        ("notion_live_read_enabled", "false"),
        ("notion_live_read_called", _MISSING),
        ("notion_live_read_called", True),
        ("notion_live_read_called", 0),
        ("schema_version", _MISSING),
        ("schema_version", ""),
        ("schema_version", "other.v1"),
        ("summary", []),
        ("stage_counts", []),
        ("stages", {}),
        ("operator_summary", []),
    ],
)
def test_actual_producer_payload_mutations_fail_closed(
    actual_payload: dict[str, object],
    field: str,
    value: object,
) -> None:
    payload = deepcopy(actual_payload)
    if value is _MISSING:
        payload.pop(field)
    else:
        payload[field] = value
    assert runbook_stage_e_evidence.validate_final_status_payload(payload, _state())


def test_unofficial_runner_result_cannot_hide_failed_overall_status(actual_payload: dict[str, object]) -> None:
    payload = deepcopy(actual_payload)
    payload["runner_result"] = "PASS"
    payload["overall_status"] = "FAILED"
    assert runbook_stage_e_evidence.validate_final_status_payload(payload, _state())


def test_wrapper_pass_cannot_hide_failed_raw_payload(tmp_path: Path, actual_payload: dict[str, object]) -> None:
    payload = deepcopy(actual_payload)
    payload["overall_status"] = "FAILED"
    state = _store_wrapper(tmp_path / "workspace", payload)
    result = runbook_stage_e_evidence.validate_stored_final_status(tmp_path / "workspace", state)
    assert result["valid"] is False
    assert any("overall_status" in blocker for blocker in result["blockers"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("terminal", _MISSING),
        ("terminal", False),
        ("terminal", "true"),
        ("terminal", 1),
        ("needs_attention", _MISSING),
        ("needs_attention", True),
        ("needs_attention", 0),
    ],
)
def test_terminal_summary_mutations_fail_closed(
    actual_payload: dict[str, object],
    field: str,
    value: object,
) -> None:
    payload = deepcopy(actual_payload)
    summary = payload["summary"]
    assert isinstance(summary, dict)
    if value is _MISSING:
        summary.pop(field)
    else:
        summary[field] = value
    assert runbook_stage_e_evidence.validate_final_status_payload(payload, _state())


def test_terminal_payload_with_next_command_fails_closed(actual_payload: dict[str, object]) -> None:
    payload = deepcopy(actual_payload)
    payload["next_command"] = "python scripts\\paper.py review"
    assert runbook_stage_e_evidence.validate_final_status_payload(payload, _state())


def test_rollover_accepts_actual_producer_wrapper_without_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    actual_payload: dict[str, object],
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    monkeypatch.setattr(rollover_fixtures, "ACCOUNT_ID", ACCOUNT_ID)
    monkeypatch.setattr(
        rollover_core,
        "build_paper_account_paths",
        lambda account_id, create=False: type("Paths", (), {"root": account_root})(),
    )
    state_path = rollover_fixtures._complete_state(workspace, DATA_DATE, TRADE_DATE)
    state = runbook_state.load_state(state_path)
    final_path = workspace / state.artifacts["final_status_report_json"]
    wrapper = json.loads(final_path.read_text(encoding="utf-8"))
    wrapper["raw_payload"] = actual_payload
    _write_json(final_path, wrapper)
    before = {path: path.read_bytes() for path in workspace.rglob("*") if path.is_file()}

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "PASS"
    assert result["safe_to_prepare"] is True
    assert {path: path.read_bytes() for path in workspace.rglob("*") if path.is_file()} == before
