from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

from core.runbook_calendar import CalendarCoverageError, load_market_calendar
from core.runbook_day_rollover import preview_rollover
from scripts import runbook_day_rollover, runbook_state


ACCOUNT_ID = "paper_pilot_202606"


def _complete_state(workspace: Path, data_date: str, trade_date: str) -> Path:
    state = runbook_state.create_initial_state(ACCOUNT_ID, data_date, trade_date)
    state = replace(
        state,
        current_stage="E",
        current_status="PASS",
        last_completed_step=18,
        last_completed_stage="E",
        stage_status={stage_id: "PASS" for stage_id in runbook_state.STAGE_IDS},
        artifacts={"final_status_report_json": f"command_runs/{state.runbook_day_id}/final_status.json"},
    )
    path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, data_date, trade_date)
    runbook_state.save_state(state, path)
    return path


def _active_state(workspace: Path, data_date: str, trade_date: str) -> Path:
    state = runbook_state.create_initial_state(ACCOUNT_ID, data_date, trade_date)
    path = runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, data_date, trade_date)
    runbook_state.save_state(state, path)
    return path


def test_calendar_returns_next_ordinary_weekday() -> None:
    calendar = load_market_calendar()
    assert calendar.next_trading_day(date(2026, 7, 6)) == date(2026, 7, 7)


def test_calendar_skips_friday_to_monday() -> None:
    calendar = load_market_calendar()
    assert calendar.next_trading_day(date(2026, 7, 10)) == date(2026, 7, 13)


def test_calendar_skips_weekend() -> None:
    calendar = load_market_calendar()
    assert calendar.is_trading_day(date(2026, 7, 11)) is False
    assert calendar.is_trading_day(date(2026, 7, 12)) is False


def test_calendar_skips_us_market_holiday() -> None:
    calendar = load_market_calendar()
    assert calendar.next_trading_day(date(2026, 7, 2)) == date(2026, 7, 6)


def test_previous_trade_date_becomes_next_data_date(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-01", "2026-07-02")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result == {
        "runner_result": "PASS",
        "mode": "PREVIEW",
        "account_id": ACCOUNT_ID,
        "previous_runbook_day_id": f"{ACCOUNT_ID}_2026-07-01_2026-07-02",
        "next_data_date": "2026-07-02",
        "next_trade_date": "2026-07-06",
        "next_runbook_day_id": f"{ACCOUNT_ID}_2026-07-02_2026-07-06",
        "already_exists": False,
        "safe_to_prepare": True,
        "next_required_action": "Run 6-4C to prepare the local runbook environment.",
    }


def test_active_incomplete_day_blocks_rollover(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-01", "2026-07-02")
    _active_state(workspace, "2026-07-02", "2026-07-06")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"
    assert result["safe_to_prepare"] is False


def test_missing_completed_day_blocks_without_bootstrap(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / runbook_state.STATE_DIRNAME).mkdir()

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "completed_runbook_day_not_found"


def test_multiple_active_days_are_blocked(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-01", "2026-07-02")
    _active_state(workspace, "2026-07-02", "2026-07-06")
    _active_state(workspace, "2026-07-06", "2026-07-07")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "multiple_active_runbook_days"
    assert len(result["blockers"]) == 2


def test_tied_latest_completed_days_are_blocked(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-06-30", "2026-07-02")
    _complete_state(workspace, "2026-07-01", "2026-07-02")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "latest_completed_runbook_day_ambiguous"


def test_calculated_data_date_cannot_move_backward(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-03", "2026-07-02")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "calculated_dates_move_backward"


def test_target_account_state_filename_mismatch_blocks_rollover(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    valid_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    mismatched_path = valid_path.with_name("wrong_filename.json")
    valid_path.replace(mismatched_path)

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "invalid_runbook_state"
    assert result["blockers"] == ["state_filename_mismatch:wrong_filename.json"]


def test_existing_next_runbook_artifact_is_detected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-01", "2026-07-02")
    duplicate_dir = workspace / "artifacts" / f"{ACCOUNT_ID}_2026-07-02_2026-07-06"
    duplicate_dir.mkdir(parents=True)

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "PASS"
    assert result["already_exists"] is True
    assert result["safe_to_prepare"] is False


def test_calendar_coverage_exceeded_blocks_rollover(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2027-12-30", "2027-12-31")

    result = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "calendar_coverage_exceeded"


def test_calendar_rejects_direct_out_of_coverage_query() -> None:
    calendar = load_market_calendar()
    try:
        calendar.is_trading_day(date(2028, 1, 3))
    except CalendarCoverageError as exc:
        assert "calendar_coverage_exceeded" in str(exc)
    else:
        raise AssertionError("Expected CalendarCoverageError")


def test_invalid_workspace_and_account_are_blocked(tmp_path: Path) -> None:
    calendar = load_market_calendar()
    invalid_workspace = preview_rollover(
        tmp_path / "missing",
        ACCOUNT_ID,
        calendar,
        confirm_paper_test=True,
    )
    invalid_account = preview_rollover(
        tmp_path,
        "live_account",
        calendar,
        confirm_paper_test=True,
    )

    assert invalid_workspace["reason"] == "invalid_workspace"
    assert invalid_account["reason"] == "paper_account_required"


def test_repeated_preview_is_identical_and_read_only(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    state_path = _complete_state(workspace, "2026-07-01", "2026-07-02")
    artifact = workspace / "existing_artifact.json"
    artifact.write_text('{"unchanged": true}\n', encoding="utf-8")
    before_state = state_path.read_bytes()
    before_artifact = artifact.read_bytes()

    first = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)
    second = preview_rollover(workspace, ACCOUNT_ID, load_market_calendar(), confirm_paper_test=True)

    assert first == second
    assert state_path.read_bytes() == before_state
    assert artifact.read_bytes() == before_artifact
    assert sorted(path.relative_to(workspace) for path in workspace.rglob("*")) == [
        Path("existing_artifact.json"),
        Path("runbook_states"),
        Path("runbook_states") / state_path.name,
    ]


def test_cli_exit_codes_match_pass_and_blocked(tmp_path: Path, capsys) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    _complete_state(workspace, "2026-07-01", "2026-07-02")

    pass_code = runbook_day_rollover.main(
        ["--workspace", str(workspace), "--account-id", ACCOUNT_ID, "--confirm-paper-test"]
    )
    pass_payload = json.loads(capsys.readouterr().out)
    blocked_code = runbook_day_rollover.main(
        ["--workspace", str(workspace), "--account-id", ACCOUNT_ID]
    )
    blocked_payload = json.loads(capsys.readouterr().out)

    assert pass_code == 0
    assert pass_payload["runner_result"] == "PASS"
    assert blocked_code == 2
    assert blocked_payload["reason"] == "paper_test_confirmation_required"
