from __future__ import annotations

import json
import csv
from dataclasses import replace
from pathlib import Path

from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_execution_intent import build_execution_intent
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_position_snapshot import PAPER_POSITION_SNAPSHOT_COLUMNS
from scripts import runbook_completion_evidence
from scripts import runbook_stage_runner
from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-07-01"
TRADE_DATE = "2026-07-02"


def _write_json(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


def _seed_stage_d_pass_state(workspace: Path, *, stage_d_pass: bool = True) -> runbook_state.RunbookState:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    for stage_id in ("A", "GATE1", "B", "C", "GATE2"):
        state = runbook_state.complete_stage(state, stage_id)
    items = [{"symbol": "AAPL", "action": "BUY", "quantity": 1}]
    daily_plan = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "daily_plan.json",
        {
            "schema_version": "paper_daily_plan.v1",
            "account_id": ACCOUNT_ID,
            "data_date": DATA_DATE,
            "trade_date": TRADE_DATE,
            "plan_date": TRADE_DATE,
            "run_mode": "official",
            "official_run": True,
            "generated_at": "2026-07-01T18:00:00+09:00",
            "fingerprints": {},
            "items": items,
            "execution_intent": build_execution_intent(items),
        },
    )
    state = runbook_state.record_artifact(state, "daily_plan_json", daily_plan, workspace)
    verification = _write_json(
        workspace / "verification_runs" / state.runbook_day_id / "latest_stage_b_verification.json",
        {
            "schema_version": "stage_b_verification.v1",
            "runner_result": "PASS",
            "committed_row_count": 5,
            "failed_count": 0,
        },
    )
    state = runbook_state.record_artifact(state, "stage_b_verification_json", verification, workspace)
    review_append = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_d" / "manual_review_import_commit_20260702.json",
        {"status": "COMMITTED", "account_id": ACCOUNT_ID, "review_date": TRADE_DATE},
    )
    review_sync = _write_json(
        workspace / "artifacts" / state.runbook_day_id / "stage_d" / "manual_review_status_sync_20260702.json",
        {"overall_status": "SUCCESS", "account_id": ACCOUNT_ID, "review_date": TRADE_DATE},
    )
    state = runbook_state.record_artifact(state, "review_append_report_json", review_append, workspace)
    state = runbook_state.record_artifact(state, "review_status_sync_report_json", review_sync, workspace)
    if stage_d_pass:
        state = runbook_state.complete_step(state, 15, "D")
        state = runbook_state.complete_stage(state, "D")
    latest_dir = workspace / "stage_runs" / state.runbook_day_id
    _write_json(latest_dir / "latest_D_PREVIEW.json", {"stage_id": "D_PREVIEW", "runner_result": "PASS"})
    _write_json(latest_dir / "latest_D.json", {"stage_id": "D", "runner_result": "PASS"})
    state_path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    runbook_state.save_state(state, state_path)
    return state


def _fake_stage_e_run(
    repo_outputs: Path,
    calls: list[list[str]],
    *,
    dryrun_runner_result: str = "PASS",
    commit_failed: bool = False,
    final_status: str = "PASS",
):
    def fake_run(argv, cwd, timeout_sec):
        calls.append(list(argv))
        compact = TRADE_DATE.replace("-", "")
        joined = " ".join(argv)
        if "paper.py" in joined and "eod" in argv and "--dry-run" in argv:
            dryrun_json = repo_outputs / "reports" / f"paper_eod_dryrun_{compact}.json"
            dryrun_md = repo_outputs / "reports" / f"paper_eod_dryrun_{compact}.md"
            dryrun_json.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "runner_result": dryrun_runner_result,
                "status": dryrun_runner_result,
                "mode": "dry_run",
                "account_id": ACCOUNT_ID,
                "date": TRADE_DATE,
                "trade_date": TRADE_DATE,
                "fail_count": 1 if dryrun_runner_result != "PASS" else 0,
                "failed_count": 1 if dryrun_runner_result != "PASS" else 0,
                "blocked_count": 0,
                "commit_allowed": dryrun_runner_result == "PASS",
                "would_write_current_state": True,
                "would_write_account_snapshot": True,
                "would_write_position_snapshot": True,
                "json_path": str(dryrun_json),
                "markdown_path": str(dryrun_md),
            }
            dryrun_json.write_text(json.dumps(payload), encoding="utf-8")
            dryrun_md.write_text("# dryrun\n", encoding="utf-8")
        elif "paper.py" in joined and "eod" in argv and "--commit" in argv:
            assert "--dryrun-json" in argv
            assert any("workspace" in part and "paper_eod_dryrun_20260702.json" in part for part in argv)
            commit_json = repo_outputs / "reports" / f"paper_eod_commit_{compact}.json"
            commit_md = repo_outputs / "reports" / f"paper_eod_commit_{compact}.md"
            commit_json.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "status": "FAILED" if commit_failed else "COMMITTED",
                "runner_result": "FAILED" if commit_failed else "PASS",
                "mode": "commit",
                "account_id": ACCOUNT_ID,
                "date": TRADE_DATE,
                "trade_date": TRADE_DATE,
                "failed_count": 1 if commit_failed else 0,
                "blocked_count": 0,
                "current_state_written": not commit_failed,
                "account_snapshot_written": not commit_failed,
                "position_snapshot_written": not commit_failed,
                "market_valuation_status": "success",
                "json_path": str(commit_json),
                "markdown_path": str(commit_md),
            }
            commit_json.write_text(json.dumps(payload), encoding="utf-8")
            commit_md.write_text("# commit\n", encoding="utf-8")
        elif "paper_daily_ops.py" in joined and "status" in argv:
            workspace = Path(argv[argv.index("--runbook-workspace") + 1])
            state_ref = argv[argv.index("--runbook-state-json") + 1]
            state = runbook_state.load_state(workspace / state_ref)
            source_plan = workspace / state.artifacts["daily_plan_json"]
            (repo_outputs / f"daily_action_plan_{TRADE_DATE.replace('-', '')}.json").parent.mkdir(parents=True, exist_ok=True)
            (repo_outputs / f"daily_action_plan_{TRADE_DATE.replace('-', '')}.json").write_bytes(source_plan.read_bytes())
            with (repo_outputs / "paper_execution_log.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
                writer.writeheader()
                writer.writerow({"date": TRADE_DATE, "symbol": "AAPL", "status": "COMMITTED"})
            reviews = repo_outputs / "reviews"
            reviews.mkdir(parents=True, exist_ok=True)
            with (reviews / "paper_manual_review_log.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS)
                writer.writeheader()
                writer.writerow({
                    "review_date": TRADE_DATE, "symbol": "AAPL", "question_id": "Q1",
                    "question_text": "review", "is_actionable": "false", "manual_answer": "done",
                    "review_status": "reviewed", "follow_up_needed": "false",
                })
            with (repo_outputs / "paper_account_snapshot.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
                writer.writeheader()
                writer.writerow({"account_id": ACCOUNT_ID, "snapshot_date": TRADE_DATE, "position_count": 1})
            with (repo_outputs / "paper_position_snapshot.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=PAPER_POSITION_SNAPSHOT_COLUMNS)
                writer.writeheader()
                writer.writerow({"account_id": ACCOUNT_ID, "snapshot_date": TRADE_DATE, "symbol": "AAPL", "shares": 1})
            payload = {
                "schema_version": "mfu_oper9_daily_ops_status.v1",
                "overall_status": final_status,
                "account_id": ACCOUNT_ID,
                "data_date": DATA_DATE,
                "trade_date": TRADE_DATE,
                "workflow_status": "REVIEW_DONE",
                "completion_mode": "STANDARD",
                "completion_proof": None,
                "account_root": str(repo_outputs),
                "read_only": True,
                "write_executed": False,
                "operation_write_executed": False,
                "notion_api_called": False,
                "notion_live_read_enabled": False,
                "notion_live_read_called": False,
                "commit_append_executed": False,
                "blockers": [],
                "warnings": [],
                "next_command": None,
                "next_action": None,
                "summary": {"terminal": True, "needs_attention": False},
                "stage_counts": {},
                "stages": [],
                "operator_summary": {},
            }
            payload["completion_manifest"] = runbook_completion_evidence.build_runbook_completion_manifest(
                workspace, state, repo_outputs
            )
        else:
            raise AssertionError(f"unexpected argv: {argv}")
        return {"exit_code": 0, "duration_ms": 10, "stdout": json.dumps(payload), "stderr": ""}

    return fake_run


def test_stage_e_success_persists_pass_and_points_to_stage_f(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    state = _seed_stage_d_pass_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_e_run(repo_outputs, calls))

    result = runbook_stage_runner.run_stage_e(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert result["next_stage"] == "F"
    assert result["next_required_action"] == "Run Stage F benchmark and Notion synchronization."
    assert [item["command_key"] for item in result["rendered_commands"]] == [
        "eod_dryrun",
        "eod_commit",
        "final_status",
    ]
    loaded = runbook_state.load_state(runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert loaded.stage_status["E"] == "PASS"
    assert loaded.stage_status["F"] == "PENDING"
    assert loaded.last_completed_step == 18
    assert loaded.last_completed_stage == "E"
    assert loaded.artifacts["eod_dryrun_report_json"].startswith(f"artifacts/{state.runbook_day_id}/stage_e/")
    assert loaded.artifacts["eod_commit_report_json"].startswith(f"artifacts/{state.runbook_day_id}/stage_e/")
    assert loaded.artifacts["final_status_report_json"].startswith("command_runs/")
    assert (workspace / "stage_runs" / state.runbook_day_id / "latest_E.json").exists()
    assert (workspace / "stage_runs" / state.runbook_day_id / "latest_D.json").exists()
    assert (workspace / "stage_runs" / state.runbook_day_id / "latest_D_PREVIEW.json").exists()
    assert all("--include-notion-read" not in argv for argv in calls)


def test_relative_workspace_renders_absolute_workspace_and_relative_state_ref(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_d_pass_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_e_run(repo_outputs, calls))
    monkeypatch.chdir(tmp_path)

    result = runbook_stage_runner.run_stage_e(
        Path("workspace"), ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert result["runner_result"] == "PASS"
    final_argv = calls[-1]
    assert Path(final_argv[final_argv.index("--runbook-workspace") + 1]).is_absolute()
    state_ref = final_argv[final_argv.index("--runbook-state-json") + 1]
    assert state_ref == f"runbook_states/{ACCOUNT_ID}_{DATA_DATE}_{TRADE_DATE}.json"
    assert "workspace/workspace" not in state_ref.replace("\\", "/")


def test_stage_e_blocks_when_stage_d_not_pass(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_stage_d_pass_state(workspace, stage_d_pass=False)

    result = runbook_stage_runner.run_stage_e(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "stage_d_required"


def test_stage_e_dryrun_failure_does_not_run_commit(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_d_pass_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_stage_e_run(repo_outputs, calls, dryrun_runner_result="FAILED"),
    )

    result = runbook_stage_runner.run_stage_e(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] in {"BLOCKED", "FAILED"}
    assert len(calls) == 1
    assert "--dry-run" in calls[0]


def test_stage_e_dryrun_missing_artifact_stops_before_commit(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _seed_stage_d_pass_state(workspace)
    calls: list[list[str]] = []

    def fake_run(argv, cwd, timeout_sec):
        calls.append(list(argv))
        payload = {
            "runner_result": "PASS",
            "status": "PASS",
            "account_id": ACCOUNT_ID,
            "date": TRADE_DATE,
            "fail_count": 0,
            "blocked_count": 0,
            "commit_allowed": True,
            "would_write_current_state": True,
            "would_write_account_snapshot": True,
            "would_write_position_snapshot": True,
            "json_path": str(tmp_path / "missing.json"),
            "markdown_path": str(tmp_path / "missing.md"),
        }
        return {"exit_code": 0, "duration_ms": 10, "stdout": json.dumps(payload), "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = runbook_stage_runner.run_stage_e(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "FAILED"
    assert len(calls) == 1


def test_stage_e_same_eod_commit_rerun_after_pass_is_blocked(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_d_pass_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_e_run(repo_outputs, calls))

    first = runbook_stage_runner.run_stage_e(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )
    second = runbook_stage_runner.run_stage_e(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert first["runner_result"] == "PASS"
    assert second["runner_result"] == "BLOCKED"
    assert second["reason"] == "stage_e_already_pass"


def test_stage_e_commit_pass_then_final_fail_retries_final_without_commit(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_d_pass_state(workspace)
    first_calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_stage_e_run(repo_outputs, first_calls, final_status="FAILED"),
    )

    first = runbook_stage_runner.run_stage_e(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert first["runner_result"] == "BLOCKED"
    second_calls: list[list[str]] = []
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", _fake_stage_e_run(repo_outputs, second_calls))

    second = runbook_stage_runner.run_stage_e(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert second["runner_result"] == "PASS"
    assert second["rendered_commands"][0]["command_key"] == "eod_commit"
    assert second["rendered_commands"][0]["argv"] == []
    assert len(second_calls) == 1
    assert "paper_daily_ops.py" in " ".join(second_calls[0])


def test_stage_e_final_status_warning_does_not_pass_stage(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    repo_outputs = tmp_path / "repo_outputs"
    workspace.mkdir()
    _seed_stage_d_pass_state(workspace)
    calls: list[list[str]] = []
    monkeypatch.setattr(
        runbook_stage_runner,
        "run_allowlisted_command",
        _fake_stage_e_run(repo_outputs, calls, final_status="WARNING"),
    )

    result = runbook_stage_runner.run_stage_e(
        workspace,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    loaded = runbook_state.load_state(runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE))
    assert loaded.stage_status["E"] != "PASS"
