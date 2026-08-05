from __future__ import annotations

import csv
from contextlib import redirect_stdout
from dataclasses import replace
import io
import json
from pathlib import Path

import pytest

from core import runbook_day_rollover as rollover_core
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_execution_intent import build_execution_intent
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS
from core.runbook_calendar import load_market_calendar
from scripts import paper_daily_ops
from scripts import runbook_command_registry
from scripts import runbook_completion_evidence
from scripts import runbook_result
from scripts import runbook_stage_e_evidence
from scripts import runbook_stage_runner
from scripts import runbook_state
from tests import test_runbook_day_rollover as rollover_fixtures
from tests import test_runbook_stage_e_evidence as standard_fixtures


ACCOUNT_ID = rollover_fixtures.ACCOUNT_ID
DATA_DATE = "2026-07-01"
TRADE_DATE = "2026-07-02"


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _completed_standard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = rollover_fixtures._complete_state(workspace, DATA_DATE, TRADE_DATE)
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    monkeypatch.setattr(
        rollover_core,
        "build_paper_account_paths",
        lambda account_id, create=False: type("Paths", (), {"root": account_root})(),
    )
    return workspace, account_root, state_path


def _assert_all_downstream_blocked(workspace: Path, account_root: Path, state: runbook_state.RunbookState) -> None:
    assert runbook_stage_e_evidence.validate_stored_final_status(workspace, state, account_root)["valid"] is False
    assert runbook_stage_e_evidence.validate_stage_e_completion_evidence(workspace, state, account_root)["valid"] is False
    assert runbook_stage_runner._stage_f_precondition_error(state, workspace, account_root) == "stage_e_completion_evidence_invalid"
    rollover = rollover_core.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )
    assert rollover["runner_result"] == "BLOCKED"


@pytest.mark.parametrize(
    ("source", "operation"),
    [
        ("account_plan", "change"),
        ("account_plan", "delete"),
        ("workspace_plan", "change"),
        ("workspace_plan", "delete"),
        ("execution", "change"),
        ("execution", "delete_rows"),
        ("review", "change"),
        ("review", "delete_rows"),
        ("account_snapshot", "change"),
        ("account_snapshot", "delete_rows"),
        ("position_snapshot", "change"),
        ("position_snapshot", "delete_rows"),
        ("eod", "change"),
        ("eod", "delete"),
    ],
)
def test_same_date_source_mutation_blocks_stored_stage_f_and_rollover(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    operation: str,
) -> None:
    workspace, account_root, state_path = _completed_standard(tmp_path, monkeypatch)
    state = runbook_state.load_state(state_path)
    paths = {
        "account_plan": account_root / "daily_action_plan_20260702.json",
        "workspace_plan": workspace / state.artifacts["daily_plan_json"],
        "execution": account_root / "paper_execution_log.csv",
        "review": account_root / "reviews" / "paper_manual_review_log.csv",
        "account_snapshot": account_root / "paper_account_snapshot.csv",
        "position_snapshot": account_root / "paper_position_snapshot.csv",
        "eod": workspace / state.artifacts["eod_commit_report_json"],
    }
    path = paths[source]
    if operation == "delete":
        path.unlink()
    elif operation == "change" and source in {"account_plan", "workspace_plan"}:
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    elif operation == "change" and source == "eod":
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["status"] = "FAILED"
        path.write_text(json.dumps(payload), encoding="utf-8")
    else:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            columns = list(reader.fieldnames or [])
            rows = list(reader)
        if operation == "delete_rows":
            rows = [row for row in rows if TRADE_DATE not in row.values()]
        else:
            rows[0][columns[-1]] = str(rows[0].get(columns[-1]) or "") + "mutated"
        _write_csv(path, columns, rows)
    _assert_all_downstream_blocked(workspace, account_root, state)


@pytest.mark.parametrize(
    ("relative_path", "date_field", "row"),
    [
        ("paper_execution_log.csv", "date", {"symbol": "MSFT", "status": "COMMITTED"}),
        (
            "reviews/paper_manual_review_log.csv",
            "review_date",
            {
                "symbol": "MSFT", "question_id": "Q2", "question_text": "future review",
                "is_actionable": "false", "manual_answer": "done", "review_status": "reviewed",
                "follow_up_needed": "false",
            },
        ),
        ("paper_account_snapshot.csv", "snapshot_date", {"account_id": ACCOUNT_ID}),
        ("paper_position_snapshot.csv", "snapshot_date", {"account_id": ACCOUNT_ID, "symbol": "MSFT", "shares": 1}),
    ],
)
def test_later_date_append_preserves_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    relative_path: str,
    date_field: str,
    row: dict[str, object],
) -> None:
    workspace, account_root, state_path = _completed_standard(tmp_path, monkeypatch)
    state = runbook_state.load_state(state_path)
    path = account_root / relative_path
    with path.open("r", encoding="utf-8", newline="") as handle:
        columns = list(csv.DictReader(handle).fieldnames or [])
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writerow({date_field: "2026-07-06", **row})
    assert runbook_stage_e_evidence.validate_stage_e_completion_evidence(workspace, state, account_root)["valid"] is True
    assert runbook_stage_runner._stage_f_precondition_error(state, workspace, account_root) is None
    assert rollover_core.preview_rollover(
        workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True
    )["runner_result"] == "PASS"


def test_manifest_artifact_mismatch_and_missing_manifest_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace, account_root, state_path = _completed_standard(tmp_path, monkeypatch)
    state = runbook_state.load_state(state_path)
    manifest_path = workspace / state.artifacts["completion_manifest_json"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["sources"]["execution_ledger"]["record_count"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    _assert_all_downstream_blocked(workspace, account_root, state)

    artifacts = dict(state.artifacts)
    artifacts.pop("completion_manifest_json")
    missing = replace(state, artifacts=artifacts)
    result = runbook_stage_e_evidence.validate_stored_final_status(workspace, missing, account_root)
    assert result["valid"] is False
    assert any("completion_manifest_required" in blocker or "completion_manifest_json" in blocker for blocker in result["blockers"])


def test_actual_standard_cli_wrapper_manifest_and_stored_validator(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    account_root, legacy_root = standard_fixtures._build_terminal_account(tmp_path)
    items = [{"symbol": "AAPL", "action": "BUY", "quantity": 1}]
    plan = {
        "schema_version": "paper_daily_plan.v1", "account_id": standard_fixtures.ACCOUNT_ID,
        "data_date": standard_fixtures.DATA_DATE, "trade_date": standard_fixtures.TRADE_DATE,
        "plan_date": standard_fixtures.TRADE_DATE, "run_mode": "official", "official_run": True,
        "generated_at": "2026-06-05T18:00:00+09:00", "fingerprints": {},
        "items": items, "execution_intent": build_execution_intent(items),
    }
    account_plan = account_root / "daily_action_plan_20260608.json"
    account_plan.write_text(json.dumps(plan), encoding="utf-8")
    _write_csv(account_root / "paper_account_snapshot.csv", PAPER_ACCOUNT_SNAPSHOT_COLUMNS, [{"account_id": standard_fixtures.ACCOUNT_ID, "snapshot_date": standard_fixtures.TRADE_DATE, "position_count": 1}])
    _write_csv(account_root / "paper_position_snapshot.csv", PAPER_POSITION_SNAPSHOT_COLUMNS, [{"account_id": standard_fixtures.ACCOUNT_ID, "snapshot_date": standard_fixtures.TRADE_DATE, "symbol": "AAPL", "shares": 1}])
    _write_csv(account_root / "paper_execution_log.csv", PAPER_EXECUTION_LOG_COLUMNS, [{"date": standard_fixtures.TRADE_DATE, "symbol": "AAPL", "status": "COMMITTED"}])
    review_row = {"review_date": standard_fixtures.TRADE_DATE, "symbol": "AAPL", "question_id": "Q1", "question_text": "review", "is_actionable": "false", "manual_answer": "done", "review_status": "reviewed", "follow_up_needed": "false"}
    _write_csv(account_root / "reviews" / "paper_manual_review_log_template.csv", PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS, [review_row])
    _write_csv(account_root / "reviews" / "paper_manual_review_log.csv", PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS, [review_row])

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = runbook_state.create_initial_state(standard_fixtures.ACCOUNT_ID, standard_fixtures.DATA_DATE, standard_fixtures.TRADE_DATE)
    state = runbook_state.complete_stage(state, "D")
    workspace_plan = workspace / "artifacts" / state.runbook_day_id / "daily_plan.json"
    workspace_plan.parent.mkdir(parents=True, exist_ok=True)
    workspace_plan.write_bytes(account_plan.read_bytes())
    state = runbook_state.record_artifact(state, "daily_plan_json", str(workspace_plan), workspace)
    eod = workspace / "artifacts" / state.runbook_day_id / "stage_e" / "eod.json"
    eod.parent.mkdir(parents=True, exist_ok=True)
    eod.write_text(json.dumps({
        "runner_result": "PASS", "status": "COMMITTED", "mode": "commit",
        "account_id": standard_fixtures.ACCOUNT_ID, "date": standard_fixtures.TRADE_DATE,
        "trade_date": standard_fixtures.TRADE_DATE, "failed_count": 0, "blocked_count": 0,
        "current_state_written": True, "account_snapshot_written": True,
        "position_snapshot_written": True, "market_valuation_status": "success",
    }), encoding="utf-8")
    state = runbook_state.record_artifact(state, "eod_commit_report_json", str(eod), workspace)
    state_path = runbook_state.get_state_path_for_context(
        workspace, standard_fixtures.ACCOUNT_ID, standard_fixtures.DATA_DATE, standard_fixtures.TRADE_DATE
    )
    runbook_state.save_state(state, state_path)

    exit_code = paper_daily_ops.main([
        "status", "--account-id", standard_fixtures.ACCOUNT_ID,
        "--data-date", standard_fixtures.DATA_DATE, "--trade-date", standard_fixtures.TRADE_DATE,
        "--account-root", str(account_root), "--legacy-root", str(legacy_root),
        "--runbook-workspace", str(workspace), "--runbook-state-json", state_path.relative_to(workspace).as_posix(), "--json",
    ])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["completion_mode"] == "STANDARD"
    assert payload["completion_proof"] is None
    assert payload["completion_manifest"]["schema_version"] == runbook_completion_evidence.MANIFEST_SCHEMA_VERSION
    assert runbook_stage_e_evidence.validate_final_status_payload(payload, state, workspace, account_root) == []

    wrapper = runbook_result.create_command_result(
        state, runbook_command_registry.get_command("final_status"), "PASS", "PASS",
        raw_payload=payload, process={"executed": True, "exit_code": 0, "duration_ms": 1}, workspace=workspace,
    )
    wrapper_path = workspace / "command_runs" / state.runbook_day_id / "final_status.json"
    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper_path.write_text(json.dumps(wrapper), encoding="utf-8")
    manifest_path = workspace / "completion_manifests" / f"{state.runbook_day_id}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload["completion_manifest"]), encoding="utf-8")
    state = runbook_state.record_artifact(state, "final_status_report_json", str(wrapper_path), workspace)
    state = runbook_state.record_artifact(state, "completion_manifest_json", str(manifest_path), workspace)
    assert runbook_stage_e_evidence.validate_stored_final_status(workspace, state, account_root)["valid"] is True


def test_workspace_ref_path_matrix_and_stable_reasons(tmp_path: Path) -> None:
    workspace = (tmp_path / "workspace").resolve()
    target = workspace / "runbook_states" / "state.json"
    target.parent.mkdir(parents=True)
    target.write_text("{}", encoding="utf-8")
    assert runbook_completion_evidence.resolve_workspace_ref(workspace, target) == target
    assert runbook_completion_evidence.resolve_workspace_ref(workspace, "runbook_states/state.json") == target
    assert runbook_completion_evidence.resolve_workspace_ref(workspace, "runbook_states\\state.json") == target
    with pytest.raises(runbook_completion_evidence.CompletionEvidenceError, match="workspace_ref_required"):
        runbook_completion_evidence.resolve_workspace_ref(workspace, "")
    with pytest.raises(runbook_completion_evidence.CompletionEvidenceError, match="workspace_ref_missing"):
        runbook_completion_evidence.resolve_workspace_ref(workspace, "missing.json")
    with pytest.raises(runbook_completion_evidence.CompletionEvidenceError, match="workspace_ref_outside_workspace"):
        runbook_completion_evidence.resolve_workspace_ref(workspace, tmp_path / "outside.json")
    with pytest.raises(runbook_completion_evidence.CompletionEvidenceError, match="workspace_ref_not_file"):
        runbook_completion_evidence.resolve_workspace_ref(workspace, "runbook_states")


@pytest.mark.parametrize("artifact_name", runbook_completion_evidence.NO_ACTION_ARTIFACT_KEYS)
def test_all_no_action_write_artifact_aliases_are_contradictions(artifact_name: str) -> None:
    state = runbook_state.create_initial_state("paper_no_action", DATA_DATE, TRADE_DATE)
    state = replace(state, artifacts={artifact_name: "command_runs/write.json"})
    with pytest.raises(
        runbook_completion_evidence.CompletionEvidenceError,
        match="no_action_write_artifact_present",
    ):
        runbook_completion_evidence.validate_no_action_contradictions(state)


@pytest.mark.parametrize("command_key", sorted(runbook_completion_evidence.NO_ACTION_WRITE_COMMAND_KEYS))
@pytest.mark.parametrize("status", sorted(runbook_state.ALLOWED_IDEMPOTENCY_STATUSES))
def test_all_no_action_write_idempotency_statuses_are_contradictions(
    command_key: str, status: str
) -> None:
    state = runbook_state.create_initial_state("paper_no_action", DATA_DATE, TRADE_DATE)
    record = {
        "idempotency_key": "key",
        "command_key": command_key,
        "step_id": 14,
        "stage_id": "D",
        "status": status,
        "created_at": "2026-07-02T18:00:00+09:00",
        "updated_at": "2026-07-02T18:00:00+09:00",
        "artifact_refs": {},
        "result_ref": None,
        "notes": None,
    }
    state = replace(state, idempotency_records={"key": record})
    with pytest.raises(
        runbook_completion_evidence.CompletionEvidenceError,
        match="no_action_write_idempotency_present",
    ):
        runbook_completion_evidence.validate_no_action_contradictions(state)
