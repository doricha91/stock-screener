from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import runbook_stage_runner
from scripts import runbook_state
from scripts.runbook_no_action import sha256_file
from core.paper_execution_intent import build_execution_intent


ACCOUNT_ID = "paper_A"
DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"


def _seed_gate1_pass_state(workspace: Path, account_id: str = ACCOUNT_ID) -> Path:
    state = runbook_state.create_initial_state(account_id, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    items = [{"symbol": "AAPL", "action": "BUY", "quantity": 1}]
    plan_path = workspace / "daily_plan_execution.json"
    _write_plan(plan_path, account_id, items)
    state = runbook_state.record_artifact(state, "daily_plan_json", str(plan_path), workspace)
    state_path = runbook_state.get_state_path_for_context(workspace, account_id, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)
    return state_path


def _write_plan(path: Path, account_id: str, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "paper_daily_plan.v1",
                "account_id": account_id,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
                "plan_date": TRADE_DATE,
                "run_mode": "official",
                "official_run": True,
                "generated_at": "2026-06-12T12:00:00Z",
                "items": items,
                "execution_intent": build_execution_intent(items),
                "fingerprints": {"generator_version": "paper_daily_plan.v1"},
            }
        ),
        encoding="utf-8",
    )


def _seed_no_action_gate1_pass_state(workspace: Path, *, gate_action_mode: str = "NO_ACTION") -> Path:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    plan_path = workspace / "daily_plan_no_action.json"
    _write_plan(plan_path, ACCOUNT_ID, [])
    gate_path = workspace / "gate1_no_action.json"
    gate_path.write_text(
        json.dumps(
            {
                "schema_version": "runbook_gate_result.v1",
                "runner_result": "PASS",
                "gate_id": "GATE1",
                "frozen_context": {
                    "account_id": ACCOUNT_ID,
                    "data_date": DATA_DATE,
                    "trade_date": TRADE_DATE,
                },
                "action_mode": gate_action_mode,
                "execution_required": gate_action_mode != "NO_ACTION",
                "candidate_execution_count": 0,
                "manual_execution_row_count": 0,
                "daily_plan_sha256": sha256_file(plan_path),
            }
        ),
        encoding="utf-8",
    )
    state = runbook_state.record_artifact(state, "daily_plan_json", str(plan_path), workspace)
    state = runbook_state.record_artifact(state, "gate1_readiness_json", str(gate_path), workspace)
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)
    return state_path


def _fake_stage_b_run(tmp_path: Path, calls: list[list[str]]):
    preview_json = tmp_path / "manual_execution_import_preview_20260615.json"
    preview_md = tmp_path / "manual_execution_import_preview_20260615.md"
    recon_json = tmp_path / "execution_reconciliation_preview_20260615.json"
    recon_md = tmp_path / "execution_reconciliation_preview_20260615.md"
    commit_json = tmp_path / "manual_execution_import_commit_20260615.json"
    commit_md = tmp_path / "manual_execution_import_commit_20260615.md"
    sync_json = tmp_path / "manual_execution_status_sync_20260615.json"
    sync_md = tmp_path / "manual_execution_status_sync_20260615.md"

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        calls.append(argv)
        joined = " ".join(argv)
        if "import_notion_executions.py" in joined and "--preview" in argv:
            preview_json.write_text("{}", encoding="utf-8")
            preview_md.write_text("preview", encoding="utf-8")
            payload = {
                "candidate_count": 4,
                "fail_count": 0,
                "commit_allowed": "true",
                "json_path": str(preview_json),
                "markdown_path": str(preview_md),
            }
        elif "runbook_execution_reconciliation_preview.py" in joined:
            recon_json.write_text("{}", encoding="utf-8")
            recon_md.write_text("recon", encoding="utf-8")
            payload = {
                "runner_result": "PASS",
                "blocked_count": 0,
                "needs_review_count": 0,
                "warning_count": 0,
                "missing_count": 0,
                "extra_count": 0,
                "preview_json": str(recon_json),
                "preview_md": str(recon_md),
            }
        elif "import_notion_executions.py" in joined and "--commit" in argv:
            assert str(preview_json) in argv
            assert str(recon_json) in argv
            commit_json.write_text("{}", encoding="utf-8")
            commit_md.write_text("commit", encoding="utf-8")
            payload = {
                "status": "COMMITTED",
                "committed_row_count": 4,
                "current_state_written": True,
                "account_snapshot_written": True,
                "position_snapshot_written": True,
                "commit_json_path": str(commit_json),
                "commit_markdown_path": str(commit_md),
            }
        elif "sync_notion_execution_status.py" in joined:
            assert str(commit_json) in argv
            sync_json.write_text("{}", encoding="utf-8")
            sync_md.write_text("sync", encoding="utf-8")
            payload = {
                "overall_status": "SUCCESS",
                "candidate_count": 4,
                "updated_count": 4,
                "failed_count": 0,
                "sync_json_path": str(sync_json),
                "sync_markdown_path": str(sync_md),
            }
        else:
            raise AssertionError(f"unexpected argv: {argv}")
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": json.dumps(payload),
            "stderr": "",
        }

    return fake_run


def test_stage_b_dry_run_renders_step_7_7r_8_9_commands(tmp_path: Path) -> None:
    _seed_gate1_pass_state(tmp_path)

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert [item["command_key"] for item in result["rendered_commands"]] == [
        "execution_preview",
        "execution_reconciliation_preview",
        "execution_commit",
        "sync_execution_status",
    ]
    commit_argv = result["rendered_commands"][2]["argv"]
    sync_argv = result["rendered_commands"][3]["argv"]
    assert "--reconciliation-preview-json" in commit_argv
    assert any("dry_run" in part and "manual_execution_import_preview.json" in part for part in commit_argv)
    assert any("dry_run" in part and "execution_reconciliation_preview.json" in part for part in commit_argv)
    assert any("dry_run" in part and "manual_execution_import_commit.json" in part for part in sync_argv)


def test_stage_b_missing_gate1_pass_is_blocked(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state_path = runbook_state.get_state_path_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "gate1_not_pass"


def test_stage_b_reconciliation_warning_blocks_commit(tmp_path: Path, monkeypatch) -> None:
    _seed_gate1_pass_state(tmp_path)
    calls: list[list[str]] = []
    preview_json = tmp_path / "manual_execution_import_preview_20260615.json"
    recon_json = tmp_path / "execution_reconciliation_preview_20260615.json"

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        calls.append(argv)
        joined = " ".join(argv)
        if "import_notion_executions.py" in joined and "--preview" in argv:
            preview_json.write_text("{}", encoding="utf-8")
            payload = {
                "candidate_count": 4,
                "fail_count": 0,
                "commit_allowed": "true",
                "json_path": str(preview_json),
                "markdown_path": str(tmp_path / "preview.md"),
            }
        elif "runbook_execution_reconciliation_preview.py" in joined:
            recon_json.write_text("{}", encoding="utf-8")
            payload = {
                "runner_result": "WARNING",
                "blocked_count": 0,
                "needs_review_count": 0,
                "warning_count": 1,
                "missing_count": 0,
                "extra_count": 0,
                "preview_json": str(recon_json),
                "preview_md": str(tmp_path / "recon.md"),
            }
        else:
            raise AssertionError("commit must not execute after reconciliation warning")
        return {"executed": True, "exit_code": 0, "duration_ms": 1, "stdout": json.dumps(payload), "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert len(calls) == 2


def test_stage_b_import_preview_fail_count_blocks(tmp_path: Path, monkeypatch) -> None:
    _seed_gate1_pass_state(tmp_path)
    calls: list[list[str]] = []
    preview_json = tmp_path / "manual_execution_import_preview_20260615.json"

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        calls.append(argv)
        preview_json.write_text("{}", encoding="utf-8")
        payload = {
            "candidate_count": 4,
            "fail_count": 1,
            "commit_allowed": "false",
            "json_path": str(preview_json),
            "markdown_path": str(tmp_path / "preview.md"),
        }
        return {"executed": True, "exit_code": 0, "duration_ms": 1, "stdout": json.dumps(payload), "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert len(calls) == 1


def test_stage_b_success_pins_artifacts_and_completes(tmp_path: Path, monkeypatch) -> None:
    _seed_gate1_pass_state(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_b_run(tmp_path, calls))

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert len(calls) == 4
    state = runbook_state.load_state(Path(result["state_path"]))
    assert state.stage_status["B"] == "PASS"
    assert state.last_completed_step == 9
    assert state.artifacts["execution_preview_json"].endswith("manual_execution_import_preview_20260615.json")
    assert state.artifacts["execution_reconciliation_preview_json"].endswith("execution_reconciliation_preview_20260615.json")
    assert state.artifacts["execution_commit_report_json"].endswith("manual_execution_import_commit_20260615.json")
    assert state.artifacts["execution_status_sync_report"].endswith("manual_execution_status_sync_20260615.json")
    assert any(
        record.get("command_key") == "execution_commit" and record.get("status") == "PASS"
        for record in state.idempotency_records.values()
    )


def test_stage_b_no_action_skips_all_commands_and_completes(tmp_path: Path, monkeypatch) -> None:
    state_path = _seed_no_action_gate1_pass_state(tmp_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        lambda argv, cwd, timeout_sec=1800: calls.append(argv),
    )

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert result["action_mode"] == "NO_ACTION"
    assert result["ledger_write_performed"] is False
    assert result["notion_write_performed"] is False
    assert result["execution_commit_report_json"] is None
    assert result["execution_status_sync_report_json"] is None
    assert calls == []
    command_payloads = [json.loads((tmp_path / ref).read_text(encoding="utf-8")) for ref in result["command_results"]]
    assert [payload["runner_result"] for payload in command_payloads] == ["SKIPPED"] * 4
    assert all(payload["process"]["executed"] is False for payload in command_payloads)
    summary = json.loads(Path(result["stage_summary_json"]).read_text(encoding="utf-8"))
    assert summary["runner_result"] == "PASS"
    assert summary["counts"]["skipped"] == 4

    state = runbook_state.load_state(state_path)
    assert state.last_completed_step == 9
    assert state.last_completed_stage == "B"
    assert state.stage_status["B"] == "PASS"
    assert state.current_status == "PASS"
    assert state.last_error is None
    assert not state.idempotency_records
    assert "execution_commit_report_json" not in state.artifacts
    assert "execution_status_sync_report_json" not in state.artifacts
    assert "stage_b_no_action_json" in state.artifacts
    step7_events = [
        event
        for event in state.history
        if event.get("event_type") == "step_completed" and event.get("step_id") == 7
    ]
    assert len(step7_events) == 1
    evidence = json.loads((tmp_path / state.artifacts["stage_b_no_action_json"]).read_text(encoding="utf-8"))
    assert len(evidence["daily_plan_sha256"]) == 64
    assert evidence["idempotency_record_created"] is False


def test_stage_b_no_action_blocks_gate1_action_mode_mismatch(tmp_path: Path, monkeypatch) -> None:
    _seed_no_action_gate1_pass_state(tmp_path, gate_action_mode="EXECUTION")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        lambda argv, cwd, timeout_sec=1800: calls.append(argv),
    )

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "no_action_evidence_context_mismatch"
    assert calls == []


def test_stage_b_no_action_blocks_daily_plan_changed_after_gate1(tmp_path: Path, monkeypatch) -> None:
    state_path = _seed_no_action_gate1_pass_state(tmp_path)
    state = runbook_state.load_state(state_path)
    plan_path = tmp_path / state.artifacts["daily_plan_json"]
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    payload["generated_at"] = "2026-06-12T13:00:00Z"
    plan_path.write_text(json.dumps(payload), encoding="utf-8")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        lambda argv, cwd, timeout_sec=1800: calls.append(argv),
    )

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "no_action_evidence_context_mismatch"
    assert calls == []


def test_stage_b_copies_repo_output_artifacts_into_workspace(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    repo_outputs.mkdir()
    _seed_gate1_pass_state(workspace)
    calls: list[list[str]] = []
    preview_json = repo_outputs / "manual_execution_import_preview_20260615.json"
    preview_md = repo_outputs / "manual_execution_import_preview_20260615.md"
    recon_json = repo_outputs / "execution_reconciliation_preview_20260615.json"
    recon_md = repo_outputs / "execution_reconciliation_preview_20260615.md"
    commit_json = repo_outputs / "manual_execution_import_commit_20260615.json"
    commit_md = repo_outputs / "manual_execution_import_commit_20260615.md"
    sync_json = repo_outputs / "manual_execution_status_sync_20260615.json"
    sync_md = repo_outputs / "manual_execution_status_sync_20260615.md"

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        calls.append(argv)
        joined = " ".join(argv)
        if "import_notion_executions.py" in joined and "--preview" in argv:
            preview_json.write_text("{}", encoding="utf-8")
            preview_md.write_text("preview", encoding="utf-8")
            payload = {
                "candidate_count": 4,
                "fail_count": 0,
                "commit_allowed": "true",
                "json_path": str(preview_json),
                "markdown_path": str(preview_md),
            }
        elif "runbook_execution_reconciliation_preview.py" in joined:
            assert str(workspace / "artifacts" / f"{ACCOUNT_ID}_{DATA_DATE}_{TRADE_DATE}" / "stage_b" / preview_json.name) not in argv
            recon_json.write_text("{}", encoding="utf-8")
            recon_md.write_text("recon", encoding="utf-8")
            payload = {
                "runner_result": "PASS",
                "blocked_count": 0,
                "needs_review_count": 0,
                "warning_count": 0,
                "missing_count": 0,
                "extra_count": 0,
                "preview_json": str(recon_json),
                "preview_md": str(recon_md),
            }
        elif "import_notion_executions.py" in joined and "--commit" in argv:
            assert str(preview_json) not in argv
            assert str(recon_json) not in argv
            assert any("workspace" in part and preview_json.name in part for part in argv)
            assert any("workspace" in part and recon_json.name in part for part in argv)
            commit_json.write_text("{}", encoding="utf-8")
            commit_md.write_text("commit", encoding="utf-8")
            payload = {
                "status": "COMMITTED",
                "committed_row_count": 4,
                "current_state_written": True,
                "account_snapshot_written": True,
                "position_snapshot_written": True,
                "commit_json_path": str(commit_json),
                "commit_markdown_path": str(commit_md),
            }
        elif "sync_notion_execution_status.py" in joined:
            assert str(commit_json) not in argv
            assert any("workspace" in part and commit_json.name in part for part in argv)
            sync_json.write_text("{}", encoding="utf-8")
            sync_md.write_text("sync", encoding="utf-8")
            payload = {
                "overall_status": "SUCCESS",
                "candidate_count": 4,
                "updated_count": 4,
                "failed_count": 0,
                "sync_json_path": str(sync_json),
                "sync_markdown_path": str(sync_md),
            }
        else:
            raise AssertionError(f"unexpected argv: {argv}")
        return {"executed": True, "exit_code": 0, "duration_ms": 1, "stdout": json.dumps(payload), "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = runbook_stage_runner.run_stage_b(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    state = runbook_state.load_state(Path(result["state_path"]))
    for key in (
        "execution_preview_json",
        "execution_reconciliation_preview_json",
        "execution_commit_report_json",
        "execution_status_sync_report",
    ):
        assert state.artifacts[key].startswith(f"artifacts/{state.runbook_day_id}/stage_b/")
        assert (workspace / state.artifacts[key]).exists()
    command_json = next((workspace / "command_runs" / state.runbook_day_id).glob("*_007_execution_preview.json"))
    payload = json.loads(command_json.read_text(encoding="utf-8"))
    assert payload["outputs"]["artifact_refs"]["execution_preview_json"].startswith("artifacts/")


def test_stage_b_stale_running_without_commit_record_restarts(tmp_path: Path, monkeypatch) -> None:
    state_path = _seed_gate1_pass_state(tmp_path)
    state = runbook_state.load_state(state_path)
    state = runbook_state.start_stage(state, "B")
    runbook_state.save_state(state, state_path)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_b_run(tmp_path, calls))

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    loaded = runbook_state.load_state(state_path)
    assert loaded.stage_status["B"] == "PASS"
    assert any(event.get("event_type") == "stale_stage_recovered" for event in loaded.history)


def test_stage_b_stale_running_with_commit_idempotency_pass_blocks(tmp_path: Path) -> None:
    state_path = _seed_gate1_pass_state(tmp_path)
    state = runbook_state.load_state(state_path)
    state = runbook_state.start_stage(state, "B")
    state, key = runbook_state.reserve_idempotency(
        state,
        "execution_commit",
        8,
        "B",
        {"execution_preview_json": "a.json", "execution_reconciliation_preview_json": "b.json"},
        tmp_path,
    )
    state = runbook_state.mark_idempotency_pass(state, key, result_ref="commit.json")
    runbook_state.save_state(state, state_path)

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "execution_commit_already_recorded"


def test_stage_b_command_exception_does_not_leave_running_state(tmp_path: Path, monkeypatch) -> None:
    state_path = _seed_gate1_pass_state(tmp_path)

    def boom(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        raise RuntimeError("boom")

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", boom)

    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "FAILED"
    state = runbook_state.load_state(state_path)
    assert state.current_status == "FAILED"
    assert state.stage_status["B"] == "FAILED"
    assert state.last_error["reason"] == "stage_b_step_exception:execution_preview"


def test_stage_b_confirm_guard_blocks_missing_confirmation(tmp_path: Path) -> None:
    result = runbook_stage_runner.run_stage_b(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "paper_test_confirmation_required"


def test_stage_b_confirm_guard_blocks_non_paper_account(tmp_path: Path) -> None:
    result = runbook_stage_runner.run_stage_b(
        tmp_path,
        "live_account",
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "paper_account_required"


def test_cli_stage_b_dry_run_outputs_json(tmp_path: Path) -> None:
    _seed_gate1_pass_state(tmp_path, account_id="paper_cli")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_stage_runner.py",
            "stage-b",
            "--workspace",
            str(tmp_path),
            "--account-id",
            "paper_cli",
            "--data-date",
            DATA_DATE,
            "--trade-date",
            TRADE_DATE,
            "--confirm-paper-test",
            "--dry-run",
        ],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["runner_result"] == "PASS"
    assert payload["stage_id"] == "B"
    assert [item["command_key"] for item in payload["rendered_commands"]] == [
        "execution_preview",
        "execution_reconciliation_preview",
        "execution_commit",
        "sync_execution_status",
    ]
