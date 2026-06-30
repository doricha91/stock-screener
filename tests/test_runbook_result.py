from __future__ import annotations

import json
from pathlib import Path

from scripts import runbook_command_registry as registry
from scripts import runbook_result
from scripts import runbook_state


ACCOUNT_ID = "paper_A"
DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"


def _state(account_id: str = ACCOUNT_ID) -> runbook_state.RunbookState:
    return runbook_state.create_initial_state(account_id, DATA_DATE, TRADE_DATE)


def _command_result(
    state: runbook_state.RunbookState,
    command_key: str,
    runner_result: str,
    workspace: Path | None = None,
) -> dict[str, object]:
    return runbook_result.create_command_result(
        state,
        registry.get_command(command_key),
        runner_result,
        f"{command_key} sample message",
        workspace=workspace,
    )


def test_create_command_result_has_schema_version() -> None:
    state = _state()
    command = registry.get_command("daily_plan")

    result = runbook_result.create_command_result(state, command, "PASS", "Fake/sample result.")

    assert result["schema_version"] == "runbook_command_result.v1"
    assert result["runner_result"] == "PASS"


def test_command_result_includes_frozen_context_and_runbook_day_id() -> None:
    state = _state()

    result = _command_result(state, "daily_plan", "PASS")

    assert result["runbook_day_id"] == state.runbook_day_id
    assert result["frozen_context"] == {
        "account_id": ACCOUNT_ID,
        "data_date": DATA_DATE,
        "trade_date": TRADE_DATE,
    }


def test_command_result_process_defaults_to_not_executed() -> None:
    state = _state()

    result = _command_result(state, "daily_plan", "PASS")

    assert result["process"] == {
        "executed": False,
        "exit_code": None,
        "duration_ms": None,
    }


def test_command_result_artifact_refs_are_canonicalized(tmp_path: Path) -> None:
    state = _state()
    command = registry.get_command("daily_plan")

    result = runbook_result.create_command_result(
        state,
        command,
        "PASS",
        "Fake/sample result.",
        artifact_refs={"daily_plan_json": r".\outputs\plan.json"},
        workspace=tmp_path,
    )

    assert result["outputs"]["artifact_refs"] == {"daily_plan_json": "outputs/plan.json"}


def test_validate_command_result_accepts_valid_result() -> None:
    state = _state()

    result = _command_result(state, "daily_plan", "PASS")

    assert runbook_result.validate_command_result(result) == []


def test_validate_command_result_reports_missing_required_field() -> None:
    state = _state()
    result = _command_result(state, "daily_plan", "PASS")
    result.pop("command_key")

    errors = runbook_result.validate_command_result(result)

    assert "command_key is required" in errors


def test_write_command_result_uses_runbook_day_directory_and_filename(tmp_path: Path) -> None:
    state = _state()
    command = registry.get_command("daily_plan")
    result = runbook_result.create_command_result(state, command, "PASS", "Fake/sample result.")

    json_path, txt_path = runbook_result.write_command_result(tmp_path, state, command, result)

    expected_dir = tmp_path / "command_runs" / state.runbook_day_id
    assert json_path.parent == expected_dir
    assert txt_path.parent == expected_dir
    assert json_path.name.endswith("_003_daily_plan.json")
    assert txt_path.name.endswith("_003_daily_plan.txt")
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["outputs"]["json_ref"].startswith(f"command_runs/{state.runbook_day_id}/")
    assert "[PASS] Step 3 daily_plan" in txt_path.read_text(encoding="utf-8")


def test_create_stage_summary_groups_command_results() -> None:
    state = _state()
    command_results = [
        _command_result(state, "status", "PASS"),
        _command_result(state, "daily_plan", "PASS"),
    ]

    summary = runbook_result.create_stage_summary(
        state,
        "A",
        command_results,
        next_required_action="Wait for Step 6 manual execution input.",
        next_stage="GATE1",
    )

    assert summary["schema_version"] == "runbook_stage_summary.v1"
    assert summary["runner_result"] == "PASS"
    assert summary["counts"]["total"] == 2
    assert summary["steps"] == [
        {
            "step_id": 0,
            "command_key": "status",
            "runner_result": "PASS",
            "result_json_ref": None,
        },
        {
            "step_id": 3,
            "command_key": "daily_plan",
            "runner_result": "PASS",
            "result_json_ref": None,
        },
    ]


def test_stage_summary_runner_result_priority() -> None:
    state = _state()

    cases = [
        ("WARNING", ["PASS", "WARNING"]),
        ("WAIT", ["PASS", "WARNING", "WAIT"]),
        ("BLOCKED", ["PASS", "WAIT", "BLOCKED"]),
        ("FAILED", ["PASS", "BLOCKED", "FAILED"]),
        ("PASS", ["PASS", "SKIPPED"]),
    ]
    for expected_result, results in cases:
        command_results = [
            _command_result(state, "status", result)
            for result in results
        ]

        summary = runbook_result.create_stage_summary(state, "A", command_results)

        assert summary["runner_result"] == expected_result


def test_write_stage_summary_writes_timestamped_and_latest_files(tmp_path: Path) -> None:
    state = _state()
    command_results = [_command_result(state, "status", "PASS")]
    summary = runbook_result.create_stage_summary(
        state,
        "A",
        command_results,
        next_required_action="Wait for Step 6 manual execution input.",
    )

    json_path, txt_path = runbook_result.write_stage_summary(tmp_path, state, summary)

    expected_dir = tmp_path / "stage_runs" / state.runbook_day_id
    assert json_path.parent == expected_dir
    assert txt_path.parent == expected_dir
    assert json_path.name.endswith("_A.json")
    assert txt_path.name.endswith("_A.txt")
    assert (expected_dir / "latest_A.json").exists()
    assert (expected_dir / "latest_A.txt").exists()
    assert "[PASS] Stage A summary" in (expected_dir / "latest_A.txt").read_text(encoding="utf-8")


def test_format_stage_summary_text_contains_telegram_push_fields() -> None:
    state = _state()
    summary = runbook_result.create_stage_summary(
        state,
        "A",
        [_command_result(state, "status", "PASS")],
        next_required_action="Wait for Step 6 manual execution input.",
    )

    text = runbook_result.format_stage_summary_text(summary)

    assert "[PASS] Stage A summary" in text
    assert "Account: paper_A" in text
    assert "Data date: 2026-06-12" in text
    assert "Trade date: 2026-06-15" in text
    assert "Steps: 1 total / 1 pass / 0 warning / 0 blocked / 0 failed" in text
    assert "Next action: Wait for Step 6 manual execution input." in text


def test_multi_account_result_paths_use_separate_directories(tmp_path: Path) -> None:
    state_a = _state("paper_A")
    state_b = _state("paper_B")

    command_a_dir = runbook_result.get_command_runs_dir(tmp_path, state_a.runbook_day_id)
    command_b_dir = runbook_result.get_command_runs_dir(tmp_path, state_b.runbook_day_id)
    stage_a_dir = runbook_result.get_stage_runs_dir(tmp_path, state_a.runbook_day_id)
    stage_b_dir = runbook_result.get_stage_runs_dir(tmp_path, state_b.runbook_day_id)

    assert command_a_dir != command_b_dir
    assert stage_a_dir != stage_b_dir
    assert command_a_dir == tmp_path / "command_runs" / "paper_A_2026-06-12_2026-06-15"
    assert stage_b_dir == tmp_path / "stage_runs" / "paper_B_2026-06-12_2026-06-15"
