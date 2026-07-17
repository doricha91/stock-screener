from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from core.paper_execution_intent import build_execution_intent
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.runbook_calendar import load_market_calendar
from core.runbook_day_rollover import preview_rollover
from scripts import runbook_stage_runner, runbook_state
from scripts.runbook_no_action import sha256_file


ACCOUNT_ID = "paper_no_action"
DATA_DATE = "2026-07-01"
TRADE_DATE = "2026-07-02"


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _seed_no_action_gate2_pass(workspace: Path) -> runbook_state.RunbookState:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    for stage_id in ("A", "GATE1", "B", "C"):
        state = runbook_state.complete_stage(state, stage_id)
    state = runbook_state.complete_step(state, 12, "GATE2")
    state = runbook_state.complete_stage(state, "GATE2")
    items: list[dict] = []
    daily_plan = Path(
        _write_json(
            workspace / "artifacts" / state.runbook_day_id / "daily_plan.json",
            {
                "schema_version": "paper_daily_plan.v1",
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
                "plan_date": TRADE_DATE,
                "run_mode": "official",
                "official_run": True,
                "generated_at": f"{TRADE_DATE}T00:00:00Z",
                "items": items,
                "execution_intent": build_execution_intent(items),
                "fingerprints": {},
            },
        )
    )
    state = runbook_state.record_artifact(state, "daily_plan_json", str(daily_plan), workspace)
    gate1 = _write_json(workspace / "gate_runs" / state.runbook_day_id / "gate1.json", {"runner_result": "PASS"})
    state = runbook_state.record_artifact(state, "gate1_readiness_json", gate1, workspace)
    no_action = _write_json(
        workspace / "no_action_runs" / state.runbook_day_id / "stage_b.json",
        {
            "schema_version": "stage_b_no_action.v1",
            "runner_result": "PASS",
            "runbook_day_id": state.runbook_day_id,
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "action_mode": "NO_ACTION",
            "execution_required": False,
            "candidate_execution_count": 0,
            "manual_execution_row_count": 0,
            "daily_plan_json": state.artifacts["daily_plan_json"],
            "daily_plan_sha256": sha256_file(daily_plan),
            "gate1_readiness_json": state.artifacts["gate1_readiness_json"],
            "skipped_command_keys": [
                "execution_preview",
                "execution_reconciliation_preview",
                "execution_commit",
                "sync_execution_status",
            ],
            "ledger_write_performed": False,
            "notion_write_performed": False,
            "idempotency_record_created": False,
        },
    )
    verification = _write_json(
        workspace / "verification_runs" / state.runbook_day_id / "stage_b.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": "PASS",
            "runbook_day_id": state.runbook_day_id,
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "action_mode": "NO_ACTION",
            "verified_no_action": True,
            "committed_row_count": 0,
            "updated_count": 0,
            "failed_count": 0,
        },
    )
    stage_c = _write_json(
        workspace / "stage_runs" / state.runbook_day_id / "stage_c.json",
        {
            "schema_version": "runbook_stage_summary.v1",
            "runner_result": "PASS",
            "stage_id": "C",
            "runbook_day_id": state.runbook_day_id,
            "frozen_context": {"account_id": ACCOUNT_ID, "data_date": DATA_DATE, "trade_date": TRADE_DATE},
            "raw_payload": {"action_mode": "NO_ACTION", "verified_no_action": True},
        },
    )
    template = workspace / "artifacts" / state.runbook_day_id / "review_prep" / "template.csv"
    template.parent.mkdir(parents=True, exist_ok=True)
    with template.open("w", encoding="utf-8-sig", newline="") as handle:
        csv.DictWriter(handle, fieldnames=PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS).writeheader()
    gate2 = _write_json(
        workspace / "gate_runs" / state.runbook_day_id / "gate2.json",
        {
            "schema_version": "gate2_review_readiness.v1",
            "runner_result": "PASS",
            "action_mode": "NO_ACTION",
            "review_required": False,
            "manual_review_row_count": 0,
            "frozen_context": {"account_id": ACCOUNT_ID, "data_date": DATA_DATE, "trade_date": TRADE_DATE},
        },
    )
    for key, value in (
        ("stage_b_no_action_json", no_action),
        ("stage_b_verification_json", verification),
        ("stage_c_summary_json", stage_c),
        ("manual_review_template_csv", str(template)),
        ("gate2_readiness_json", gate2),
    ):
        state = runbook_state.record_artifact(state, key, value, workspace)
    path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, path)
    return state


def _assert_append_blocked_without_progress(
    workspace: Path,
    monkeypatch,
    *,
    expected_reason: str,
) -> dict:
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    before = runbook_state.load_state(state_path)
    calls: list = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", lambda *args: calls.append(args))

    result = runbook_stage_runner.run_stage_d_append(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    after = runbook_state.load_state(state_path)
    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == expected_reason
    assert result["action_mode"] == "NO_ACTION"
    assert result["verified_no_action"] is False
    assert calls == []
    assert after.last_completed_step == before.last_completed_step
    assert after.stage_status.get("D") != "PASS"
    assert after.idempotency_records == before.idempotency_records
    assert "review_append_report_json" not in after.artifacts
    assert "review_status_sync_report_json" not in after.artifacts
    return result


def _complete_no_action_stage_d(workspace: Path) -> runbook_state.RunbookState:
    _seed_no_action_gate2_pass(workspace)
    preview = runbook_stage_runner.run_stage_d_preview(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    append = runbook_stage_runner.run_stage_d_append(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    assert preview["runner_result"] == "PASS"
    assert append["runner_result"] == "PASS"
    return runbook_state.load_state(
        runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    )


def _fake_no_action_stage_e_run(
    output_root: Path,
    calls: list[list[str]],
    *,
    position_count: int,
    final_status: str = "PASS",
):
    def fake_run(argv, cwd, timeout_sec):
        calls.append(list(argv))
        joined = " ".join(argv)
        reports = output_root / "reports"
        reports.mkdir(parents=True, exist_ok=True)
        if "paper.py" in joined and "eod" in argv and "--dry-run" in argv:
            json_path = reports / "paper_eod_dryrun_20260702.json"
            markdown_path = reports / "paper_eod_dryrun_20260702.md"
            payload = {
                "runner_result": "PASS",
                "status": "PASS",
                "mode": "dry_run",
                "account_id": ACCOUNT_ID,
                "date": TRADE_DATE,
                "trade_date": TRADE_DATE,
                "fail_count": 0,
                "failed_count": 0,
                "blocked_count": 0,
                "commit_allowed": True,
                "would_write_current_state": True,
                "would_write_account_snapshot": True,
                "would_write_position_snapshot": True,
                "position_count": position_count,
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            }
            json_path.write_text(json.dumps(payload), encoding="utf-8")
            markdown_path.write_text("# dry-run\n", encoding="utf-8")
        elif "paper.py" in joined and "eod" in argv and "--commit" in argv:
            json_path = reports / "paper_eod_commit_20260702.json"
            markdown_path = reports / "paper_eod_commit_20260702.md"
            current_state = output_root / "paper_current_state_20260702.json"
            account_snapshot = output_root / "paper_account_snapshot.csv"
            position_snapshot = output_root / "paper_position_snapshot.csv"
            current_state.write_text(json.dumps({"positions": {}}), encoding="utf-8")
            account_snapshot.write_text("snapshot_date,position_count\n2026-07-02,%s\n" % position_count, encoding="utf-8")
            position_snapshot.write_text("snapshot_date,symbol,shares\n", encoding="utf-8")
            payload = {
                "runner_result": "PASS",
                "status": "COMMITTED",
                "mode": "commit",
                "account_id": ACCOUNT_ID,
                "date": TRADE_DATE,
                "trade_date": TRADE_DATE,
                "failed_count": 0,
                "blocked_count": 0,
                "current_state_written": True,
                "account_snapshot_written": True,
                "position_snapshot_written": True,
                "market_valuation_status": "success",
                "position_count": position_count,
                "json_path": str(json_path),
                "markdown_path": str(markdown_path),
            }
            json_path.write_text(json.dumps(payload), encoding="utf-8")
            markdown_path.write_text("# commit\n", encoding="utf-8")
        elif "paper_daily_ops.py" in joined and "status" in argv:
            payload = {
                "overall_status": final_status,
                "account_id": ACCOUNT_ID,
                "trade_date": TRADE_DATE,
                "unresolved_error_count": 0 if final_status == "PASS" else 1,
            }
        else:
            raise AssertionError(f"unexpected Stage E command: {argv}")
        return {"exit_code": 0, "duration_ms": 10, "stdout": json.dumps(payload), "stderr": ""}

    return fake_run


def _assert_stage_e_blocked_without_progress(
    workspace: Path,
    monkeypatch,
    *,
    expected_reason: str,
) -> None:
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    before = runbook_state.load_state(state_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", lambda *args: calls.append(list(args)))

    result = runbook_stage_runner.run_stage_e(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    after = runbook_state.load_state(state_path)
    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == expected_reason
    assert calls == []
    assert after.last_completed_step == before.last_completed_step
    assert after.stage_status.get("E") != "PASS"
    assert after.idempotency_records == before.idempotency_records
    assert "eod_dryrun_report_json" not in after.artifacts
    assert "eod_commit_report_json" not in after.artifacts


def test_no_action_stage_d_preview_skips_subprocess_and_pins_evidence(tmp_path: Path, monkeypatch) -> None:
    state = _seed_no_action_gate2_pass(tmp_path)
    calls: list = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", lambda *args: calls.append(args))

    result = runbook_stage_runner.run_stage_d_preview(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert result["runner_result"] == "PASS"
    assert calls == []
    command = json.loads((tmp_path / result["command_results"][0]).read_text(encoding="utf-8"))
    assert command["runner_result"] == "SKIPPED"
    assert command["process"] == {"executed": False, "exit_code": None, "duration_ms": None}
    loaded = runbook_state.load_state(runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert loaded.last_completed_step == 13
    assert loaded.artifacts["stage_d_no_action_preview_json"]
    assert "review_preview_json" not in loaded.artifacts
    evidence = json.loads((tmp_path / loaded.artifacts["stage_d_no_action_preview_json"]).read_text(encoding="utf-8"))
    assert evidence["schema_version"] == "stage_d_no_action_preview.v1"
    assert evidence["candidate_count"] == 0
    assert evidence["review_preview_executed"] is False


def test_no_action_stage_d_append_skips_writes_and_completes_stage(tmp_path: Path, monkeypatch) -> None:
    _seed_no_action_gate2_pass(tmp_path)
    runbook_stage_runner.run_stage_d_preview(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True)
    calls: list = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", lambda *args: calls.append(args))

    result = runbook_stage_runner.run_stage_d_append(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert result["runner_result"] == "PASS"
    assert calls == []
    commands = [json.loads((tmp_path / ref).read_text(encoding="utf-8")) for ref in result["command_results"]]
    assert [item["runner_result"] for item in commands] == ["SKIPPED", "SKIPPED"]
    assert all(item["process"]["executed"] is False for item in commands)
    loaded = runbook_state.load_state(Path(result["state_path"]))
    assert loaded.stage_status["D"] == "PASS"
    assert loaded.last_completed_step == 15
    assert loaded.last_completed_stage == "D"
    assert loaded.idempotency_records == {}
    assert "review_append_report_json" not in loaded.artifacts
    assert "review_status_sync_report_json" not in loaded.artifacts
    evidence = json.loads((tmp_path / loaded.artifacts["stage_d_no_action_json"]).read_text(encoding="utf-8"))
    assert evidence["schema_version"] == "stage_d_no_action.v1"
    assert evidence["review_append_executed"] is False
    assert evidence["review_sync_executed"] is False
    assert evidence["idempotency_created"] is False


def test_no_action_stage_d_append_before_preview_is_blocked(tmp_path: Path, monkeypatch) -> None:
    _seed_no_action_gate2_pass(tmp_path)

    _assert_append_blocked_without_progress(
        tmp_path, monkeypatch, expected_reason="stage_d_no_action_preview_required"
    )


def test_no_action_stage_d_append_without_preview_artifact_ref_is_blocked(tmp_path: Path, monkeypatch) -> None:
    _seed_no_action_gate2_pass(tmp_path)
    runbook_stage_runner.run_stage_d_preview(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.load_state(state_path)
    state.artifacts.pop("stage_d_no_action_preview_json")
    runbook_state.save_state(state, state_path)

    _assert_append_blocked_without_progress(
        tmp_path, monkeypatch, expected_reason="stage_d_no_action_preview_required"
    )


def test_no_action_stage_d_append_with_deleted_preview_file_is_blocked(tmp_path: Path, monkeypatch) -> None:
    _seed_no_action_gate2_pass(tmp_path)
    runbook_stage_runner.run_stage_d_preview(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.load_state(state_path)
    (tmp_path / state.artifacts["stage_d_no_action_preview_json"]).unlink()

    _assert_append_blocked_without_progress(
        tmp_path, monkeypatch, expected_reason="stage_d_no_action_preview_required"
    )


def test_no_action_stage_d_append_with_malformed_preview_is_blocked(tmp_path: Path, monkeypatch) -> None:
    _seed_no_action_gate2_pass(tmp_path)
    runbook_stage_runner.run_stage_d_preview(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.load_state(state_path)
    (tmp_path / state.artifacts["stage_d_no_action_preview_json"]).write_text("{invalid", encoding="utf-8")

    _assert_append_blocked_without_progress(
        tmp_path, monkeypatch, expected_reason="stage_d_no_action_preview_invalid"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "stage_d_no_action_preview.v0"),
        ("account_id", "other_account"),
        ("data_date", "2026-06-30"),
        ("trade_date", "2026-07-03"),
        ("runbook_day_id", "other_runbook_day"),
        ("action_mode", "EXECUTION"),
        ("verified_no_action", False),
    ],
)
def test_no_action_stage_d_append_with_invalid_preview_context_is_blocked(
    tmp_path: Path, monkeypatch, field: str, value
) -> None:
    _seed_no_action_gate2_pass(tmp_path)
    runbook_stage_runner.run_stage_d_preview(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True)
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.load_state(state_path)
    preview_path = tmp_path / state.artifacts["stage_d_no_action_preview_json"]
    payload = json.loads(preview_path.read_text(encoding="utf-8"))
    payload[field] = value
    preview_path.write_text(json.dumps(payload), encoding="utf-8")

    _assert_append_blocked_without_progress(
        tmp_path, monkeypatch, expected_reason="no_action_evidence_mismatch"
    )


def test_no_action_stage_d_append_with_daily_plan_hash_mismatch_is_blocked(tmp_path: Path, monkeypatch) -> None:
    state = _seed_no_action_gate2_pass(tmp_path)
    runbook_stage_runner.run_stage_d_preview(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True)
    daily_plan_path = tmp_path / state.artifacts["daily_plan_json"]
    payload = json.loads(daily_plan_path.read_text(encoding="utf-8"))
    payload["generated_at"] = f"{TRADE_DATE}T01:00:00Z"
    daily_plan_path.write_text(json.dumps(payload), encoding="utf-8")

    _assert_append_blocked_without_progress(
        tmp_path, monkeypatch, expected_reason="no_action_evidence_mismatch"
    )


def test_no_action_stage_d_blocks_unexpected_review_artifact(tmp_path: Path) -> None:
    state = _seed_no_action_gate2_pass(tmp_path)
    artifact = _write_json(tmp_path / "unexpected.json", {"candidate_count": 1})
    state = runbook_state.record_artifact(state, "review_preview_json", artifact, tmp_path)
    runbook_state.save_state(state, runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE))

    result = runbook_stage_runner.run_stage_d_preview(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "unexpected_review_artifact_for_no_action"


def test_no_action_stage_d_blocks_unexpected_review_idempotency(tmp_path: Path) -> None:
    state = _seed_no_action_gate2_pass(tmp_path)
    state, key = runbook_state.reserve_idempotency(state, "review_append", 14, "D", workspace=tmp_path)
    state = runbook_state.mark_idempotency_running(state, key)
    runbook_state.save_state(state, runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE))

    result = runbook_stage_runner.run_stage_d_preview(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "unexpected_review_idempotency_for_no_action"


def test_no_action_stage_d_blocks_hash_mismatch(tmp_path: Path) -> None:
    state = _seed_no_action_gate2_pass(tmp_path)
    path = tmp_path / state.artifacts["daily_plan_json"]
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["generated_at"] = f"{TRADE_DATE}T01:00:00Z"
    path.write_text(json.dumps(payload), encoding="utf-8")

    result = runbook_stage_runner.run_stage_d_preview(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "daily_plan_hash_mismatch"


def test_no_action_stage_d_reruns_are_safely_blocked(tmp_path: Path) -> None:
    _seed_no_action_gate2_pass(tmp_path)
    first_preview = runbook_stage_runner.run_stage_d_preview(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    second_preview = runbook_stage_runner.run_stage_d_preview(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    first_append = runbook_stage_runner.run_stage_d_append(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    second_append = runbook_stage_runner.run_stage_d_append(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert first_preview["runner_result"] == "PASS"
    assert second_preview["runner_result"] == "BLOCKED"
    assert second_preview["reason"] == "stage_d_preview_already_complete"
    assert first_append["runner_result"] == "PASS"
    assert second_append["runner_result"] == "BLOCKED"
    assert second_append["reason"] == "stage_d_already_pass"


@pytest.mark.parametrize("position_count", [0, 2])
def test_no_action_stage_e_executes_eod_and_completes_runbook_day(
    tmp_path: Path, monkeypatch, position_count: int
) -> None:
    workspace = tmp_path / "workspace"
    output_root = tmp_path / "paper_account"
    workspace.mkdir()
    _complete_no_action_stage_d(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_no_action_stage_e_run(output_root, calls, position_count=position_count),
    )

    result = runbook_stage_runner.run_stage_e(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert result["runner_result"] == "PASS"
    assert result["action_mode"] == "NO_ACTION"
    assert result["verified_no_action"] is True
    assert result["execution_count"] == 0
    assert result["review_count"] == 0
    assert result["eod_executed"] is True
    assert [item["command_key"] for item in result["rendered_commands"]] == [
        "eod_dryrun",
        "eod_commit",
        "final_status",
    ]
    assert len(calls) == 3
    assert (output_root / "paper_current_state_20260702.json").exists()
    assert (output_root / "paper_account_snapshot.csv").exists()
    assert (output_root / "paper_position_snapshot.csv").read_text(encoding="utf-8") == "snapshot_date,symbol,shares\n"
    state = runbook_state.load_state(Path(result["state_path"]))
    assert state.stage_status["E"] == "PASS"
    assert state.last_completed_step == 18
    assert state.last_completed_stage == "E"
    assert state.last_error is None

    rollover = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)
    assert rollover["runner_result"] == "PASS"
    assert rollover["previous_runbook_day_id"] == state.runbook_day_id
    assert rollover["next_data_date"] == TRADE_DATE

    rerun = runbook_stage_runner.run_stage_e(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    assert rerun["runner_result"] == "BLOCKED"
    assert rerun["reason"] == "stage_e_already_pass"
    assert len(calls) == 3


def test_no_action_stage_e_blocks_missing_stage_d_evidence(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = _complete_no_action_stage_d(workspace)
    state.artifacts.pop("stage_d_no_action_json")
    runbook_state.save_state(state, runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE))

    _assert_stage_e_blocked_without_progress(
        workspace, monkeypatch, expected_reason="stage_d_no_action_evidence_required"
    )


def test_no_action_stage_e_blocks_malformed_stage_d_evidence(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = _complete_no_action_stage_d(workspace)
    (workspace / state.artifacts["stage_d_no_action_json"]).write_text("{invalid", encoding="utf-8")

    _assert_stage_e_blocked_without_progress(
        workspace, monkeypatch, expected_reason="stage_d_no_action_evidence_invalid"
    )


def test_no_action_stage_e_blocks_daily_plan_hash_mismatch(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = _complete_no_action_stage_d(workspace)
    daily_plan_path = workspace / state.artifacts["daily_plan_json"]
    payload = json.loads(daily_plan_path.read_text(encoding="utf-8"))
    payload["generated_at"] = f"{TRADE_DATE}T01:00:00Z"
    daily_plan_path.write_text(json.dumps(payload), encoding="utf-8")

    _assert_stage_e_blocked_without_progress(
        workspace, monkeypatch, expected_reason="daily_plan_hash_mismatch"
    )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "stage_d_no_action.v0"),
        ("runbook_day_id", "other_day"),
        ("account_id", "other_account"),
        ("action_mode", "EXECUTION"),
        ("verified_no_action", False),
        ("candidate_count", 1),
        ("review_append_executed", True),
        ("idempotency_created", True),
    ],
)
def test_no_action_stage_e_blocks_invalid_stage_d_evidence(
    tmp_path: Path, monkeypatch, field: str, value
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = _complete_no_action_stage_d(workspace)
    evidence_path = workspace / state.artifacts["stage_d_no_action_json"]
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    payload[field] = value
    evidence_path.write_text(json.dumps(payload), encoding="utf-8")

    _assert_stage_e_blocked_without_progress(
        workspace, monkeypatch, expected_reason="no_action_evidence_mismatch"
    )


def test_no_action_stage_e_blocks_unexpected_review_artifact(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = _complete_no_action_stage_d(workspace)
    unexpected = _write_json(workspace / "unexpected_review.json", {"candidate_count": 1})
    state = runbook_state.record_artifact(state, "review_append_report_json", unexpected, workspace)
    runbook_state.save_state(state, runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE))

    _assert_stage_e_blocked_without_progress(
        workspace, monkeypatch, expected_reason="unexpected_review_artifact_for_no_action"
    )


def test_no_action_stage_e_blocks_unexpected_review_idempotency(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state = _complete_no_action_stage_d(workspace)
    state, key = runbook_state.reserve_idempotency(state, "review_append", 14, "D", workspace=workspace)
    state = runbook_state.mark_idempotency_running(state, key)
    runbook_state.save_state(state, runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE))

    _assert_stage_e_blocked_without_progress(
        workspace, monkeypatch, expected_reason="unexpected_review_idempotency_for_no_action"
    )


def test_no_action_stage_e_retries_final_status_without_repeating_commit(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    output_root = tmp_path / "paper_account"
    workspace.mkdir()
    _complete_no_action_stage_d(workspace)
    first_calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_no_action_stage_e_run(output_root, first_calls, position_count=0, final_status="FAILED"),
    )

    first = runbook_stage_runner.run_stage_e(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    assert first["runner_result"] == "BLOCKED"
    assert len(first_calls) == 3

    second_calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_no_action_stage_e_run(output_root, second_calls, position_count=0),
    )
    second = runbook_stage_runner.run_stage_e(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert second["runner_result"] == "PASS"
    assert second["action_mode"] == "NO_ACTION"
    assert [item["command_key"] for item in second["rendered_commands"]] == ["eod_commit", "final_status"]
    assert second["rendered_commands"][0]["argv"] == []
    assert len(second_calls) == 1
    assert "paper_daily_ops.py" in " ".join(second_calls[0])
