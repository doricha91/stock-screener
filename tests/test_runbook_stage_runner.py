from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from scripts import runbook_command_registry as registry
from scripts import runbook_result
from scripts import runbook_stage_runner
from scripts import runbook_state


ACCOUNT_ID = "paper_A"
DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"


def test_dry_run_stage_a_creates_step_0_to_5_command_results(tmp_path: Path) -> None:
    result = runbook_stage_runner.run_stage_a(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
    )

    assert result["runner_result"] == "PASS"
    assert result["dry_run"] is True
    assert result["paper_test_confirmed"] is False
    command_dir = tmp_path / "command_runs" / result["runbook_day_id"]
    command_jsons = sorted(command_dir.glob("*.json"))
    assert len(command_jsons) == 6
    assert [json.loads(path.read_text(encoding="utf-8"))["step_id"] for path in command_jsons] == list(range(6))
    assert [json.loads(path.read_text(encoding="utf-8"))["command_key"] for path in command_jsons] == [
        "status",
        "data_prepare",
        "data_freshness",
        "daily_plan",
        "export_daily_plan_notion",
        "export_execution_template",
    ]


def test_dry_run_stage_a_creates_stage_summary_and_latest(tmp_path: Path) -> None:
    result = runbook_stage_runner.run_stage_a(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
    )

    stage_dir = tmp_path / "stage_runs" / result["runbook_day_id"]
    assert Path(result["stage_summary_json"]).exists()
    assert Path(result["stage_summary_txt"]).exists()
    assert Path(result["latest_stage_summary_json"]).exists()
    assert Path(result["latest_stage_summary_txt"]).exists()
    assert (stage_dir / "latest_A.json").exists()
    assert (stage_dir / "latest_A.txt").exists()
    latest = json.loads((stage_dir / "latest_A.json").read_text(encoding="utf-8"))
    assert latest["runner_result"] == "PASS"
    assert latest["counts"]["total"] == 6


def test_stage_a_uses_per_runbook_day_id_directories(tmp_path: Path) -> None:
    result_a = runbook_stage_runner.run_stage_a(tmp_path, "paper_A", DATA_DATE, TRADE_DATE, dry_run=True)
    result_b = runbook_stage_runner.run_stage_a(tmp_path, "paper_B", DATA_DATE, TRADE_DATE, dry_run=True)

    assert result_a["runbook_day_id"] != result_b["runbook_day_id"]
    assert (tmp_path / "runbook_states" / f"{result_a['runbook_day_id']}.json").exists()
    assert (tmp_path / "runbook_states" / f"{result_b['runbook_day_id']}.json").exists()
    assert (tmp_path / "command_runs" / result_a["runbook_day_id"]).exists()
    assert (tmp_path / "command_runs" / result_b["runbook_day_id"]).exists()


def test_stage_a_state_transition_records_running_to_pass(tmp_path: Path) -> None:
    result = runbook_stage_runner.run_stage_a(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        dry_run=True,
    )

    state_path = Path(result["state_path"])
    state = runbook_state.load_state(state_path)
    assert state.current_stage == "A"
    assert state.current_status == "PASS"
    assert state.stage_status["A"] == "PASS"
    assert state.last_completed_stage == "A"
    assert state.last_completed_step == 5
    assert [event["event_type"] for event in state.history if event["event_type"].startswith("stage_")] == [
        "stage_started",
        "stage_completed",
    ]


def test_stage_a_selects_only_step_0_to_5() -> None:
    commands = runbook_stage_runner.get_stage_a_commands()

    assert [command.step_id for command in commands] == list(range(6))
    assert {command.stage_id for command in commands} == {"A"}


def test_stage_a_rejects_non_stage_a_command() -> None:
    commands = list(runbook_stage_runner.get_stage_a_commands())
    commands[5] = replace(commands[5], stage_id="B")

    try:
        runbook_stage_runner.validate_stage_a_commands(commands)
    except ValueError as exc:
        assert "invalid stage_id" in str(exc)
    else:
        raise AssertionError("expected invalid stage command to raise")


def test_fake_subprocess_success_marks_results_pass(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        calls.append(argv)
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 12,
            "stdout": '{"ok": true}',
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = runbook_stage_runner.run_stage_a(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert result["dry_run"] is False
    assert result["paper_test_confirmed"] is True
    assert len(calls) == 6
    assert all(isinstance(call, list) for call in calls)
    assert all(call[0] == sys.executable for call in calls)
    command_json = next((tmp_path / "command_runs" / result["runbook_day_id"]).glob("*_000_status.json"))
    payload = json.loads(command_json.read_text(encoding="utf-8"))
    assert payload["process"]["executed"] is True
    assert payload["process"]["exit_code"] == 0
    assert payload["process"]["duration_ms"] == 12
    assert payload["raw_payload"] == {"ok": True}


def test_fake_subprocess_failure_is_fail_stop(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        calls.append(argv)
        exit_code = 1 if len(calls) == 3 else 0
        return {
            "executed": True,
            "exit_code": exit_code,
            "duration_ms": 10,
            "stdout": "",
            "stderr": "failed at step",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = runbook_stage_runner.run_stage_a(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "FAILED"
    assert len(calls) == 3
    command_jsons = sorted((tmp_path / "command_runs" / result["runbook_day_id"]).glob("*.json"))
    assert len(command_jsons) == 3
    assert [json.loads(path.read_text(encoding="utf-8"))["step_id"] for path in command_jsons] == [0, 1, 2]
    state = runbook_state.load_state(Path(result["state_path"]))
    assert state.current_status == "FAILED"
    assert state.stage_status["A"] == "FAILED"
    assert state.last_completed_step == 1


def test_command_result_log_is_written(tmp_path: Path, monkeypatch) -> None:
    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 9,
            "stdout": "plain stdout",
            "stderr": "plain stderr",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = runbook_stage_runner.run_stage_a(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )
    command_json = next((tmp_path / "command_runs" / result["runbook_day_id"]).glob("*_000_status.json"))
    payload = json.loads(command_json.read_text(encoding="utf-8"))
    log_path = tmp_path / payload["outputs"]["log_ref"]

    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "rendered_argv:" in log_text
    assert "normalized_argv:" in log_text
    assert "argv:" in log_text
    assert "exit_code: 0" in log_text
    assert "plain stdout" in log_text
    assert "plain stderr" in log_text


def test_normalize_python_script_argv_uses_sys_executable() -> None:
    argv = runbook_stage_runner.normalize_python_script_argv(
        ["scripts\\paper.py", "data-freshness"],
        Path("D:/repo"),
    )

    assert argv[0] == sys.executable
    assert argv[1].endswith("scripts\\paper.py")
    assert argv[2:] == ["data-freshness"]


def test_cli_stage_a_dry_run_outputs_json(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_stage_runner.py",
            "stage-a",
            "--workspace",
            str(tmp_path),
            "--account-id",
            "paper_cli",
            "--data-date",
            DATA_DATE,
            "--trade-date",
            TRADE_DATE,
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
    assert payload["stage_id"] == "A"
    assert payload["dry_run"] is True
    assert payload["paper_test_confirmed"] is False
    assert Path(payload["latest_stage_summary_json"]).exists()
    assert Path(payload["stage_summary_json"]).exists()


def test_stage_a_summary_uses_result_helper_contract(tmp_path: Path) -> None:
    result = runbook_stage_runner.run_stage_a(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, dry_run=True)
    summary = json.loads(Path(result["stage_summary_json"]).read_text(encoding="utf-8"))

    assert runbook_result.validate_stage_summary(summary) == []
    assert summary["schema_version"] == "runbook_stage_summary.v1"
    assert summary["summary"]["next_stage"] == "GATE1"


def test_real_stage_a_without_confirm_is_blocked(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        calls.append(argv)
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = runbook_stage_runner.run_stage_a(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "paper_test_confirmation_required"
    assert result["dry_run"] is False
    assert result["paper_test_confirmed"] is False
    assert calls == []


def test_real_stage_a_with_confirm_and_paper_account_is_allowed(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        calls.append(argv)
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = runbook_stage_runner.run_stage_a(
        tmp_path,
        "paper_smoke",
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "PASS"
    assert result["paper_test_confirmed"] is True
    assert result["dry_run"] is False
    assert len(calls) == 6


def test_real_stage_a_with_confirm_and_non_paper_account_is_blocked(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800) -> dict[str, object]:
        calls.append(argv)
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = runbook_stage_runner.run_stage_a(
        tmp_path,
        "live_account",
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "paper_account_required"
    assert result["paper_test_confirmed"] is True
    assert calls == []


def test_cli_real_stage_a_without_confirm_returns_blocked_json(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_stage_runner.py",
            "stage-a",
            "--workspace",
            str(tmp_path),
            "--account-id",
            "paper_cli",
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
    assert payload["reason"] == "paper_test_confirmation_required"
    assert payload["dry_run"] is False
    assert payload["paper_test_confirmed"] is False
