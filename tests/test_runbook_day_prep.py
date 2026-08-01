from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest

from core import runbook_day_rollover as rollover_core
from core.runbook_calendar import load_market_calendar
from core.runbook_day_prep import (
    prepare_runbook_day_local,
    read_runbook_day_local,
    render_runbook_day_local,
)
from scripts import runbook_state


ACCOUNT_ID = "paper_pilot_202606"
NEXT_VALUES = {
    "DATA_DATE": "2026-07-02",
    "TRADE_DATE": "2026-07-06",
    "RUNBOOK_DAY_ID": f"{ACCOUNT_ID}_2026-07-02_2026-07-06",
}


@pytest.fixture(autouse=True)
def _patch_account_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    account_root = tmp_path / "outputs" / "paper_accounts" / ACCOUNT_ID
    monkeypatch.setattr(
        rollover_core,
        "build_paper_account_paths",
        lambda account_id, create=False: type("Paths", (), {"root": account_root})(),
    )


def _write_cmd(path: Path, lines: list[str]) -> None:
    path.write_bytes(("\r\n".join([*lines, ""])).encode("ascii"))


def _complete_state(workspace: Path, data_date: str = "2026-07-01", trade_date: str = "2026-07-02") -> None:
    state = runbook_state.create_initial_state(ACCOUNT_ID, data_date, trade_date)
    account_root = workspace.parent / "outputs" / "paper_accounts" / ACCOUNT_ID
    snapshot = account_root / "paper_account_snapshot.csv"
    benchmark_source = account_root / "reports" / "paper_benchmark_comparison.json"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    benchmark_source.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(f"account_id,snapshot_date\n{ACCOUNT_ID},{trade_date}\n", encoding="utf-8")
    benchmark_payload = {"account_id": ACCOUNT_ID, "latest_snapshot_date": trade_date, "run_mode": "exploratory"}
    benchmark_source.write_text(json.dumps(benchmark_payload), encoding="utf-8")
    command_dir = workspace / "command_runs" / state.runbook_day_id
    artifact_dir = workspace / "artifacts" / state.runbook_day_id / "stage_f"
    command_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "benchmark.json").write_text(json.dumps(benchmark_payload), encoding="utf-8")

    def command_result(
        command_key: str,
        step_id: int,
        raw_payload: dict[str, object],
        *,
        stage_id: str = "F",
    ) -> dict[str, object]:
        timestamp = "2026-07-02T18:00:00+09:00"
        return {
            "schema_version": "runbook_command_result.v1",
            "runner_result": "PASS",
            "created_at": timestamp,
            "updated_at": timestamp,
            "runbook_day_id": state.runbook_day_id,
            "frozen_context": {"account_id": ACCOUNT_ID, "data_date": data_date, "trade_date": trade_date},
            "stage_id": stage_id,
            "step_id": step_id,
            "command_key": command_key,
            "command_type": "NOTION_WRITE",
            "process": {"executed": True, "exit_code": 0, "duration_ms": 1},
            "outputs": {"json_ref": None, "txt_ref": None, "log_ref": None, "artifact_refs": {}},
            "summary": {"title": command_key, "message": "PASS", "warnings": [], "blockers": []},
            "raw_payload": raw_payload,
        }

    account_notion = command_dir / "account_notion.json"
    benchmark_notion = command_dir / "benchmark_notion.json"
    account_notion.write_text(
        json.dumps(command_result("account_snapshot_notion_upsert", 20, {"json": [{
            "account_id": ACCOUNT_ID,
            "external_key": f"account_snapshot:{ACCOUNT_ID}:{trade_date}",
            "action": "created",
            "source_path": str(snapshot),
            "failed_count": 0,
        }]})),
        encoding="utf-8",
    )
    benchmark_notion.write_text(
        json.dumps(command_result("benchmark_report_notion_upsert", 21, {"json": [{
            "account_id": ACCOUNT_ID,
            "external_key": f"benchmark:{ACCOUNT_ID}:{trade_date}:exploratory",
            "action": "created",
            "source_path": str(benchmark_source),
            "failed_count": 0,
        }]})),
        encoding="utf-8",
    )
    (command_dir / "eod_commit.json").write_text(
        json.dumps({
            "runner_result": "PASS",
            "status": "COMMITTED",
            "mode": "commit",
            "account_id": ACCOUNT_ID,
            "date": trade_date,
            "trade_date": trade_date,
            "failed_count": 0,
            "blocked_count": 0,
            "current_state_written": True,
            "account_snapshot_written": True,
            "position_snapshot_written": True,
            "market_valuation_status": "success",
        }),
        encoding="utf-8",
    )
    (command_dir / "final_status.json").write_text(
        json.dumps(command_result(
            "final_status",
            18,
            {
                "schema_version": "mfu_oper9_daily_ops_status.v1",
                "overall_status": "PASS",
                "account_id": ACCOUNT_ID,
                "data_date": data_date,
                "trade_date": trade_date,
                "workflow_status": "REVIEW_DONE",
                "completion_mode": "STANDARD",
                "completion_proof": None,
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
            },
            stage_id="E",
        )),
        encoding="utf-8",
    )
    state = replace(
        state,
        current_stage="F",
        current_status="PASS",
        last_completed_step=21,
        last_completed_stage="F",
        stage_status={stage_id: "PASS" for stage_id in runbook_state.STAGE_IDS},
        artifacts={
            "eod_commit_report_json": f"command_runs/{state.runbook_day_id}/eod_commit.json",
            "final_status_report_json": f"command_runs/{state.runbook_day_id}/final_status.json",
            "benchmark_report_json": f"artifacts/{state.runbook_day_id}/stage_f/benchmark.json",
            "account_snapshot_notion_report_json": f"command_runs/{state.runbook_day_id}/account_notion.json",
            "benchmark_notion_report_json": f"command_runs/{state.runbook_day_id}/benchmark_notion.json",
        },
    )
    runbook_state.save_state(
        state,
        runbook_state.get_state_path_for_context(workspace, ACCOUNT_ID, data_date, trade_date),
    )


def _account_local(path: Path, account_id: str = ACCOUNT_ID, mode: str = "PAPER") -> None:
    _write_cmd(
        path,
        [
            "@echo off",
            f'set "ACCOUNT_ID={account_id}"',
            f'set "ACCOUNT_MODE={mode}"',
            "exit /b 0",
        ],
    )


def _prep_fixture(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    workspace = tmp_path / "workspace"
    wrappers = tmp_path / "wrappers"
    workspace.mkdir()
    wrappers.mkdir(parents=True)
    _complete_state(workspace)
    machine = wrappers / "_machine.local.cmd"
    account = wrappers / "_account.local.cmd"
    day = wrappers / "_runbook_day.local.cmd"
    machine.write_bytes(b"machine unchanged\r\n")
    _account_local(account)
    return workspace, machine, account, day


def _prepare(workspace: Path, account: Path, day: Path, **kwargs):
    return prepare_runbook_day_local(
        workspace,
        ACCOUNT_ID,
        account,
        day,
        load_market_calendar(),
        write_env_local=True,
        confirm_paper_test=True,
        **kwargs,
    )


def test_prep_creates_only_runbook_day_local(tmp_path: Path) -> None:
    workspace, machine, account, day = _prep_fixture(tmp_path)
    machine_before = machine.read_bytes()
    account_before = account.read_bytes()

    result = _prepare(workspace, account, day)

    assert result["runner_result"] == "PASS"
    assert result["mode"] == "WRITE_RUNBOOK_DAY_LOCAL"
    assert read_runbook_day_local(day, account_id=ACCOUNT_ID) == NEXT_VALUES
    assert day.read_bytes() == render_runbook_day_local(NEXT_VALUES)
    assert machine.read_bytes() == machine_before
    assert account.read_bytes() == account_before


def test_identical_day_is_idempotent(tmp_path: Path) -> None:
    workspace, _machine, account, day = _prep_fixture(tmp_path)
    day.write_bytes(render_runbook_day_local(NEXT_VALUES))
    before = day.stat().st_mtime_ns

    result = _prepare(workspace, account, day)

    assert result["file_changed"] is False
    assert result["backup_created"] is False
    assert day.stat().st_mtime_ns == before


def test_old_day_is_backed_up_and_atomically_replaced(tmp_path: Path) -> None:
    workspace, _machine, account, day = _prep_fixture(tmp_path)
    old_values = {
        "DATA_DATE": "2026-07-01",
        "TRADE_DATE": "2026-07-02",
        "RUNBOOK_DAY_ID": f"{ACCOUNT_ID}_2026-07-01_2026-07-02",
    }
    old_content = render_runbook_day_local(old_values)
    day.write_bytes(old_content)

    result = _prepare(workspace, account, day)

    assert result["file_changed"] is True
    assert result["backup_created"] is True
    assert day.with_name("_runbook_day.local.cmd.bak").read_bytes() == old_content
    assert read_runbook_day_local(day, account_id=ACCOUNT_ID) == NEXT_VALUES


def test_temp_validation_failure_preserves_existing_day(tmp_path: Path) -> None:
    workspace, _machine, account, day = _prep_fixture(tmp_path)
    original = b"existing day\r\n"
    day.write_bytes(original)

    def fail_validation(_path: str | Path, **_kwargs) -> dict[str, str]:
        raise ValueError("injected_validation_failure")

    result = _prepare(workspace, account, day, validate_temp=fail_validation)

    assert result["runner_result"] == "BLOCKED"
    assert result["reason"] == "runbook_day_write_failed"
    assert day.read_bytes() == original
    assert not day.with_name("_runbook_day.local.cmd.tmp").exists()
    assert not day.with_name("_runbook_day.local.cmd.bak").exists()


def test_account_local_must_match_cli_and_paper_mode(tmp_path: Path) -> None:
    workspace, _machine, account, day = _prep_fixture(tmp_path)
    _account_local(account, account_id="paper_other")
    mismatch = _prepare(workspace, account, day)
    _account_local(account, mode="LIVE")
    wrong_mode = _prepare(workspace, account, day)

    assert mismatch["reason"] == "account_local_mismatch"
    assert wrong_mode["reason"] == "account_local_invalid"
    assert not day.exists()


def test_legacy_env_requires_manual_migration(tmp_path: Path) -> None:
    workspace, _machine, account, day = _prep_fixture(tmp_path)
    day.with_name("_env.local.cmd").write_bytes(b"legacy\r\n")

    result = _prepare(workspace, account, day)

    assert result["reason"] == "legacy_env_local_detected"
    assert "automatic migration is not supported" in result["blockers"][0]
    assert not day.exists()


def _loader_fixture(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    wrappers = tmp_path / "wrappers"
    repo = tmp_path / "repo"
    workspace = tmp_path / "workspace"
    fake_env = tmp_path / "fake_env"
    wrappers.mkdir(parents=True)
    repo.mkdir()
    workspace.mkdir()
    fake_env.mkdir()
    (fake_env / "python.exe").write_bytes(b"")
    loader = wrappers / "_env.cmd"
    loader.write_bytes(Path("ops/runbook_wrappers/_env.cmd").read_bytes())
    marker = tmp_path / "activated_env.txt"
    conda = tmp_path / "fake_conda.bat"
    _write_cmd(
        conda,
        [
            "@echo off",
            'if /I not "%~1"=="activate" exit /b 9',
            f'>"{marker}" echo %~2',
            'set "CONDA_DEFAULT_ENV=%~2"',
            f'set "CONDA_PREFIX={fake_env}"',
            "exit /b 0",
        ],
    )
    machine = wrappers / "_machine.local.cmd"
    _write_cmd(
        machine,
        [
            "@echo off",
            f'set "REPO_ROOT={repo}"',
            f'set "WORKSPACE={workspace}"',
            f'set "CONDA_BAT={conda}"',
            'set "CONDA_ENV_NAME=HANTU311_64"',
            'set "PAUSE_ON_EXIT=0"',
            'set "PYTHONUTF8=1"',
            'set "PYTHONIOENCODING=utf-8"',
            "exit /b 0",
        ],
    )
    account = wrappers / "_account.local.cmd"
    _account_local(account)
    day = wrappers / "_runbook_day.local.cmd"
    day.write_bytes(render_runbook_day_local(NEXT_VALUES))
    return loader, {
        "machine": machine,
        "account": account,
        "day": day,
        "repo": repo,
        "workspace": workspace,
        "conda": conda,
        "marker": marker,
    }


def _run_loader(loader: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["cmd.exe", "/d", "/c", str(loader)],
        capture_output=True,
        text=True,
        check=False,
    )


def test_loader_loads_three_files_and_uses_configured_conda_name(tmp_path: Path) -> None:
    loader, paths = _loader_fixture(tmp_path)

    completed = _run_loader(loader)

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert paths["marker"].read_text(encoding="ascii").strip() == "HANTU311_64"


@pytest.mark.parametrize("missing_key", ["machine", "account", "day"])
def test_loader_missing_local_fails_before_conda(tmp_path: Path, missing_key: str) -> None:
    loader, paths = _loader_fixture(tmp_path)
    paths[missing_key].unlink()

    completed = _run_loader(loader)

    assert completed.returncode != 0
    assert not paths["marker"].exists()


@pytest.mark.parametrize("failing_key", ["machine", "account", "day"])
def test_loader_nonzero_local_fails_before_conda(tmp_path: Path, failing_key: str) -> None:
    loader, paths = _loader_fixture(tmp_path)
    _write_cmd(paths[failing_key], ["@echo off", "exit /b 7"])

    completed = _run_loader(loader)

    assert completed.returncode == 7
    assert not paths["marker"].exists()


def test_loader_blocks_missing_variable_mode_and_id_mismatch(tmp_path: Path) -> None:
    loader, paths = _loader_fixture(tmp_path)
    content = paths["machine"].read_text(encoding="ascii").replace('set "PYTHONUTF8=1"\n', "")
    paths["machine"].write_text(content, encoding="ascii")
    missing = _run_loader(loader)

    loader, paths = _loader_fixture(tmp_path / "mode")
    _account_local(paths["account"], mode="LIVE")
    mode = _run_loader(loader)

    loader, paths = _loader_fixture(tmp_path / "id")
    wrong = dict(NEXT_VALUES)
    wrong["RUNBOOK_DAY_ID"] = "wrong"
    paths["day"].write_bytes(render_runbook_day_local(wrong))
    mismatch = _run_loader(loader)

    assert missing.returncode != 0
    assert mode.returncode != 0
    assert mismatch.returncode != 0


@pytest.mark.parametrize("invalid_key", ["repo", "workspace", "conda"])
def test_loader_blocks_invalid_paths_before_activation(tmp_path: Path, invalid_key: str) -> None:
    loader, paths = _loader_fixture(tmp_path)
    paths[invalid_key].rename(paths[invalid_key].with_name(f"missing_{invalid_key}"))

    completed = _run_loader(loader)

    assert completed.returncode != 0
    assert not paths["marker"].exists()


def test_templates_are_not_fallbacks_and_wrappers_only_call_loader(tmp_path: Path) -> None:
    loader, paths = _loader_fixture(tmp_path)
    paths["machine"].unlink()
    (loader.parent / "_machine.template.cmd").write_bytes(
        Path("ops/runbook_wrappers/_machine.template.cmd").read_bytes()
    )

    completed = _run_loader(loader)

    assert completed.returncode != 0
    wrappers = sorted(Path("ops/runbook_wrappers").glob("0[1-9]_*.cmd"))
    assert len(wrappers) == 9
    for wrapper in wrappers:
        content = wrapper.read_text(encoding="utf-8")
        assert 'call "%~dp0_env.cmd"' in content
        assert ".local.cmd" not in content


def test_actual_local_files_are_ignored_and_untracked() -> None:
    local_names = [
        "_machine.local.cmd",
        "_account.local.cmd",
        "_runbook_day.local.cmd",
        "_runbook_day.local.cmd.tmp",
        "_runbook_day.local.cmd.bak",
    ]
    paths = [Path("ops/runbook_wrappers") / name for name in local_names]

    ignored = subprocess.run(
        ["git", "check-ignore", *map(str, paths)],
        capture_output=True,
        text=True,
        check=False,
    )
    tracked = subprocess.run(
        ["git", "ls-files", *map(str, paths)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert ignored.returncode == 0
    assert len(ignored.stdout.splitlines()) == len(paths)
    assert tracked.stdout.strip() == ""
