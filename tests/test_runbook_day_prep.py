from __future__ import annotations

import subprocess
from dataclasses import replace
from pathlib import Path

from core.runbook_calendar import load_market_calendar
from core.runbook_day_prep import prepare_env_local, read_env_local, render_env_local
from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-07-01"
TRADE_DATE = "2026-07-02"
NEXT_VALUES = {
    "ACCOUNT_ID": ACCOUNT_ID,
    "DATA_DATE": "2026-07-02",
    "TRADE_DATE": "2026-07-06",
    "RUNBOOK_DAY_ID": f"{ACCOUNT_ID}_2026-07-02_2026-07-06",
}


def _complete_state(workspace: Path, data_date: str = DATA_DATE, trade_date: str = TRADE_DATE) -> Path:
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


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    workspace = tmp_path / "workspace"
    wrappers = tmp_path / "wrappers"
    workspace.mkdir()
    wrappers.mkdir()
    _complete_state(workspace)
    return workspace, wrappers / "_env.local.cmd"


def _prepare(workspace: Path, env_path: Path, **kwargs):
    return prepare_env_local(
        workspace,
        ACCOUNT_ID,
        env_path,
        load_market_calendar(),
        write_env_local=True,
        confirm_paper_test=True,
        **kwargs,
    )


def test_rollover_pass_creates_local_env_with_exact_values(tmp_path: Path) -> None:
    workspace, env_path = _paths(tmp_path)

    result = _prepare(workspace, env_path)

    assert result["runner_result"] == "PASS"
    assert result["file_changed"] is True
    assert result["backup_created"] is False
    assert read_env_local(env_path) == NEXT_VALUES
    assert env_path.read_bytes() == render_env_local(NEXT_VALUES)
    assert result["runbook_day_id"] == NEXT_VALUES["RUNBOOK_DAY_ID"]


def test_identical_existing_env_is_idempotent(tmp_path: Path) -> None:
    workspace, env_path = _paths(tmp_path)
    env_path.write_bytes(render_env_local(NEXT_VALUES))
    before = env_path.stat().st_mtime_ns

    result = _prepare(workspace, env_path)

    assert result["runner_result"] == "PASS"
    assert result["file_changed"] is False
    assert result["backup_created"] is False
    assert env_path.stat().st_mtime_ns == before
    assert not env_path.with_name("_env.local.cmd.bak").exists()


def test_existing_old_date_is_backed_up_then_replaced(tmp_path: Path) -> None:
    workspace, env_path = _paths(tmp_path)
    old_values = {
        "ACCOUNT_ID": ACCOUNT_ID,
        "DATA_DATE": "2026-07-01",
        "TRADE_DATE": "2026-07-02",
        "RUNBOOK_DAY_ID": f"{ACCOUNT_ID}_2026-07-01_2026-07-02",
    }
    old_content = render_env_local(old_values)
    env_path.write_bytes(old_content)

    result = _prepare(workspace, env_path)

    assert result["runner_result"] == "PASS"
    assert result["file_changed"] is True
    assert result["backup_created"] is True
    assert env_path.with_name("_env.local.cmd.bak").read_bytes() == old_content
    assert read_env_local(env_path) == NEXT_VALUES


def test_active_runbook_day_blocks_without_changing_env(tmp_path: Path) -> None:
    workspace, env_path = _paths(tmp_path)
    original = b"existing local file\r\n"
    env_path.write_bytes(original)
    _active_state(workspace, "2026-07-02", "2026-07-06")

    result = _prepare(workspace, env_path)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "active_runbook_day_exists"
    assert env_path.read_bytes() == original


def test_duplicate_next_runbook_day_blocks_without_changing_env(tmp_path: Path) -> None:
    workspace, env_path = _paths(tmp_path)
    original = b"existing local file\r\n"
    env_path.write_bytes(original)
    (workspace / "artifacts" / NEXT_VALUES["RUNBOOK_DAY_ID"]).mkdir(parents=True)

    result = _prepare(workspace, env_path)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "rollover_not_safe_to_prepare"
    assert env_path.read_bytes() == original


def test_calendar_coverage_blocks_without_changing_env(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    wrappers = tmp_path / "wrappers"
    workspace.mkdir()
    wrappers.mkdir()
    _complete_state(workspace, "2027-12-30", "2027-12-31")
    env_path = wrappers / "_env.local.cmd"
    original = b"existing local file\r\n"
    env_path.write_bytes(original)

    result = _prepare(workspace, env_path)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "calendar_coverage_exceeded"
    assert env_path.read_bytes() == original


def test_missing_confirm_flag_blocks_without_creating_env(tmp_path: Path) -> None:
    workspace, env_path = _paths(tmp_path)

    result = prepare_env_local(
        workspace,
        ACCOUNT_ID,
        env_path,
        load_market_calendar(),
        write_env_local=True,
        confirm_paper_test=False,
    )

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "paper_test_confirmation_required"
    assert not env_path.exists()


def test_missing_write_flag_blocks_without_creating_env(tmp_path: Path) -> None:
    workspace, env_path = _paths(tmp_path)

    result = prepare_env_local(
        workspace,
        ACCOUNT_ID,
        env_path,
        load_market_calendar(),
        write_env_local=False,
        confirm_paper_test=True,
    )

    assert result["reason"] == "write_env_local_confirmation_required"
    assert not env_path.exists()


def test_invalid_account_and_workspace_are_blocked(tmp_path: Path) -> None:
    workspace, env_path = _paths(tmp_path)
    invalid_account = prepare_env_local(
        workspace,
        "live_account",
        env_path,
        load_market_calendar(),
        write_env_local=True,
        confirm_paper_test=True,
    )
    invalid_workspace = prepare_env_local(
        tmp_path / "missing",
        ACCOUNT_ID,
        env_path,
        load_market_calendar(),
        write_env_local=True,
        confirm_paper_test=True,
    )

    assert invalid_account["reason"] == "paper_account_required"
    assert invalid_workspace["reason"] == "invalid_workspace"
    assert not env_path.exists()


def test_temp_validation_failure_preserves_original(tmp_path: Path) -> None:
    workspace, env_path = _paths(tmp_path)
    original = b"existing local file\r\n"
    env_path.write_bytes(original)

    def fail_validation(_path: str | Path) -> dict[str, str]:
        raise ValueError("injected_validation_failure")

    result = _prepare(workspace, env_path, validate_temp=fail_validation)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "env_local_write_failed"
    assert env_path.read_bytes() == original
    assert not env_path.with_name("_env.local.cmd.tmp").exists()
    assert not env_path.with_name("_env.local.cmd.bak").exists()


def test_env_loader_fails_before_conda_when_local_file_is_missing(tmp_path: Path) -> None:
    source = Path("ops/runbook_wrappers/_env.cmd")
    copied = tmp_path / "_env.cmd"
    copied.write_bytes(source.read_bytes())

    completed = subprocess.run(
        ["cmd.exe", "/d", "/c", str(copied)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert "Required local environment file not found" in completed.stdout


def test_wrappers_still_call_tracked_env_loader() -> None:
    wrappers = sorted(Path("ops/runbook_wrappers").glob("0*.cmd"))

    assert len(wrappers) == 9
    for wrapper in wrappers:
        content = wrapper.read_text(encoding="utf-8")
        assert 'call "%~dp0_env.cmd"' in content
        assert "_env.local.cmd" not in content

    loader = Path("ops/runbook_wrappers/_env.cmd").read_text(encoding="utf-8")
    assert 'set "EXPECTED_RUNBOOK_DAY_ID=%ACCOUNT_ID%_%DATA_DATE%_%TRADE_DATE%"' in loader
    assert 'if not "%RUNBOOK_DAY_ID%"=="%EXPECTED_RUNBOOK_DAY_ID%"' in loader
