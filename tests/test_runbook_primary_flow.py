from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from core import runbook_day_rollover
from scripts import runbook_primary_flow
from scripts import runbook_state


ACCOUNT_ID = "paper_test"
DATA_DATE = "2026-08-27"
TRADE_DATE = "2026-08-28"
ROOT = Path(__file__).resolve().parents[1]
WRAPPERS = ROOT / "ops" / "runbook_wrappers"
DAILY = WRAPPERS / "daily"


def _state_through(*stages: str, version: str = runbook_state.EXECUTION_CONTRACT_V2):
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    state = replace(
        state,
        execution_contract={
            "version": version,
            "input_finalized": False,
            "finalized_at": None,
        },
    )
    for stage in stages:
        state = runbook_state.complete_stage(state, stage)
    return state


def _install_flow_fakes(
    monkeypatch: pytest.MonkeyPatch,
    state,
    *,
    outcomes: dict[str, str] | None = None,
    action_mode: str = "EXECUTION",
    stage_c_next_action: str | None = None,
    preview_required: bool | None = None,
) -> tuple[list[str], list[Any]]:
    outcomes = outcomes or {}
    calls: list[str] = []
    holder = [state]
    stage_c_next_action = stage_c_next_action or (
        "No Manual Review input is required. Run Gate 2 to validate the pinned no-action review state."
        if action_mode == "NO_ACTION"
        else "Fill Manual Review in Notion, then run Gate 2."
    )
    preview_required = action_mode != "NO_ACTION" if preview_required is None else preview_required
    monkeypatch.setattr(runbook_primary_flow, "_load_state", lambda *args, **kwargs: holder[0])
    monkeypatch.setattr(
        runbook_primary_flow,
        "load_stage_c_summary_evidence",
        lambda *args, **kwargs: (
            {
                "runner_result": "PASS",
                "stage_id": "C",
                "summary": {"next_required_action": stage_c_next_action},
            },
            Path("isolated/stage_c_summary.json"),
        ),
    )

    def stage(name: str, state_id: str | None = None):
        def fake(*args, **kwargs):
            calls.append(name)
            outcome = outcomes.get(name, "PASS")
            if outcome == "PASS" and state_id:
                holder[0] = runbook_state.complete_stage(holder[0], state_id)
                if state_id == "F":
                    holder[0] = replace(holder[0], last_completed_step=21)
            result = {
                "runner_result": outcome,
                "reason": None if outcome == "PASS" else f"{name.lower()}_{outcome.lower()}",
                "action_mode": action_mode,
            }
            if name == "C":
                result["next_required_action"] = stage_c_next_action
            if name == "D_PREVIEW":
                result.update(
                    {
                        "review_preview_json": (
                            "isolated/review_preview.json" if preview_required else None
                        ),
                        "review_preview_md": (
                            "isolated/review_preview.md" if preview_required else None
                        ),
                        "review_preview_skipped": not preview_required,
                        "next_required_action": (
                            "Review preview artifact, then run Stage D append/sync."
                            if preview_required
                            else "No review preview is required. Run Stage D append/sync to record the verified no-action completion."
                        ),
                    }
                )
            return result

        return fake

    monkeypatch.setattr(runbook_primary_flow.runbook_gate_checker, "check_gate1_execution_input", stage("GATE1", "GATE1"))
    monkeypatch.setattr(runbook_primary_flow.runbook_stage_runner, "run_stage_b", stage("B", "B"))
    monkeypatch.setattr(runbook_primary_flow.runbook_stage_b_verifier, "verify_stage_b_completion", stage("VERIFY"))
    monkeypatch.setattr(runbook_primary_flow.runbook_stage_runner, "run_stage_c", stage("C", "C"))
    monkeypatch.setattr(runbook_primary_flow.runbook_stage_runner, "check_gate2", stage("GATE2", "GATE2"))
    monkeypatch.setattr(runbook_primary_flow.runbook_stage_runner, "run_stage_d_preview", stage("D_PREVIEW"))
    monkeypatch.setattr(runbook_primary_flow.runbook_stage_runner, "run_stage_d_append", stage("D", "D"))
    monkeypatch.setattr(runbook_primary_flow.runbook_stage_runner, "run_stage_e", stage("E", "E"))
    monkeypatch.setattr(runbook_primary_flow.runbook_stage_runner, "run_stage_f", stage("F", "F"))
    return calls, holder


def _run_02():
    return runbook_primary_flow.run_execution_to_review_prep(
        Path("isolated"), ACCOUNT_ID, DATA_DATE, TRADE_DATE
    )


def _run_03():
    return runbook_primary_flow.run_review_preview(
        Path("isolated"), ACCOUNT_ID, DATA_DATE, TRADE_DATE
    )


def _run_04():
    return runbook_primary_flow.run_close_day(
        Path("isolated"), ACCOUNT_ID, DATA_DATE, TRADE_DATE
    )


def test_daily_surface_is_exactly_five_wrappers_and_preserves_detailed_recovery() -> None:
    assert sorted(path.name for path in DAILY.glob("*.cmd")) == [
        "00_prepare_next_runbook_day.cmd",
        "01_stage_a_plan_prep.cmd",
        "02_execution_to_review_prep.cmd",
        "03_review_preview.cmd",
        "04_close_day.cmd",
    ]
    detailed = [
        "02_gate1_execution_input.cmd",
        "03_stage_b_execution_commit_sync.cmd",
        "04_stage_b_verify.cmd",
        "05_stage_c_review_prep.cmd",
        "06_gate2_review_input.cmd",
        "07_stage_d_preview.cmd",
        "08_stage_d_append_sync.cmd",
        "09_stage_e_eod_close.cmd",
        "10_stage_f_benchmark_notion_sync.cmd",
    ]
    for name in detailed:
        assert (WRAPPERS / name).is_file(), name


def test_primary_00_preserves_prepare_boundary_and_propagates_exit() -> None:
    text = (DAILY / "00_prepare_next_runbook_day.cmd").read_text(encoding="utf-8")
    assert "..\\00_prepare_next_runbook_day.cmd" in text
    assert "Review the frozen Runbook dates" in text
    assert "Stage A was NOT_RUN" in text
    assert "01_stage_a_plan_prep.cmd" in text
    assert "call \"%~dp0..\\01_stage_a_plan_prep.cmd\"" not in text
    assert "exit /b %EXIT_CODE%" in text


@pytest.mark.parametrize("action_mode", ["EXECUTION", "NO_ACTION"])
def test_primary_01_preserves_stage_a_boundary_for_both_action_modes(action_mode: str) -> None:
    text = (DAILY / "01_stage_a_plan_prep.cmd").read_text(encoding="utf-8")
    assert "..\\01_stage_a_plan_prep.cmd" in text
    assert "Manual Execution input only when required" in text
    assert "Primary 02 was NOT_RUN" in text
    assert "call \"%~dp0..\\02_gate1_execution_input.cmd\"" not in text
    assert "exit /b %EXIT_CODE%" in text
    assert action_mode in {"EXECUTION", "NO_ACTION"}


def test_primary_wrappers_suppress_only_nested_pause() -> None:
    env_text = (WRAPPERS / "_env.cmd").read_text(encoding="utf-8")
    prepare_text = (WRAPPERS / "00_prepare_next_runbook_day.cmd").read_text(encoding="utf-8")
    assert 'if /I "%RUNBOOK_CHAINED_MODE%"=="1" set "PAUSE_ON_EXIT=0"' in env_text
    assert 'if /I "%RUNBOOK_CHAINED_MODE%"=="1" set "PAUSE_ON_EXIT=0"' in prepare_text
    for name in (
        "00_prepare_next_runbook_day.cmd",
        "01_stage_a_plan_prep.cmd",
        "02_execution_to_review_prep.cmd",
        "03_review_preview.cmd",
        "04_close_day.cmd",
    ):
        assert 'set "RUNBOOK_CHAINED_MODE=1"' in (DAILY / name).read_text(encoding="utf-8")


def test_primary_02_execution_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, holder = _install_flow_fakes(monkeypatch, _state_through("A"))
    result = _run_02()
    assert result["runner_result"] == "PASS"
    assert calls == ["GATE1", "B", "VERIFY", "C"]
    assert holder[0].stage_status["C"] == "PASS"
    assert result["next_required_action"] == runbook_primary_flow.MANUAL_REVIEW_REQUIRED
    terminal = runbook_primary_flow.format_operator_summary(result)
    assert f"STOP: {runbook_primary_flow.MANUAL_REVIEW_REQUIRED}" in terminal


@pytest.mark.parametrize(
    ("outcomes", "expected_calls", "stopped_at"),
    [
        ({"GATE1": "WAIT"}, ["GATE1"], "GATE1"),
        ({"GATE1": "BLOCKED"}, ["GATE1"], "GATE1"),
        ({"B": "FAILED"}, ["GATE1", "B"], "STAGE_B"),
        ({"VERIFY": "FAILED"}, ["GATE1", "B", "VERIFY"], "STAGE_B_VERIFICATION"),
        ({"C": "FAILED"}, ["GATE1", "B", "VERIFY", "C"], "STAGE_C"),
    ],
)
def test_primary_02_is_fail_fast(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: dict[str, str],
    expected_calls: list[str],
    stopped_at: str,
) -> None:
    calls, holder = _install_flow_fakes(monkeypatch, _state_through("A"), outcomes=outcomes)
    result = _run_02()
    assert calls == expected_calls
    assert result["stopped_at"] == stopped_at
    assert result["no_downstream_stage_executed"] is True
    assert holder[0].stage_status["C"] != "PASS"


def test_primary_02_retry_does_not_repeat_execution_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, holder = _install_flow_fakes(monkeypatch, _state_through("A", "GATE1", "B"))
    result = _run_02()
    assert result["runner_result"] == "PASS"
    assert calls == ["VERIFY", "C"]
    assert holder[0].stage_status["C"] == "PASS"


@pytest.mark.parametrize(
    ("version", "finalized"),
    [
        (runbook_state.EXECUTION_CONTRACT_V1, False),
        (runbook_state.EXECUTION_CONTRACT_V2, True),
    ],
)
def test_primary_02_delegates_v1_and_v2_gate_semantics(
    monkeypatch: pytest.MonkeyPatch, version: str, finalized: bool
) -> None:
    state = _state_through("A", version=version)
    state = replace(
        state,
        execution_contract={
            "version": version,
            "input_finalized": finalized,
            "finalized_at": "2026-08-28T09:00:00+09:00" if finalized else None,
        },
    )
    calls, _ = _install_flow_fakes(monkeypatch, state)
    assert _run_02()["runner_result"] == "PASS"
    assert calls == ["GATE1", "B", "VERIFY", "C"]


def test_primary_02_already_finalized_retry_skips_gate_and_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, _ = _install_flow_fakes(monkeypatch, _state_through("A", "GATE1", "B", "C"))
    result = _run_02()
    assert result["runner_result"] == "PASS"
    assert calls == []


@pytest.mark.parametrize("action_mode", ["EXECUTION", "NO_ACTION"])
def test_primary_02_preserves_action_mode_path(
    monkeypatch: pytest.MonkeyPatch, action_mode: str
) -> None:
    calls, _ = _install_flow_fakes(
        monkeypatch, _state_through("A"), action_mode=action_mode
    )
    assert _run_02()["runner_result"] == "PASS"
    assert calls == ["GATE1", "B", "VERIFY", "C"]


def test_primary_02_no_action_guidance_matches_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_flow_fakes(monkeypatch, _state_through("A"), action_mode="NO_ACTION")
    result = _run_02()
    terminal = runbook_primary_flow.format_operator_summary(result)

    assert result["next_required_action"] == runbook_primary_flow.MANUAL_REVIEW_NOT_REQUIRED
    assert f"STOP: {runbook_primary_flow.MANUAL_REVIEW_NOT_REQUIRED}" in terminal
    assert "Fill Manual Review in Notion" not in terminal


def test_primary_02_verified_zero_write_guidance_uses_canonical_stage_c_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_flow_fakes(
        monkeypatch,
        _state_through("A"),
        action_mode="EXECUTION",
        stage_c_next_action="The canonical Manual Review scope is empty. Run Gate 2 to verify it.",
    )
    result = _run_02()
    terminal = runbook_primary_flow.format_operator_summary(result)

    assert result["next_required_action"] == runbook_primary_flow.MANUAL_REVIEW_NOT_REQUIRED
    assert f"STOP: {runbook_primary_flow.MANUAL_REVIEW_NOT_REQUIRED}" in terminal
    assert "Fill Manual Review in Notion" not in terminal


def test_primary_03_stops_after_preview_without_append(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, _ = _install_flow_fakes(monkeypatch, _state_through("A", "GATE1", "B", "C"))
    result = _run_03()
    assert result["runner_result"] == "PASS"
    assert calls == ["GATE2", "D_PREVIEW"]
    assert result["preview_artifacts"]["review_preview_json"]
    assert result["next_required_action"] == runbook_primary_flow.REVIEW_PREVIEW_REQUIRED
    terminal = runbook_primary_flow.format_operator_summary(result)
    assert f"STOP: {runbook_primary_flow.REVIEW_PREVIEW_REQUIRED}" in terminal


def test_primary_03_no_action_guidance_matches_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_flow_fakes(
        monkeypatch,
        _state_through("A", "GATE1", "B", "C"),
        action_mode="NO_ACTION",
    )
    result = _run_03()
    terminal = runbook_primary_flow.format_operator_summary(result)

    assert result["preview_artifacts"] == {
        "review_preview_json": None,
        "review_preview_md": None,
    }
    assert result["next_required_action"] == runbook_primary_flow.REVIEW_PREVIEW_NOT_REQUIRED
    assert f"STOP: {runbook_primary_flow.REVIEW_PREVIEW_NOT_REQUIRED}" in terminal
    assert "Review Stage D preview artifact" not in terminal


@pytest.mark.parametrize(
    ("outcomes", "calls_expected", "stopped_at"),
    [
        ({"GATE2": "BLOCKED"}, ["GATE2"], "GATE2"),
        ({"D_PREVIEW": "FAILED"}, ["GATE2", "D_PREVIEW"], "STAGE_D_PREVIEW"),
    ],
)
def test_primary_03_is_fail_fast(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: dict[str, str],
    calls_expected: list[str],
    stopped_at: str,
) -> None:
    calls, holder = _install_flow_fakes(
        monkeypatch, _state_through("A", "GATE1", "B", "C"), outcomes=outcomes
    )
    result = _run_03()
    assert calls == calls_expected
    assert result["stopped_at"] == stopped_at
    assert holder[0].stage_status["D"] != "PASS"


def test_primary_blocked_guidance_does_not_show_pass_next_action(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_flow_fakes(
        monkeypatch,
        _state_through("A"),
        outcomes={"GATE1": "BLOCKED"},
    )
    result = _run_02()
    terminal = runbook_primary_flow.format_operator_summary(result)

    assert result["runner_result"] == "BLOCKED"
    assert "STOPPED_AT: GATE1" in terminal
    assert "Recovery: ops\\runbook_wrappers\\02_gate1_execution_input.cmd" in terminal
    assert "STOP: Fill Manual Review" not in terminal
    assert "STOP: No Manual Review" not in terminal


def test_primary_04_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, holder = _install_flow_fakes(
        monkeypatch, _state_through("A", "GATE1", "B", "C", "GATE2")
    )
    result = _run_04()
    assert result["runner_result"] == "PASS"
    assert calls == ["D", "E", "F"]
    assert holder[0].stage_status["F"] == "PASS"


@pytest.mark.parametrize(
    ("outcomes", "calls_expected", "stopped_at"),
    [
        ({"D": "FAILED"}, ["D"], "STAGE_D"),
        ({"E": "FAILED"}, ["D", "E"], "STAGE_E"),
        ({"F": "FAILED"}, ["D", "E", "F"], "STAGE_F"),
    ],
)
def test_primary_04_is_fail_fast(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: dict[str, str],
    calls_expected: list[str],
    stopped_at: str,
) -> None:
    calls, _ = _install_flow_fakes(
        monkeypatch,
        _state_through("A", "GATE1", "B", "C", "GATE2"),
        outcomes=outcomes,
    )
    result = _run_04()
    assert calls == calls_expected
    assert result["stopped_at"] == stopped_at


def test_primary_04_retry_after_d_skips_duplicate_append(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, _ = _install_flow_fakes(
        monkeypatch, _state_through("A", "GATE1", "B", "C", "GATE2", "D")
    )
    assert _run_04()["runner_result"] == "PASS"
    assert calls == ["E", "F"]


def test_primary_04_retry_after_e_is_f_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, _ = _install_flow_fakes(
        monkeypatch, _state_through("A", "GATE1", "B", "C", "GATE2", "D", "E")
    )
    assert _run_04()["runner_result"] == "PASS"
    assert calls == ["F"]


def test_primary_04_complete_rerun_does_not_repeat_d_or_e(monkeypatch: pytest.MonkeyPatch) -> None:
    calls, _ = _install_flow_fakes(
        monkeypatch,
        _state_through("A", "GATE1", "B", "C", "GATE2", "D", "E", "F"),
        outcomes={"F": "SKIPPED"},
    )
    assert _run_04()["runner_result"] == "PASS"
    assert calls == ["F"]


@pytest.mark.parametrize("action_mode", ["EXECUTION", "NO_ACTION"])
def test_continuous_primary_lifecycle_reaches_standard_completed(
    monkeypatch: pytest.MonkeyPatch, action_mode: str
) -> None:
    calls, holder = _install_flow_fakes(
        monkeypatch, _state_through("A"), action_mode=action_mode
    )
    assert _run_02()["runner_result"] == "PASS"
    assert _run_03()["runner_result"] == "PASS"
    assert _run_04()["runner_result"] == "PASS"
    assert calls == ["GATE1", "B", "VERIFY", "C", "GATE2", "D_PREVIEW", "D", "E", "F"]
    assert all(holder[0].stage_status[stage] == "PASS" for stage in runbook_state.STAGE_IDS)

    record = runbook_day_rollover.StateRecord(
        path=Path("isolated/runbook_state.json"),
        state=holder[0],
        raw_stage_status=dict(holder[0].stage_status),
    )
    monkeypatch.setattr(runbook_day_rollover, "_is_standard_completed", lambda *args: True)
    classified = runbook_day_rollover.classify_state(Path("isolated"), record)
    assert classified["classification"] == "STANDARD_COMPLETED"


@pytest.mark.parametrize(
    ("flow_arg", "runner_name", "primary_flow", "next_action", "forbidden"),
    [
        (
            "execution-to-review-prep",
            "run_execution_to_review_prep",
            runbook_primary_flow.FLOW_EXECUTION_TO_REVIEW,
            runbook_primary_flow.MANUAL_REVIEW_REQUIRED,
            runbook_primary_flow.MANUAL_REVIEW_NOT_REQUIRED,
        ),
        (
            "execution-to-review-prep",
            "run_execution_to_review_prep",
            runbook_primary_flow.FLOW_EXECUTION_TO_REVIEW,
            runbook_primary_flow.MANUAL_REVIEW_NOT_REQUIRED,
            runbook_primary_flow.MANUAL_REVIEW_REQUIRED,
        ),
        (
            "review-preview",
            "run_review_preview",
            runbook_primary_flow.FLOW_REVIEW_PREVIEW,
            runbook_primary_flow.REVIEW_PREVIEW_REQUIRED,
            runbook_primary_flow.REVIEW_PREVIEW_NOT_REQUIRED,
        ),
        (
            "review-preview",
            "run_review_preview",
            runbook_primary_flow.FLOW_REVIEW_PREVIEW,
            runbook_primary_flow.REVIEW_PREVIEW_NOT_REQUIRED,
            runbook_primary_flow.REVIEW_PREVIEW_REQUIRED,
        ),
    ],
)
def test_cli_stdout_matches_structured_pass_guidance(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    flow_arg: str,
    runner_name: str,
    primary_flow: str,
    next_action: str,
    forbidden: str,
) -> None:
    result = {
        "primary_flow": primary_flow,
        "runbook_day_id": "isolated",
        "runner_result": "PASS",
        "stopped_at": None,
        "stages": {},
        "next_required_action": next_action,
    }
    monkeypatch.setattr(runbook_primary_flow, runner_name, lambda *args, **kwargs: result)

    exit_code = runbook_primary_flow.main(
        [
            flow_arg,
            "--workspace",
            "isolated",
            "--account-id",
            ACCOUNT_ID,
            "--data-date",
            DATA_DATE,
            "--trade-date",
            TRADE_DATE,
        ]
    )
    stdout = capsys.readouterr().out

    assert exit_code == 0
    assert f'"next_required_action": "{next_action}"' in stdout
    assert f"STOP: {next_action}" in stdout
    assert forbidden not in stdout


def test_cli_blocked_exit_and_recovery_guidance_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    result = {
        "primary_flow": runbook_primary_flow.FLOW_EXECUTION_TO_REVIEW,
        "runbook_day_id": "isolated",
        "runner_result": "BLOCKED",
        "stopped_at": "GATE1",
        "stages": {"GATE1": {"runner_result": "BLOCKED"}},
        "recovery_command": "ops\\runbook_wrappers\\02_gate1_execution_input.cmd",
        "next_required_action": "Repair Gate1 before retry.",
    }
    monkeypatch.setattr(
        runbook_primary_flow,
        "run_execution_to_review_prep",
        lambda *args, **kwargs: result,
    )

    exit_code = runbook_primary_flow.main(
        [
            "execution-to-review-prep",
            "--workspace",
            "isolated",
            "--account-id",
            ACCOUNT_ID,
            "--data-date",
            DATA_DATE,
            "--trade-date",
            TRADE_DATE,
        ]
    )
    stdout = capsys.readouterr().out

    assert exit_code == 2
    assert "STOPPED_AT: GATE1" in stdout
    assert "Recovery: ops\\runbook_wrappers\\02_gate1_execution_input.cmd" in stdout
    assert "STOP: Fill Manual Review" not in stdout
    assert "STOP: No Manual Review" not in stdout
