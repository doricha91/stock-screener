from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"
DATA_DATE = "2026-06-12"
TRADE_DATE = "2026-06-15"


def test_initial_state_has_frozen_context() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert state.frozen_context.account_id == ACCOUNT_ID
    assert state.frozen_context.data_date == DATA_DATE
    assert state.frozen_context.trade_date == TRADE_DATE
    assert state.timezone == "Asia/Seoul"


def test_runbook_day_id_uses_account_data_date_and_trade_date() -> None:
    assert (
        runbook_state.get_runbook_day_id(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
        == "paper_pilot_202606_2026-06-12_2026-06-15"
    )


def test_initial_state_defaults() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert state.current_stage == "A"
    assert state.current_status in {"READY", "PENDING"}
    assert state.last_completed_step is None
    assert state.last_completed_stage is None
    assert set(state.stage_status) == {"A", "GATE1", "B", "GATE2", "C"}
    assert all(status == "PENDING" for status in state.stage_status.values())


def test_validate_initial_state_returns_no_errors() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert runbook_state.validate_state(state) == []


def test_save_state_then_load_state_round_trips(tmp_path: Path) -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    path = tmp_path / "runbook_state.json"

    runbook_state.save_state(state, path)
    loaded = runbook_state.load_state(path)

    assert loaded == state


def test_same_context_init_keeps_existing_state(tmp_path: Path) -> None:
    result, state = runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    modified_state = replace(state, current_status="WAIT")
    runbook_state.save_state(modified_state, tmp_path / "runbook_state.json")

    second_result, second_state = runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert result == "CREATED"
    assert second_result == "EXISTING"
    assert second_state.current_status == "WAIT"


def test_different_context_init_does_not_overwrite(tmp_path: Path) -> None:
    _, state = runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    path = tmp_path / "runbook_state.json"

    try:
        runbook_state.init_state_file(tmp_path, ACCOUNT_ID, "2026-06-13", TRADE_DATE)
    except ValueError as exc:
        assert str(exc) == "context_mismatch_existing_runbook_state"
    else:
        raise AssertionError("expected context mismatch to raise")

    assert runbook_state.load_state(path) == state


def test_context_matches_state() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    assert runbook_state.context_matches_state(state, ACCOUNT_ID, DATA_DATE, TRADE_DATE) is True
    assert runbook_state.context_matches_state(state, ACCOUNT_ID, "2026-06-13", TRADE_DATE) is False
    assert runbook_state.context_matches_state(state, "other_account", DATA_DATE, TRADE_DATE) is False


def test_validate_state_reports_schema_errors() -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    broken = replace(state, schema_version="bad", current_stage="Z", last_completed_step=99)

    errors = runbook_state.validate_state(broken)

    assert "schema_version must be runbook_state.v1" in errors
    assert "current_stage must be one of A/GATE1/B/GATE2/C" in errors
    assert "last_completed_step must be null or 0..18" in errors


def test_init_cli_creates_state_file(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_state.py",
            "init",
            "--workspace",
            str(tmp_path),
            "--account-id",
            ACCOUNT_ID,
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

    assert completed.returncode == 0
    assert (tmp_path / "runbook_state.json").exists()
    assert json.loads(completed.stdout)["runner_result"] == "PASS"


def test_show_and_validate_cli(tmp_path: Path) -> None:
    runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)
    root = Path(__file__).resolve().parents[1]

    show = subprocess.run(
        [sys.executable, "scripts\\runbook_state.py", "show", "--workspace", str(tmp_path)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )
    validate = subprocess.run(
        [sys.executable, "scripts\\runbook_state.py", "validate", "--workspace", str(tmp_path)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=False,
    )

    assert show.returncode == 0
    assert json.loads(show.stdout)["runbook_day_id"] == "paper_pilot_202606_2026-06-12_2026-06-15"
    assert validate.returncode == 0
    assert json.loads(validate.stdout)["runner_result"] == "PASS"


def test_context_mismatch_init_cli_returns_nonzero_and_does_not_overwrite(tmp_path: Path) -> None:
    runbook_state.init_state_file(tmp_path, ACCOUNT_ID, DATA_DATE, TRADE_DATE)

    completed = subprocess.run(
        [
            sys.executable,
            "scripts\\runbook_state.py",
            "init",
            "--workspace",
            str(tmp_path),
            "--account-id",
            ACCOUNT_ID,
            "--data-date",
            "2026-06-13",
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
    assert json.loads(completed.stdout) == {
        "runner_result": "BLOCKED",
        "reason": "context_mismatch_existing_runbook_state",
    }
    loaded = runbook_state.load_state(tmp_path / "runbook_state.json")
    assert loaded.frozen_context.data_date == DATA_DATE
