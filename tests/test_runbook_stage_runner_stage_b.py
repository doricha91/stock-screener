from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import runbook_stage_runner
from scripts import runbook_state


ACCOUNT_ID = "paper_A"
DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"


def _seed_gate1_pass_state(workspace: Path, account_id: str = ACCOUNT_ID) -> Path:
    state = runbook_state.create_initial_state(account_id, DATA_DATE, TRADE_DATE)
    state = runbook_state.complete_stage(state, "A")
    state = runbook_state.complete_stage(state, "GATE1")
    state_path = runbook_state.get_state_path_for_context(workspace, account_id, DATA_DATE, TRADE_DATE)
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
