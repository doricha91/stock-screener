from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import runbook_command_registry as registry
from scripts import runbook_result
from scripts import runbook_stage_runner
from scripts import runbook_state
from core.paper_execution_intent import build_execution_intent


ACCOUNT_ID = "paper_a"
DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"


TEST_PARTICIPANTS = ["paper_a", "paper_b", "paper_smoke"]


def _shared_pin():
    return {"data_date": DATA_DATE, "participant_account_ids": TEST_PARTICIPANTS,
            "shared_preparation_id": "fixture", "snapshot": {"path": "snapshot.sqlite3", "sha256": "sha256:fixture"}}


@pytest.fixture(autouse=True)
def admitted_shared_input(monkeypatch):
    # Runner unit tests isolate process/result handling. Real preparation and
    # consumer validation are exercised by test_ml1_4c_stage_a_shared.
    monkeypatch.setattr(runbook_stage_runner, "run_shared_market_prepare", lambda **kw: {"result": "REUSE"})
    monkeypatch.setattr(runbook_stage_runner, "validate_shared_market_input", lambda **kw: _shared_pin())


def _run_stage_a(*args, **kwargs):
    return runbook_stage_runner.run_stage_a(*args, shared_participant_account_ids=TEST_PARTICIPANTS, **kwargs)


def _daily_plan_payload(
    *,
    account_id: str = ACCOUNT_ID,
    items: list[dict] | None = None,
) -> dict:
    resolved_items = items if items is not None else [{"symbol": "AAPL", "action": "BUY", "quantity": 2}]
    observed_at = f"{DATA_DATE}T12:00:00+09:00"
    lineage = {
        source: {
            "source": source,
            "selected_max_date": DATA_DATE,
            "observed_at": observed_at,
            "revision": f"test:{source}",
            "validator_result": "PASS",
        }
        for source in ("market", "indicator", "rs", "account")
    }
    for name in ("market", "indicator", "rs"):
        lineage[name].update(source="snapshot.sqlite3", revision="sha256:fixture")
    lineage["universe"] = {
        "source": "test_universe",
        "effective_as_of": DATA_DATE,
        "observed_at": observed_at,
        "revision": "test:universe",
        "validator_result": "PASS",
    }
    lineage["config"] = {
        "source": "test_config",
        "effective_as_of": TRADE_DATE,
        "observed_at": observed_at,
        "revision": "test:config",
        "validator_result": "PASS",
    }
    return {
        "schema_version": "paper_daily_plan.v1",
        "account_id": account_id,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
        "plan_date": TRADE_DATE,
        "run_mode": "official",
        "official_run": True,
        "generated_at": "2026-06-12T12:00:00Z",
        "items": resolved_items,
        "execution_intent": build_execution_intent(resolved_items),
        "fingerprints": {"generator_version": "paper_daily_plan.v1"},
        "as_of_lineage": lineage,
        "shared_input": _shared_pin(),
    }


def _write_daily_plan_for_fake_run(tmp_path: Path, payload: dict) -> str:
    markdown_path = tmp_path / "generated" / f"daily_action_plan_{TRADE_DATE.replace('-', '')}.md"
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.write_text("# test plan\n", encoding="utf-8")
    markdown_path.with_suffix(".json").write_text(json.dumps(payload), encoding="utf-8")
    return f"Official paper daily plan is ready at:\n{markdown_path}\n"


def _is_daily_plan_command(argv: list[str]) -> bool:
    return "plan" in argv and any(str(part).endswith("paper.py") for part in argv)


def test_dry_run_renders_six_commands_without_any_artifact(tmp_path):
    result = _run_stage_a(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, dry_run=True)
    assert result["runner_result"] == "PASS"
    assert len(result["commands"]) == 6
    assert result["command_results"] == []
    assert result["state_mutated"] is False
    assert not list(tmp_path.iterdir())


def test_dry_run_preserves_ready_state_bytes(tmp_path):
    _, path, _ = runbook_state.init_state_file_for_context(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    before = path.read_bytes()
    result = _run_stage_a(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, dry_run=True)
    assert result["runner_result"] == "PASS"
    assert path.read_bytes() == before
    assert not (tmp_path / "command_runs").exists()


def test_stage_a_dry_run_account_identities_remain_separate(tmp_path):
    a = _run_stage_a(tmp_path, "paper_a", DATA_DATE, TRADE_DATE, dry_run=True)
    b = _run_stage_a(tmp_path, "paper_b", DATA_DATE, TRADE_DATE, dry_run=True)
    assert a["runbook_day_id"] != b["runbook_day_id"]
    assert not (tmp_path / "runbook_states").exists()


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

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 12,
            "stdout": (
                _write_daily_plan_for_fake_run(tmp_path, _daily_plan_payload())
                if _is_daily_plan_command(argv)
                else '{"ok": true}'
            ),
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = _run_stage_a(
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

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
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

    result = _run_stage_a(
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
    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 9,
            "stdout": (
                _write_daily_plan_for_fake_run(tmp_path, _daily_plan_payload())
                if _is_daily_plan_command(argv)
                else "plain stdout"
            ),
            "stderr": "plain stderr",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = _run_stage_a(
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
            "--shared-participant-account-ids", "paper_cli",
            "--dry-run",
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
    assert payload["dry_run"] is True
    assert not list(tmp_path.iterdir())


def test_stage_a_summary_uses_result_helper_contract(tmp_path: Path, monkeypatch) -> None:
    def execute(argv, *args, **kwargs):
        stdout = _write_daily_plan_for_fake_run(tmp_path, _daily_plan_payload()) if _is_daily_plan_command(argv) else "{}"
        return {"exit_code": 0, "stdout": stdout, "stderr": "", "duration_ms": 1}
    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", execute)
    result = _run_stage_a(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True)
    state = runbook_state.load_state(Path(result["state_path"]))
    assert state.current_status == "PASS"
    assert [e["event_type"] for e in state.history if e["event_type"].startswith("stage_")] == ["stage_started", "stage_completed"]
    summary = json.loads(Path(result["stage_summary_json"]).read_text(encoding="utf-8"))

    assert runbook_result.validate_stage_summary(summary) == []
    assert summary["schema_version"] == "runbook_stage_summary.v1"
    assert summary["summary"]["next_stage"] == "GATE1"


def test_parse_stdout_json_accepts_full_object() -> None:
    assert runbook_stage_runner._parse_stdout_json('{"created_count": 4}') == {"created_count": 4}


def test_parse_stdout_json_wraps_full_array() -> None:
    assert runbook_stage_runner._parse_stdout_json('[{"target": "daily_plans"}]') == {
        "json": [{"target": "daily_plans"}]
    }


def test_parse_stdout_json_extracts_last_object_after_text() -> None:
    stdout = """PAPER NOTION EXPORT
  manual_execution_template: account_id=paper_a create=4 failed=0
{
  "target": "manual_execution_template",
  "created_count": 4,
  "failed_count": 0
}
"""

    assert runbook_stage_runner._parse_stdout_json(stdout) == {
        "target": "manual_execution_template",
        "created_count": 4,
        "failed_count": 0,
    }


def test_parse_stdout_json_extracts_last_array_after_text() -> None:
    stdout = """PAPER NOTION EXPORT
[
  {
    "target": "daily_plans",
    "action": "created"
  }
]
"""

    assert runbook_stage_runner._parse_stdout_json(stdout) == {
        "json": [{"target": "daily_plans", "action": "created"}]
    }


def test_parse_stdout_json_returns_empty_without_json() -> None:
    assert runbook_stage_runner._parse_stdout_json("PAPER NOTION EXPORT\ncreated=4") == {}


def test_parse_stdout_json_returns_empty_for_malformed_json() -> None:
    assert runbook_stage_runner._parse_stdout_json('PAPER NOTION EXPORT\n{"created_count":') == {}


def test_stage_a_preserves_mixed_stdout_json_in_raw_payload(tmp_path: Path, monkeypatch) -> None:
    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": (
                _write_daily_plan_for_fake_run(tmp_path, _daily_plan_payload())
                if _is_daily_plan_command(argv)
                else 'PAPER NOTION EXPORT\n{"target": "manual_execution_template", "created_count": 4}'
            ),
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = _run_stage_a(
        tmp_path,
        ACCOUNT_ID,
        DATA_DATE,
        TRADE_DATE,
        confirm_paper_test=True,
    )
    command_json = next(
        (tmp_path / "command_runs" / result["runbook_day_id"]).glob("*_005_export_execution_template.json")
    )
    payload = json.loads(command_json.read_text(encoding="utf-8"))

    assert payload["raw_payload"] == {
        "target": "manual_execution_template",
        "created_count": 4,
    }


def test_real_stage_a_without_confirm_is_blocked(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": (
                _write_daily_plan_for_fake_run(
                    tmp_path,
                    _daily_plan_payload(account_id="paper_smoke"),
                )
                if _is_daily_plan_command(argv)
                else ""
            ),
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = _run_stage_a(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "paper_test_confirmation_required"
    assert result["dry_run"] is False
    assert result["paper_test_confirmed"] is False
    assert calls == []


def test_real_stage_a_with_confirm_and_paper_account_is_allowed(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": (
                _write_daily_plan_for_fake_run(
                    tmp_path,
                    _daily_plan_payload(account_id="paper_smoke"),
                )
                if _is_daily_plan_command(argv)
                else ""
            ),
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = _run_stage_a(
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

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        return {
            "executed": True,
            "exit_code": 0,
            "duration_ms": 1,
            "stdout": "",
            "stderr": "",
        }

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)

    result = _run_stage_a(
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


def test_stage_a_valid_execution_plan_exposes_pinned_intent(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    workspace = tmp_path / "workspace"

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        stdout = (
            _write_daily_plan_for_fake_run(tmp_path, _daily_plan_payload())
            if _is_daily_plan_command(argv)
            else ""
        )
        return {"executed": True, "exit_code": 0, "duration_ms": 1, "stdout": stdout, "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)
    result = _run_stage_a(
        workspace, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert result["runner_result"] == "PASS"
    assert result["action_mode"] == "EXECUTION"
    assert result["execution_required"] is True
    assert result["candidate_execution_count"] == 1
    assert result["no_action_reason"] is None
    assert result["daily_plan_json"]
    assert result["daily_plan_json"].startswith(f"artifacts/{result['runbook_day_id']}/stage_a/")
    assert (workspace / result["daily_plan_json"]).is_file()
    summary = json.loads(Path(result["stage_summary_json"]).read_text(encoding="utf-8"))
    assert summary["summary"]["next_required_action"] == (
        "Fill Manual Execution in Notion, then run Gate 1."
    )
    assert len(calls) == 6
    state = runbook_state.load_state(Path(result["state_path"]))
    assert state.artifacts["daily_plan_json"] == result["daily_plan_json"]


def test_stage_a_valid_no_action_plan_runs_exports_and_exposes_summary(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        stdout = (
            _write_daily_plan_for_fake_run(tmp_path, _daily_plan_payload(items=[]))
            if _is_daily_plan_command(argv)
            else ""
        )
        return {"executed": True, "exit_code": 0, "duration_ms": 1, "stdout": stdout, "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)
    result = _run_stage_a(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )
    summary = json.loads(Path(result["stage_summary_json"]).read_text(encoding="utf-8"))

    assert result["runner_result"] == "PASS"
    assert result["action_mode"] == "NO_ACTION"
    assert result["execution_required"] is False
    assert result["candidate_execution_count"] == 0
    assert result["no_action_reason"] == "no_executable_orders"
    assert summary["raw_payload"]["action_mode"] == "NO_ACTION"
    assert summary["raw_payload"]["daily_plan_json"] == result["daily_plan_json"]
    assert summary["summary"]["next_required_action"] == (
        "No Manual Execution input is required. "
        "Run Gate 1 to validate the pinned no-action Daily Plan."
    )
    assert len(calls) == 6
    assert any("--daily-plan" in argv for argv in calls)
    assert any("--manual-execution-template" in argv for argv in calls)


def test_stage_a_malformed_intent_blocks_before_exports(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    payload = _daily_plan_payload(items=[])
    payload["execution_intent"]["action_mode"] = "EXECUTION"

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        stdout = _write_daily_plan_for_fake_run(tmp_path, payload) if _is_daily_plan_command(argv) else ""
        return {"executed": True, "exit_code": 0, "duration_ms": 1, "stdout": stdout, "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)
    result = _run_stage_a(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "daily_plan_execution_intent_invalid"
    assert len(calls) == 4
    assert not any("--daily-plan" in argv for argv in calls)
    assert not any("--manual-execution-template" in argv for argv in calls)


def test_stage_a_context_mismatch_blocks_before_exports(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    payload = _daily_plan_payload(account_id="paper_other")

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        stdout = _write_daily_plan_for_fake_run(tmp_path, payload) if _is_daily_plan_command(argv) else ""
        return {"executed": True, "exit_code": 0, "duration_ms": 1, "stdout": stdout, "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)
    result = _run_stage_a(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "daily_plan_context_mismatch"
    assert len(calls) == 4


def test_stage_a_missing_asof_lineage_blocks_before_exports(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    payload = _daily_plan_payload()
    del payload["as_of_lineage"]

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        stdout = _write_daily_plan_for_fake_run(tmp_path, payload) if _is_daily_plan_command(argv) else ""
        return {"executed": True, "exit_code": 0, "duration_ms": 1, "stdout": stdout, "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)
    result = _run_stage_a(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "asof_provenance_missing"
    assert len(calls) == 4
    assert not any("--daily-plan" in argv for argv in calls)


def test_stage_a_future_lineage_blocks_before_exports(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []
    payload = _daily_plan_payload()
    payload["as_of_lineage"]["indicator"]["selected_max_date"] = "2026-06-13"

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        stdout = _write_daily_plan_for_fake_run(tmp_path, payload) if _is_daily_plan_command(argv) else ""
        return {"executed": True, "exit_code": 0, "duration_ms": 1, "stdout": stdout, "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)
    result = _run_stage_a(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "asof_future_source"
    assert len(calls) == 4
    assert not any("--daily-plan" in argv for argv in calls)


def test_stage_a_missing_daily_plan_evidence_blocks_before_exports(tmp_path: Path, monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(argv: list[str], cwd: Path, timeout_sec: int = 1800, **kwargs) -> dict[str, object]:
        calls.append(argv)
        return {"executed": True, "exit_code": 0, "duration_ms": 1, "stdout": "", "stderr": ""}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)
    result = _run_stage_a(
        tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE, confirm_paper_test=True
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "daily_plan_json_missing"
    assert len(calls) == 4


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
            "--shared-participant-account-ids", "paper_cli",
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
