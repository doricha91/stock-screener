from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import runbook_command_registry as registry
from scripts import runbook_gate_checker
from scripts import runbook_result
from scripts import runbook_state
from scripts.runbook_command_registry import RunbookCommand
from scripts.runbook_state import RunbookState


STAGE_A_ID = "A"
STAGE_B_ID = "B"
STAGE_C_ID = "C"
STAGE_D_ID = "D"
STAGE_D_PREVIEW_ID = "D_PREVIEW"
STAGE_E_ID = "E"
STAGE_A_STEP_IDS = tuple(range(0, 6))
STAGE_B_STEP_IDS = (7, 8, 9)
STAGE_C_STEP_IDS = (10, 11)
STAGE_D_PREVIEW_STEP_IDS = (13,)
STAGE_D_APPEND_STEP_IDS = (14, 15)
STAGE_E_STEP_IDS = (16, 17, 18)
DEFAULT_TIMEOUT_SEC = 1800


def render_argv_template(
    command: RunbookCommand,
    frozen_context: runbook_state.FrozenRunbookContext,
    artifact_refs: dict[str, str] | None = None,
) -> list[str]:
    values: dict[str, str] = {
        "account_id": frozen_context.account_id,
        "data_date": frozen_context.data_date,
        "trade_date": frozen_context.trade_date,
    }
    values.update(artifact_refs or {})
    rendered: list[str] = []
    for part in command.argv_template:
        try:
            rendered.append(part.format(**values))
        except KeyError as exc:
            raise ValueError(f"missing template value: {exc.args[0]}") from exc
    return rendered


def normalize_python_script_argv(argv: Sequence[str], repo_root: Path) -> list[str]:
    if not argv:
        raise ValueError("argv is required")
    first = str(argv[0])
    first_path = Path(first)
    normalized_first = first.replace("/", "\\")
    if normalized_first.startswith("scripts\\") and first_path.suffix == ".py":
        script_path = repo_root / first_path
        return [sys.executable, str(script_path), *[str(part) for part in argv[1:]]]
    return [str(part) for part in argv]


def run_allowlisted_command(argv: list[str], cwd: Path, timeout_sec: int = DEFAULT_TIMEOUT_SEC) -> dict[str, Any]:
    if not argv:
        raise ValueError("argv is required")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_sec,
            shell=False,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "executed": True,
            "exit_code": completed.returncode,
            "duration_ms": duration_ms,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.perf_counter() - started) * 1000)
        return {
            "executed": True,
            "exit_code": 124,
            "duration_ms": duration_ms,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or f"Command timed out after {timeout_sec} seconds.",
            "timed_out": True,
        }


def get_stage_a_commands(commands: Sequence[RunbookCommand] | None = None) -> list[RunbookCommand]:
    selected = [
        command
        for command in (commands or registry.list_commands())
        if command.step_id in STAGE_A_STEP_IDS
    ]
    selected.sort(key=lambda command: command.step_id)
    validate_stage_a_commands(selected)
    return selected


def get_stage_b_commands(commands: Sequence[RunbookCommand] | None = None) -> list[RunbookCommand]:
    selected = [
        command
        for command in (commands or registry.list_commands())
        if command.step_id in STAGE_B_STEP_IDS
    ]
    selected.sort(key=lambda command: command.step_id)
    validate_stage_b_commands(selected)
    return selected


def get_stage_c_commands(commands: Sequence[RunbookCommand] | None = None) -> list[RunbookCommand]:
    selected = [
        command
        for command in (commands or registry.list_commands())
        if command.step_id in STAGE_C_STEP_IDS
    ]
    selected.sort(key=lambda command: command.step_id)
    validate_stage_c_commands(selected)
    return selected


def get_stage_d_preview_commands(commands: Sequence[RunbookCommand] | None = None) -> list[RunbookCommand]:
    selected = [
        command
        for command in (commands or registry.list_commands())
        if command.step_id in STAGE_D_PREVIEW_STEP_IDS
    ]
    selected.sort(key=lambda command: command.step_id)
    validate_stage_d_preview_commands(selected)
    return selected


def get_stage_d_append_commands(commands: Sequence[RunbookCommand] | None = None) -> list[RunbookCommand]:
    selected = [
        command
        for command in (commands or registry.list_commands())
        if command.step_id in STAGE_D_APPEND_STEP_IDS
    ]
    selected.sort(key=lambda command: command.step_id)
    validate_stage_d_append_commands(selected)
    return selected


def get_stage_e_commands(commands: Sequence[RunbookCommand] | None = None) -> list[RunbookCommand]:
    selected = [
        command
        for command in (commands or registry.list_commands())
        if command.step_id in STAGE_E_STEP_IDS
    ]
    selected.sort(key=lambda command: command.step_id)
    validate_stage_e_commands(selected)
    return selected


def validate_stage_a_commands(commands: Sequence[RunbookCommand]) -> None:
    step_ids = [command.step_id for command in commands]
    if step_ids != list(STAGE_A_STEP_IDS):
        raise ValueError(f"Stage A commands must cover steps 0..5 in order, found {step_ids}")
    for command in commands:
        if command.stage_id != STAGE_A_ID:
            raise ValueError(f"Stage A command has invalid stage_id: {command.command_key}")
        if not command.phase1_auto_execute:
            raise ValueError(f"Stage A command is not phase1 auto executable: {command.command_key}")
        if command.manual_gate:
            raise ValueError(f"Stage A command cannot be a manual gate: {command.command_key}")
        if not command.argv_template:
            raise ValueError(f"Stage A command argv_template is required: {command.command_key}")


def validate_stage_b_commands(commands: Sequence[RunbookCommand]) -> None:
    step_ids = [command.step_id for command in commands]
    if step_ids != list(STAGE_B_STEP_IDS):
        raise ValueError(f"Stage B commands must cover steps 7..9 in order, found {step_ids}")
    for command in commands:
        if command.stage_id != STAGE_B_ID:
            raise ValueError(f"Stage B command has invalid stage_id: {command.command_key}")
        if not command.phase1_auto_execute:
            raise ValueError(f"Stage B command is not phase1 auto executable: {command.command_key}")
        if command.manual_gate:
            raise ValueError(f"Stage B command cannot be a manual gate: {command.command_key}")
        if not command.argv_template:
            raise ValueError(f"Stage B command argv_template is required: {command.command_key}")


def validate_stage_c_commands(commands: Sequence[RunbookCommand]) -> None:
    step_ids = [command.step_id for command in commands]
    if step_ids != list(STAGE_C_STEP_IDS):
        raise ValueError(f"Stage C commands must cover steps 10..11 in order, found {step_ids}")
    for command in commands:
        if command.stage_id != STAGE_C_ID:
            raise ValueError(f"Stage C command has invalid stage_id: {command.command_key}")
        if not command.phase1_auto_execute:
            raise ValueError(f"Stage C command is not phase1 auto executable: {command.command_key}")
        if command.manual_gate:
            raise ValueError(f"Stage C command cannot be a manual gate: {command.command_key}")
        if not command.argv_template:
            raise ValueError(f"Stage C command argv_template is required: {command.command_key}")


def validate_stage_d_preview_commands(commands: Sequence[RunbookCommand]) -> None:
    step_ids = [command.step_id for command in commands]
    if step_ids != list(STAGE_D_PREVIEW_STEP_IDS):
        raise ValueError(f"Stage D preview commands must cover Step 13 only, found {step_ids}")
    for command in commands:
        if command.stage_id != STAGE_D_ID:
            raise ValueError(f"Stage D preview command has invalid stage_id: {command.command_key}")
        if not command.phase1_auto_execute:
            raise ValueError(f"Stage D preview command is not phase1 auto executable: {command.command_key}")
        if command.manual_gate:
            raise ValueError(f"Stage D preview command cannot be a manual gate: {command.command_key}")
        if not command.argv_template:
            raise ValueError(f"Stage D preview command argv_template is required: {command.command_key}")


def validate_stage_d_append_commands(commands: Sequence[RunbookCommand]) -> None:
    step_ids = [command.step_id for command in commands]
    if step_ids != list(STAGE_D_APPEND_STEP_IDS):
        raise ValueError(f"Stage D append commands must cover Step 14-15 only, found {step_ids}")
    for command in commands:
        if command.stage_id != STAGE_D_ID:
            raise ValueError(f"Stage D append command has invalid stage_id: {command.command_key}")
        if not command.phase1_auto_execute:
            raise ValueError(f"Stage D append command is not phase1 auto executable: {command.command_key}")
        if command.manual_gate:
            raise ValueError(f"Stage D append command cannot be a manual gate: {command.command_key}")
        if not command.argv_template:
            raise ValueError(f"Stage D append command argv_template is required: {command.command_key}")


def validate_stage_e_commands(commands: Sequence[RunbookCommand]) -> None:
    step_ids = [command.step_id for command in commands]
    if step_ids != list(STAGE_E_STEP_IDS):
        raise ValueError(f"Stage E commands must cover Step 16-18 only, found {step_ids}")
    for command in commands:
        if command.stage_id != STAGE_E_ID:
            raise ValueError(f"Stage E command has invalid stage_id: {command.command_key}")
        if not command.phase1_auto_execute:
            raise ValueError(f"Stage E command is not phase1 auto executable: {command.command_key}")
        if command.manual_gate:
            raise ValueError(f"Stage E command cannot be a manual gate: {command.command_key}")
        if not command.argv_template:
            raise ValueError(f"Stage E command argv_template is required: {command.command_key}")


def run_stage_a(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
    dry_run: bool = False,
    confirm_paper_test: bool = False,
    repo_root: Path | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    commands: Sequence[RunbookCommand] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace)
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    guard_error = _paper_smoke_guard(account_id, dry_run, confirm_paper_test)
    if guard_error:
        return {
            "runner_result": "BLOCKED",
            "stage_id": STAGE_A_ID,
            "reason": guard_error,
            "dry_run": dry_run,
            "paper_test_confirmed": confirm_paper_test,
        }
    try:
        _, state_path, state = runbook_state.init_state_file_for_context(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone,
        )
    except ValueError as exc:
        return {
            "runner_result": "BLOCKED",
            "stage_id": STAGE_A_ID,
            "reason": str(exc),
            "dry_run": dry_run,
            "paper_test_confirmed": confirm_paper_test,
        }

    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        state = runbook_state.block_stage(state, STAGE_A_ID, "context_mismatch_existing_runbook_state")
        runbook_state.save_state(state, state_path)
        return {
            "runner_result": "BLOCKED",
            "stage_id": STAGE_A_ID,
            "runbook_day_id": state.runbook_day_id,
            "reason": "context_mismatch_existing_runbook_state",
            "dry_run": dry_run,
            "paper_test_confirmed": confirm_paper_test,
        }

    stage_commands = get_stage_a_commands(commands)
    state = runbook_state.start_stage(state, STAGE_A_ID)
    runbook_state.save_state(state, state_path)

    command_results: list[dict[str, Any]] = []
    stage_result = "PASS"
    for command in stage_commands:
        command_result, log_text = _run_stage_a_command(
            state,
            workspace,
            repo_root,
            command,
            dry_run,
            timeout_sec,
        )
        command_json_path, command_txt_path = runbook_result.write_command_result(
            workspace,
            state,
            command,
            command_result,
        )
        _write_command_log(workspace, command_json_path, log_text)
        command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
        command_results.append(command_result)

        runner_result = command_result["runner_result"]
        if runner_result == "PASS":
            state = runbook_state.complete_step(
                state,
                command.step_id,
                STAGE_A_ID,
                command_result.get("outputs", {}).get("artifact_refs", {}),
                workspace,
            )
            runbook_state.save_state(state, state_path)
            continue

        if runner_result == "BLOCKED":
            stage_result = "BLOCKED"
            state = runbook_state.block_stage(
                state,
                STAGE_A_ID,
                f"stage_a_step_blocked:{command.command_key}",
                {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
            )
        else:
            stage_result = "FAILED"
            state = runbook_state.fail_stage(
                state,
                STAGE_A_ID,
                f"stage_a_step_failed:{command.command_key}",
                {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
            )
        runbook_state.save_state(state, state_path)
        break

    if stage_result == "PASS":
        state = runbook_state.complete_stage(state, STAGE_A_ID)
        runbook_state.save_state(state, state_path)

    stage_summary = runbook_result.create_stage_summary(
        state,
        STAGE_A_ID,
        command_results,
        next_required_action=(
            "Wait for Step 6 manual execution input."
            if stage_result == "PASS"
            else "Inspect failed Stage A command result before retry."
        ),
        next_stage="GATE1" if stage_result == "PASS" else None,
    )
    stage_summary_json, stage_summary_txt = runbook_result.write_stage_summary(
        workspace,
        state,
        stage_summary,
    )
    stage_summary_paths = runbook_result.get_stage_summary_paths(
        workspace,
        state.runbook_day_id,
        STAGE_A_ID,
        timestamp=Path(stage_summary_json).name.rsplit("_", 1)[0],
    )

    return {
        "runner_result": stage_summary["runner_result"],
        "stage_id": STAGE_A_ID,
        "runbook_day_id": state.runbook_day_id,
        "state_path": str(state_path),
        "stage_summary_json": str(stage_summary_json),
        "stage_summary_txt": str(stage_summary_txt),
        "latest_stage_summary_json": str(stage_summary_paths["latest_json"]),
        "latest_stage_summary_txt": str(stage_summary_paths["latest_txt"]),
        "command_results": [
            step["result_json_ref"]
            for step in stage_summary["steps"]
            if step.get("result_json_ref")
        ],
        "paper_test_confirmed": confirm_paper_test,
        "dry_run": dry_run,
    }


def run_stage_b(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
    dry_run: bool = False,
    confirm_paper_test: bool = False,
    repo_root: Path | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    commands: Sequence[RunbookCommand] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace)
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    guard_error = _paper_smoke_guard(account_id, dry_run, confirm_paper_test)
    if guard_error:
        return _blocked_stage_b_payload(guard_error, dry_run, confirm_paper_test)

    try:
        _, state_path, state = runbook_state.init_state_file_for_context(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone,
        )
    except ValueError as exc:
        return _blocked_stage_b_payload(str(exc), dry_run, confirm_paper_test)

    precondition_error = _stage_b_precondition_error(state)
    if precondition_error:
        state = runbook_state.block_stage(state, STAGE_B_ID, precondition_error)
        runbook_state.save_state(state, state_path)
        return {
            **_blocked_stage_b_payload(precondition_error, dry_run, confirm_paper_test),
            "runbook_day_id": state.runbook_day_id,
            "state_path": str(state_path),
        }
    state, recovery_error = _recover_stale_stage_b_running(state)
    if recovery_error:
        state = runbook_state.block_stage(state, STAGE_B_ID, recovery_error)
        runbook_state.save_state(state, state_path)
        return {
            **_blocked_stage_b_payload(recovery_error, dry_run, confirm_paper_test),
            "runbook_day_id": state.runbook_day_id,
            "state_path": str(state_path),
        }
    runbook_state.save_state(state, state_path)

    command_by_key = {command.command_key: command for command in get_stage_b_commands(commands)}
    sequence = [
        command_by_key["execution_preview"],
        _execution_reconciliation_preview_command(),
        command_by_key["execution_commit"],
        command_by_key["sync_execution_status"],
    ]

    state = runbook_state.start_stage(state, STAGE_B_ID)
    runbook_state.save_state(state, state_path)

    command_results: list[dict[str, Any]] = []
    rendered_commands: list[dict[str, Any]] = []
    stage_result = "PASS"
    idempotency_key: str | None = None

    for command in sequence:
        if command.command_key == "execution_commit" and not dry_run:
            try:
                state, idempotency_key = runbook_state.reserve_idempotency(
                    state,
                    command.command_key,
                    command.step_id,
                    STAGE_B_ID,
                    {
                        "execution_preview_json": state.artifacts.get("execution_preview_json", ""),
                        "execution_reconciliation_preview_json": state.artifacts.get(
                            "execution_reconciliation_preview_json", ""
                        ),
                    },
                    workspace,
                )
                state = runbook_state.mark_idempotency_running(state, idempotency_key)
                runbook_state.save_state(state, state_path)
            except ValueError as exc:
                command_result = _blocked_command_result(
                    state,
                    workspace,
                    command,
                    f"execution_commit idempotency blocked: {exc}",
                )
                command_json_path, command_txt_path = _write_command_result_and_log(
                    workspace,
                    state,
                    command,
                    command_result,
                    "",
                )
                command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
                command_results.append(command_result)
                state = runbook_state.block_stage(
                    state,
                    STAGE_B_ID,
                    str(exc),
                    {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
                )
                runbook_state.save_state(state, state_path)
                stage_result = "BLOCKED"
                break

        try:
            command_result, log_text, rendered_argv = _run_stage_b_command(
                state,
                workspace,
                repo_root,
                command,
                dry_run,
                timeout_sec,
            )
            rendered_commands.append({"command_key": command.command_key, "argv": rendered_argv})
            command_json_path, command_txt_path = _write_command_result_and_log(
                workspace,
                state,
                command,
                command_result,
                log_text,
            )
            command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
            command_results.append(command_result)
        except Exception as exc:
            rendered_commands.append({"command_key": command.command_key, "argv": []})
            command_result = runbook_result.create_command_result(
                state,
                command,
                "FAILED",
                f"Stage B command raised {type(exc).__name__}.",
                raw_payload={},
                blockers=[str(exc)],
                process={"executed": False, "exit_code": None, "duration_ms": None},
                workspace=workspace,
            )
            command_json_path, command_txt_path = _write_command_result_and_log(
                workspace,
                state,
                command,
                command_result,
                f"exception: {type(exc).__name__}: {exc}\n",
            )
            command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
            command_results.append(command_result)
            stage_result = "FAILED"
            state = runbook_state.fail_stage(
                state,
                STAGE_B_ID,
                f"stage_b_step_exception:{command.command_key}",
                {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
            )
            runbook_state.save_state(state, state_path)
            break
        runner_result = command_result["runner_result"]

        if runner_result == "PASS":
            artifact_refs = command_result.get("outputs", {}).get("artifact_refs", {})
            state = runbook_state.complete_step(
                state,
                command.step_id,
                STAGE_B_ID,
                artifact_refs,
                workspace,
            )
            if command.command_key == "execution_commit" and idempotency_key:
                state = runbook_state.mark_idempotency_pass(
                    state,
                    idempotency_key,
                    result_ref=artifact_refs.get("execution_commit_report_json"),
                )
            runbook_state.save_state(state, state_path)
            continue

        if command.command_key == "execution_commit" and idempotency_key:
            state = runbook_state.mark_idempotency_failed(
                state,
                idempotency_key,
                f"execution_commit_{runner_result.lower()}",
            )
        if runner_result == "BLOCKED":
            stage_result = "BLOCKED"
            state = runbook_state.block_stage(
                state,
                STAGE_B_ID,
                f"stage_b_step_blocked:{command.command_key}",
                {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
            )
        else:
            stage_result = "FAILED"
            state = runbook_state.fail_stage(
                state,
                STAGE_B_ID,
                f"stage_b_step_failed:{command.command_key}",
                {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
            )
        runbook_state.save_state(state, state_path)
        break

    if stage_result == "PASS":
        state = runbook_state.complete_stage(state, STAGE_B_ID)
        runbook_state.save_state(state, state_path)

    stage_summary = runbook_result.create_stage_summary(
        state,
        STAGE_B_ID,
        command_results,
        next_required_action=(
            "Proceed to Stage B Verify, then Stage C review prep."
            if stage_result == "PASS"
            else "Inspect Stage B command result and pinned artifacts before retry."
        ),
        next_stage="GATE2" if stage_result == "PASS" else None,
    )
    stage_summary["raw_payload"] = {
        "execution_preview_json": state.artifacts.get("execution_preview_json"),
        "execution_reconciliation_preview_json": state.artifacts.get("execution_reconciliation_preview_json"),
        "execution_commit_report_json": state.artifacts.get("execution_commit_report_json"),
        "execution_status_sync_report": state.artifacts.get("execution_status_sync_report"),
        "execution_status_sync_report_json": state.artifacts.get("execution_status_sync_report_json"),
        "committed_row_count": _last_raw_value(command_results, "committed_row_count"),
        "notion_updated_count": _last_raw_value(command_results, "updated_count"),
    }
    stage_summary_json, stage_summary_txt = runbook_result.write_stage_summary(workspace, state, stage_summary)
    stage_summary_paths = runbook_result.get_stage_summary_paths(
        workspace,
        state.runbook_day_id,
        STAGE_B_ID,
        timestamp=Path(stage_summary_json).name.rsplit("_", 1)[0],
    )
    return {
        "runner_result": stage_summary["runner_result"],
        "stage_id": STAGE_B_ID,
        "runbook_day_id": state.runbook_day_id,
        "state_path": str(state_path),
        "stage_summary_json": str(stage_summary_json),
        "stage_summary_txt": str(stage_summary_txt),
        "latest_stage_summary_json": str(stage_summary_paths["latest_json"]),
        "latest_stage_summary_txt": str(stage_summary_paths["latest_txt"]),
        "command_results": [
            step["result_json_ref"]
            for step in stage_summary["steps"]
            if step.get("result_json_ref")
        ],
        "rendered_commands": rendered_commands,
        "paper_test_confirmed": confirm_paper_test,
        "dry_run": dry_run,
    }


def run_stage_c(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
    dry_run: bool = False,
    confirm_paper_test: bool = False,
    repo_root: Path | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    commands: Sequence[RunbookCommand] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace)
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    guard_error = _paper_smoke_guard(account_id, dry_run, confirm_paper_test)
    if guard_error:
        return _blocked_stage_c_payload(guard_error, dry_run, confirm_paper_test)

    try:
        _, state_path, state = runbook_state.init_state_file_for_context(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone,
        )
    except ValueError as exc:
        return _blocked_stage_c_payload(str(exc), dry_run, confirm_paper_test)

    precondition_error = _stage_c_precondition_error(state, workspace)
    if precondition_error:
        return {
            **_blocked_stage_c_payload(precondition_error, dry_run, confirm_paper_test),
            "runbook_day_id": state.runbook_day_id,
            "state_path": str(state_path),
        }

    review_commands = get_stage_c_commands(commands)
    command_results: list[dict[str, Any]] = []
    rendered_commands: list[dict[str, Any]] = []
    stage_result = "PASS"

    for command in review_commands:
        try:
            command_result, log_text, rendered_argv = _run_stage_c_command(
                state,
                workspace,
                repo_root,
                command,
                dry_run,
                timeout_sec,
            )
            rendered_commands.append({"command_key": command.command_key, "argv": rendered_argv})
            command_json_path, command_txt_path = _write_command_result_and_log(
                workspace,
                state,
                command,
                command_result,
                log_text,
            )
            command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
            command_results.append(command_result)
        except Exception as exc:
            rendered_commands.append({"command_key": command.command_key, "argv": []})
            command_result = runbook_result.create_command_result(
                state,
                command,
                "FAILED",
                f"Stage C command raised {type(exc).__name__}.",
                raw_payload={},
                blockers=[str(exc)],
                process={"executed": False, "exit_code": None, "duration_ms": None},
                workspace=workspace,
            )
            command_json_path, command_txt_path = _write_command_result_and_log(
                workspace,
                state,
                command,
                command_result,
                f"exception: {type(exc).__name__}: {exc}\n",
            )
            command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
            command_results.append(command_result)
            stage_result = "FAILED"
            state = runbook_state.record_artifact(
                state,
                "stage_c_error_result_json",
                str(command_json_path),
                workspace,
            )
            runbook_state.save_state(state, state_path)
            break

        runner_result = command_result["runner_result"]
        if runner_result == "PASS":
            artifact_refs = command_result.get("outputs", {}).get("artifact_refs", {})
            if command.command_key == "export_review_template":
                artifact_refs = {
                    **artifact_refs,
                    "notion_review_template_report_json": runbook_state.canonicalize_artifact_ref(
                        str(command_json_path),
                        workspace,
                    ),
                    "notion_review_template_report_md": runbook_state.canonicalize_artifact_ref(
                        str(command_txt_path),
                        workspace,
                    ),
                }
            state = runbook_state.complete_step(
                state,
                command.step_id,
                STAGE_C_ID,
                artifact_refs,
                workspace,
            )
            runbook_state.save_state(state, state_path)
            continue

        stage_result = "BLOCKED" if runner_result == "BLOCKED" else "FAILED"
        state = runbook_state.record_artifact(
            state,
            "stage_c_error_result_json",
            str(command_json_path),
            workspace,
        )
        runbook_state.save_state(state, state_path)
        break

    stage_summary = runbook_result.create_stage_summary(
        state,
        STAGE_C_ID,
        command_results,
        next_required_action=(
            "Fill Manual Review in Notion, then run Gate 2."
            if stage_result == "PASS"
            else "Inspect Stage C review prep command result before retry."
        ),
        next_stage="GATE2" if stage_result == "PASS" else None,
    )
    stage_summary["raw_payload"] = {
        "daily_review_report_md": state.artifacts.get("daily_review_report_md"),
        "manual_review_template_csv": state.artifacts.get("manual_review_template_csv"),
        "manual_review_template_md": state.artifacts.get("manual_review_template_md"),
        "notion_review_template_report_json": state.artifacts.get("notion_review_template_report_json"),
        "notion_review_template_report_md": state.artifacts.get("notion_review_template_report_md"),
        "next_required_action": stage_summary["summary"].get("next_required_action"),
    }
    if stage_result == "PASS":
        state = runbook_state.complete_stage(state, STAGE_C_ID)
        runbook_state.save_state(state, state_path)
        stage_summary = runbook_result.create_stage_summary(
            state,
            STAGE_C_ID,
            command_results,
            next_required_action="Fill Manual Review in Notion, then run Gate 2.",
            next_stage="GATE2",
        )
        stage_summary["raw_payload"] = {
            "daily_review_report_md": state.artifacts.get("daily_review_report_md"),
            "manual_review_template_csv": state.artifacts.get("manual_review_template_csv"),
            "manual_review_template_md": state.artifacts.get("manual_review_template_md"),
            "notion_review_template_report_json": state.artifacts.get("notion_review_template_report_json"),
            "notion_review_template_report_md": state.artifacts.get("notion_review_template_report_md"),
            "next_required_action": stage_summary["summary"].get("next_required_action"),
        }
    stage_summary_json, stage_summary_txt = runbook_result.write_stage_summary(workspace, state, stage_summary)
    stage_summary_paths = runbook_result.get_stage_summary_paths(
        workspace,
        state.runbook_day_id,
        STAGE_C_ID,
        timestamp=Path(stage_summary_json).name.rsplit("_", 1)[0],
    )
    return {
        "runner_result": stage_summary["runner_result"],
        "stage_id": STAGE_C_ID,
        "canonical_stage_id": STAGE_C_ID,
        "runbook_day_id": state.runbook_day_id,
        "state_path": str(state_path),
        "stage_summary_json": str(stage_summary_json),
        "stage_summary_txt": str(stage_summary_txt),
        "latest_stage_summary_json": str(stage_summary_paths["latest_json"]),
        "latest_stage_summary_txt": str(stage_summary_paths["latest_txt"]),
        "command_results": [
            step["result_json_ref"]
            for step in stage_summary["steps"]
            if step.get("result_json_ref")
        ],
        "rendered_commands": rendered_commands,
        "paper_test_confirmed": confirm_paper_test,
        "dry_run": dry_run,
        "next_required_action": stage_summary["summary"].get("next_required_action"),
    }


def run_stage_b_review(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = run_stage_c(*args, **kwargs)
    result["deprecated_alias"] = "stage-b-review"
    result["canonical_stage_id"] = STAGE_C_ID
    return result


def check_gate2(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
    confirm_paper_test: bool = False,
) -> dict[str, Any]:
    guard_error = _paper_smoke_guard(account_id, dry_run=False, confirm_paper_test=confirm_paper_test)
    if guard_error:
        return {
            "runner_result": "BLOCKED",
            "gate_id": "GATE2",
            "reason": guard_error,
            "paper_test_confirmed": confirm_paper_test,
        }
    result = runbook_gate_checker.check_gate2_readiness(
        workspace=workspace,
        account_id=account_id,
        data_date=data_date,
        trade_date=trade_date,
        timezone=timezone,
    )
    result["paper_test_confirmed"] = confirm_paper_test
    return result


def run_stage_d_preview(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
    dry_run: bool = False,
    confirm_paper_test: bool = False,
    repo_root: Path | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    commands: Sequence[RunbookCommand] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace)
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    guard_error = _paper_smoke_guard(account_id, dry_run, confirm_paper_test)
    if guard_error:
        return _blocked_stage_d_preview_payload(guard_error, dry_run, confirm_paper_test)

    try:
        _, state_path, state = runbook_state.init_state_file_for_context(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone,
        )
    except ValueError as exc:
        return _blocked_stage_d_preview_payload(str(exc), dry_run, confirm_paper_test)

    precondition_error = _stage_d_preview_precondition_error(state, workspace)
    if precondition_error:
        return {
            **_blocked_stage_d_preview_payload(precondition_error, dry_run, confirm_paper_test),
            "runbook_day_id": state.runbook_day_id,
            "state_path": str(state_path),
            "next_required_action": (
                "Run Gate 2 after completing Manual Review in Notion."
                if precondition_error == "gate2_required"
                else "Fix runbook state before retrying Stage D preview."
            ),
        }

    preview_commands = get_stage_d_preview_commands(commands)
    command_results: list[dict[str, Any]] = []
    rendered_commands: list[dict[str, Any]] = []
    stage_result = "PASS"

    for command in preview_commands:
        try:
            command_result, log_text, rendered_argv = _run_stage_d_preview_command(
                state,
                workspace,
                repo_root,
                command,
                dry_run,
                timeout_sec,
            )
            rendered_commands.append({"command_key": command.command_key, "argv": rendered_argv})
            command_json_path, command_txt_path = _write_command_result_and_log(
                workspace,
                state,
                command,
                command_result,
                log_text,
            )
            command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
            command_results.append(command_result)
        except Exception as exc:
            rendered_commands.append({"command_key": command.command_key, "argv": []})
            command_result = runbook_result.create_command_result(
                state,
                command,
                "FAILED",
                f"Stage D preview command raised {type(exc).__name__}.",
                raw_payload={},
                blockers=[str(exc)],
                process={"executed": False, "exit_code": None, "duration_ms": None},
                workspace=workspace,
            )
            command_json_path, command_txt_path = _write_command_result_and_log(
                workspace,
                state,
                command,
                command_result,
                f"exception: {type(exc).__name__}: {exc}\n",
            )
            command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
            command_results.append(command_result)
            stage_result = "FAILED"
            state = runbook_state.record_artifact(
                state,
                "stage_d_preview_error_result_json",
                str(command_json_path),
                workspace,
            )
            runbook_state.save_state(state, state_path)
            break

        runner_result = command_result["runner_result"]
        if runner_result in {"PASS", "WARNING"}:
            artifact_refs = command_result.get("outputs", {}).get("artifact_refs", {})
            state = runbook_state.complete_step(
                state,
                command.step_id,
                STAGE_D_ID,
                artifact_refs,
                workspace,
            )
            state = replace(state, current_status="PASS", last_error=None)
            runbook_state.save_state(state, state_path)
            if runner_result == "WARNING":
                stage_result = "WARNING"
            continue

        stage_result = "BLOCKED" if runner_result == "BLOCKED" else "FAILED"
        state = runbook_state.record_artifact(
            state,
            "stage_d_preview_error_result_json",
            str(command_json_path),
            workspace,
        )
        runbook_state.save_state(state, state_path)
        break

    stage_summary = runbook_result.create_stage_summary(
        state,
        STAGE_D_PREVIEW_ID,
        command_results,
        next_required_action=(
            "Review preview artifact, then run Stage D append/sync."
            if stage_result in {"PASS", "WARNING"}
            else "Inspect Stage D preview command result before retry."
        ),
        next_stage="D_APPEND" if stage_result in {"PASS", "WARNING"} else None,
    )
    stage_summary["canonical_stage_id"] = STAGE_D_ID
    stage_summary["artifact_refs"] = {
        **stage_summary.get("artifact_refs", {}),
        "review_preview_json": state.artifacts.get("review_preview_json"),
        "review_preview_md": state.artifacts.get("review_preview_md"),
    }
    stage_summary["raw_payload"] = {
        "canonical_stage_id": STAGE_D_ID,
        "review_preview_json": state.artifacts.get("review_preview_json"),
        "review_preview_md": state.artifacts.get("review_preview_md"),
        "next_required_action": stage_summary["summary"].get("next_required_action"),
    }
    stage_summary_json, stage_summary_txt = runbook_result.write_stage_summary(workspace, state, stage_summary)
    stage_summary_paths = runbook_result.get_stage_summary_paths(
        workspace,
        state.runbook_day_id,
        STAGE_D_PREVIEW_ID,
        timestamp=Path(stage_summary_json).name.rsplit("_", 1)[0],
    )
    return {
        "runner_result": stage_summary["runner_result"],
        "stage_id": STAGE_D_PREVIEW_ID,
        "canonical_stage_id": STAGE_D_ID,
        "runbook_day_id": state.runbook_day_id,
        "state_path": str(state_path),
        "stage_summary_json": str(stage_summary_json),
        "stage_summary_txt": str(stage_summary_txt),
        "latest_stage_summary_json": str(stage_summary_paths["latest_json"]),
        "latest_stage_summary_txt": str(stage_summary_paths["latest_txt"]),
        "command_results": [
            step["result_json_ref"]
            for step in stage_summary["steps"]
            if step.get("result_json_ref")
        ],
        "rendered_commands": rendered_commands,
        "paper_test_confirmed": confirm_paper_test,
        "dry_run": dry_run,
        "review_preview_json": state.artifacts.get("review_preview_json"),
        "review_preview_md": state.artifacts.get("review_preview_md"),
        "next_required_action": stage_summary["summary"].get("next_required_action"),
    }


def run_stage_d_append(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
    dry_run: bool = False,
    confirm_paper_test: bool = False,
    repo_root: Path | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    commands: Sequence[RunbookCommand] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace)
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    guard_error = _paper_smoke_guard(account_id, dry_run, confirm_paper_test)
    if guard_error:
        return _blocked_stage_d_append_payload(guard_error, dry_run, confirm_paper_test)

    try:
        _, state_path, state = runbook_state.init_state_file_for_context(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone,
        )
    except ValueError as exc:
        return _blocked_stage_d_append_payload(str(exc), dry_run, confirm_paper_test)

    precondition_error = _stage_d_append_precondition_error(state, workspace)
    if precondition_error:
        return {
            **_blocked_stage_d_append_payload(precondition_error, dry_run, confirm_paper_test),
            "runbook_day_id": state.runbook_day_id,
            "state_path": str(state_path),
            "next_required_action": (
                "Run Stage D preview after Gate 2 PASS."
                if precondition_error in {"review_preview_required", "review_preview_not_append_ready"}
                else "Fix runbook state before retrying Stage D append/sync."
            ),
        }

    append_commands = get_stage_d_append_commands(commands)
    command_by_key = {command.command_key: command for command in append_commands}
    append_command = command_by_key["review_append"]
    sync_command = command_by_key["sync_review_status"]
    command_results: list[dict[str, Any]] = []
    rendered_commands: list[dict[str, Any]] = []
    stage_result = "PASS"
    append_idempotency_key: str | None = _review_append_idempotency_key(state, workspace)
    append_record = state.idempotency_records.get(append_idempotency_key) if append_idempotency_key else None
    append_already_pass = bool(append_record and append_record.get("status") == "PASS")

    if append_already_pass:
        if not _artifact_ref_exists(workspace, state.artifacts.get("review_append_report_json", "")):
            return {
                **_blocked_stage_d_append_payload(
                    "review_append_already_committed_missing_report",
                    dry_run,
                    confirm_paper_test,
                ),
                "runbook_day_id": state.runbook_day_id,
                "state_path": str(state_path),
                "next_required_action": "Recover the pinned review append report before syncing.",
            }
        if state.stage_status.get(STAGE_D_ID) == "PASS":
            return {
                **_blocked_stage_d_append_payload(
                    "review_append_already_committed",
                    dry_run,
                    confirm_paper_test,
                ),
                "runbook_day_id": state.runbook_day_id,
                "state_path": str(state_path),
                "next_required_action": "Stage D is already complete.",
            }
        skipped = _skipped_stage_d_append_result(
            state,
            workspace,
            append_command,
            "Review append already committed; reusing pinned report for sync.",
        )
        command_json_path, command_txt_path = _write_command_result_and_log(workspace, state, append_command, skipped, "")
        command_results.append(json.loads(command_json_path.read_text(encoding="utf-8")))
        rendered_commands.append({"command_key": append_command.command_key, "argv": []})
    else:
        if not dry_run:
            try:
                state, append_idempotency_key = runbook_state.reserve_idempotency(
                    state,
                    append_command.command_key,
                    append_command.step_id,
                    STAGE_D_ID,
                    {"review_preview_json": state.artifacts.get("review_preview_json", "")},
                    workspace,
                )
                state = runbook_state.mark_idempotency_running(state, append_idempotency_key)
                runbook_state.save_state(state, state_path)
            except ValueError as exc:
                command_result = _blocked_command_result(
                    state,
                    workspace,
                    append_command,
                    f"review_append idempotency blocked: {exc}",
                )
                command_json_path, command_txt_path = _write_command_result_and_log(
                    workspace,
                    state,
                    append_command,
                    command_result,
                    "",
                )
                command_results.append(json.loads(command_json_path.read_text(encoding="utf-8")))
                state = runbook_state.block_stage(
                    state,
                    STAGE_D_ID,
                    str(exc),
                    {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
                )
                runbook_state.save_state(state, state_path)
                stage_result = "BLOCKED"

        if stage_result == "PASS":
            state, command_result, rendered_argv, log_text, stage_result = _execute_stage_d_append_step(
                state,
                workspace,
                state_path,
                repo_root,
                append_command,
                dry_run,
                timeout_sec,
                append_idempotency_key,
            )
            rendered_commands.append({"command_key": append_command.command_key, "argv": rendered_argv})
            command_json_path, command_txt_path = _write_command_result_and_log(
                workspace,
                state,
                append_command,
                command_result,
                log_text,
            )
            command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
            command_results.append(command_result)
            state = _apply_stage_d_append_step_result(
                state,
                state_path,
                workspace,
                append_command,
                command_result,
                command_json_path,
                command_txt_path,
                append_idempotency_key,
            )
            if command_result["runner_result"] != "PASS":
                stage_result = "BLOCKED" if command_result["runner_result"] == "BLOCKED" else "FAILED"

    if stage_result == "PASS":
        state, command_result, rendered_argv, log_text, stage_result = _execute_stage_d_append_step(
            state,
            workspace,
            state_path,
            repo_root,
            sync_command,
            dry_run,
            timeout_sec,
            None,
        )
        rendered_commands.append({"command_key": sync_command.command_key, "argv": rendered_argv})
        command_json_path, command_txt_path = _write_command_result_and_log(
            workspace,
            state,
            sync_command,
            command_result,
            log_text,
        )
        command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
        command_results.append(command_result)
        state = _apply_stage_d_append_step_result(
            state,
            state_path,
            workspace,
            sync_command,
            command_result,
            command_json_path,
            command_txt_path,
            None,
        )
        if command_result["runner_result"] != "PASS":
            stage_result = "BLOCKED" if command_result["runner_result"] == "BLOCKED" else "FAILED"

    if stage_result == "PASS":
        state = runbook_state.complete_stage(state, STAGE_D_ID)
        runbook_state.save_state(state, state_path)

    stage_summary = runbook_result.create_stage_summary(
        state,
        STAGE_D_ID,
        command_results,
        next_required_action=(
            "Run Stage E EOD dry-run/commit/final status."
            if stage_result == "PASS"
            else "Inspect Stage D command result before retry."
        ),
        next_stage="E" if stage_result == "PASS" else None,
    )
    stage_summary["raw_payload"] = {
        "review_preview_json": state.artifacts.get("review_preview_json"),
        "review_append_report_json": state.artifacts.get("review_append_report_json"),
        "review_status_sync_report_json": state.artifacts.get("review_status_sync_report_json"),
        "next_required_action": stage_summary["summary"].get("next_required_action"),
    }
    stage_summary_json, stage_summary_txt = runbook_result.write_stage_summary(workspace, state, stage_summary)
    stage_summary_paths = runbook_result.get_stage_summary_paths(
        workspace,
        state.runbook_day_id,
        STAGE_D_ID,
        timestamp=Path(stage_summary_json).name.rsplit("_", 1)[0],
    )
    return {
        "runner_result": stage_summary["runner_result"],
        "stage_id": STAGE_D_ID,
        "canonical_stage_id": STAGE_D_ID,
        "runbook_day_id": state.runbook_day_id,
        "state_path": str(state_path),
        "stage_summary_json": str(stage_summary_json),
        "stage_summary_txt": str(stage_summary_txt),
        "latest_stage_summary_json": str(stage_summary_paths["latest_json"]),
        "latest_stage_summary_txt": str(stage_summary_paths["latest_txt"]),
        "command_results": [
            step["result_json_ref"]
            for step in stage_summary["steps"]
            if step.get("result_json_ref")
        ],
        "rendered_commands": rendered_commands,
        "paper_test_confirmed": confirm_paper_test,
        "dry_run": dry_run,
        "review_append_report_json": state.artifacts.get("review_append_report_json"),
        "review_status_sync_report_json": state.artifacts.get("review_status_sync_report_json"),
        "next_required_action": stage_summary["summary"].get("next_required_action"),
    }


def run_stage_e(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
    dry_run: bool = False,
    confirm_paper_test: bool = False,
    repo_root: Path | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    commands: Sequence[RunbookCommand] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace)
    repo_root = repo_root or Path(__file__).resolve().parents[1]
    guard_error = _paper_smoke_guard(account_id, dry_run, confirm_paper_test)
    if guard_error:
        return _blocked_stage_e_payload(guard_error, dry_run, confirm_paper_test)

    try:
        _, state_path, state = runbook_state.init_state_file_for_context(
            workspace,
            account_id,
            data_date,
            trade_date,
            timezone,
        )
    except ValueError as exc:
        return _blocked_stage_e_payload(str(exc), dry_run, confirm_paper_test)

    precondition_error = _stage_e_precondition_error(state, workspace)
    if precondition_error:
        return {
            **_blocked_stage_e_payload(precondition_error, dry_run, confirm_paper_test),
            "runbook_day_id": state.runbook_day_id,
            "state_path": str(state_path),
            "next_required_action": (
                "Run Stage D append/sync first."
                if precondition_error == "stage_d_required"
                else "Fix runbook state before retrying Stage E."
            ),
        }

    stage_e_commands = get_stage_e_commands(commands)
    command_by_key = {command.command_key: command for command in stage_e_commands}
    dryrun_command = command_by_key["eod_dryrun"]
    commit_command = command_by_key["eod_commit"]
    final_status_command = command_by_key["final_status"]
    command_results: list[dict[str, Any]] = []
    rendered_commands: list[dict[str, Any]] = []
    stage_result = "PASS"
    eod_idempotency_key: str | None = _eod_commit_idempotency_key(state, workspace)
    eod_record = state.idempotency_records.get(eod_idempotency_key) if eod_idempotency_key else None
    eod_already_pass = bool(eod_record and eod_record.get("status") == "PASS")

    if not eod_already_pass:
        state = runbook_state.start_stage(state, STAGE_E_ID)
        runbook_state.save_state(state, state_path)

        state, command_result, rendered_argv, log_text, stage_result = _execute_stage_e_step(
            state,
            workspace,
            state_path,
            repo_root,
            dryrun_command,
            dry_run,
            timeout_sec,
            None,
        )
        rendered_commands.append({"command_key": dryrun_command.command_key, "argv": rendered_argv})
        command_json_path, command_txt_path = _write_command_result_and_log(
            workspace,
            state,
            dryrun_command,
            command_result,
            log_text,
        )
        command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
        command_results.append(command_result)
        state = _apply_stage_e_step_result(
            state,
            state_path,
            workspace,
            dryrun_command,
            command_result,
            command_json_path,
            command_txt_path,
            None,
        )
        if command_result["runner_result"] != "PASS":
            stage_result = "BLOCKED" if command_result["runner_result"] == "BLOCKED" else "FAILED"

    if stage_result == "PASS" and not eod_already_pass:
        eod_idempotency_key = _eod_commit_idempotency_key(state, workspace)
        try:
            if not dry_run:
                state, eod_idempotency_key = runbook_state.reserve_idempotency(
                    state,
                    commit_command.command_key,
                    commit_command.step_id,
                    STAGE_E_ID,
                    {"eod_dryrun_report_json": state.artifacts.get("eod_dryrun_report_json", "")},
                    workspace,
                )
                state = runbook_state.mark_idempotency_running(state, eod_idempotency_key)
                runbook_state.save_state(state, state_path)
        except ValueError as exc:
            command_result = _blocked_command_result(
                state,
                workspace,
                commit_command,
                f"eod_commit idempotency blocked: {exc}",
            )
            command_json_path, command_txt_path = _write_command_result_and_log(
                workspace,
                state,
                commit_command,
                command_result,
                "",
            )
            command_results.append(json.loads(command_json_path.read_text(encoding="utf-8")))
            state = runbook_state.block_stage(
                state,
                STAGE_E_ID,
                str(exc),
                {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
            )
            runbook_state.save_state(state, state_path)
            stage_result = "BLOCKED"

        if stage_result == "PASS":
            state, command_result, rendered_argv, log_text, stage_result = _execute_stage_e_step(
                state,
                workspace,
                state_path,
                repo_root,
                commit_command,
                dry_run,
                timeout_sec,
                eod_idempotency_key,
            )
            rendered_commands.append({"command_key": commit_command.command_key, "argv": rendered_argv})
            command_json_path, command_txt_path = _write_command_result_and_log(
                workspace,
                state,
                commit_command,
                command_result,
                log_text,
            )
            command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
            command_results.append(command_result)
            state = _apply_stage_e_step_result(
                state,
                state_path,
                workspace,
                commit_command,
                command_result,
                command_json_path,
                command_txt_path,
                eod_idempotency_key,
            )
            if command_result["runner_result"] != "PASS":
                stage_result = "BLOCKED" if command_result["runner_result"] == "BLOCKED" else "FAILED"
    elif stage_result == "PASS" and eod_already_pass:
        if state.stage_status.get(STAGE_E_ID) == "PASS":
            return {
                **_blocked_stage_e_payload("eod_commit_already_committed", dry_run, confirm_paper_test),
                "runbook_day_id": state.runbook_day_id,
                "state_path": str(state_path),
                "next_required_action": "Stage E is already complete.",
            }
        if not _artifact_ref_exists(workspace, state.artifacts.get("eod_commit_report_json", "")):
            return {
                **_blocked_stage_e_payload("eod_commit_already_committed_missing_report", dry_run, confirm_paper_test),
                "runbook_day_id": state.runbook_day_id,
                "state_path": str(state_path),
                "next_required_action": "Recover the pinned EOD commit report before final status.",
            }
        skipped = _skipped_stage_e_commit_result(
            state,
            workspace,
            commit_command,
            "EOD commit already completed; reusing pinned report for final status.",
        )
        command_json_path, _ = _write_command_result_and_log(workspace, state, commit_command, skipped, "")
        command_results.append(json.loads(command_json_path.read_text(encoding="utf-8")))
        rendered_commands.append({"command_key": commit_command.command_key, "argv": []})

    if stage_result == "PASS":
        state, command_result, rendered_argv, log_text, stage_result = _execute_stage_e_step(
            state,
            workspace,
            state_path,
            repo_root,
            final_status_command,
            dry_run,
            timeout_sec,
            None,
        )
        rendered_commands.append({"command_key": final_status_command.command_key, "argv": rendered_argv})
        command_json_path, command_txt_path = _write_command_result_and_log(
            workspace,
            state,
            final_status_command,
            command_result,
            log_text,
        )
        command_result = json.loads(command_json_path.read_text(encoding="utf-8"))
        command_results.append(command_result)
        state = _apply_stage_e_step_result(
            state,
            state_path,
            workspace,
            final_status_command,
            command_result,
            command_json_path,
            command_txt_path,
            None,
        )
        if command_result["runner_result"] != "PASS":
            stage_result = "BLOCKED" if command_result["runner_result"] in {"BLOCKED", "WARNING"} else "FAILED"

    if stage_result == "PASS":
        state = runbook_state.complete_stage(state, STAGE_E_ID)
        runbook_state.save_state(state, state_path)

    stage_summary = runbook_result.create_stage_summary(
        state,
        STAGE_E_ID,
        command_results,
        next_required_action=(
            "Runbook day complete."
            if stage_result == "PASS"
            else "Inspect Stage E command result before retry."
        ),
        next_stage=None,
    )
    stage_summary["raw_payload"] = {
        "eod_dryrun_report_json": state.artifacts.get("eod_dryrun_report_json"),
        "eod_commit_report_json": state.artifacts.get("eod_commit_report_json"),
        "final_status_report_json": state.artifacts.get("final_status_report_json"),
        "next_required_action": stage_summary["summary"].get("next_required_action"),
    }
    stage_summary_json, stage_summary_txt = runbook_result.write_stage_summary(workspace, state, stage_summary)
    stage_summary_paths = runbook_result.get_stage_summary_paths(
        workspace,
        state.runbook_day_id,
        STAGE_E_ID,
        timestamp=Path(stage_summary_json).name.rsplit("_", 1)[0],
    )
    return {
        "runner_result": stage_summary["runner_result"],
        "stage_id": STAGE_E_ID,
        "canonical_stage_id": STAGE_E_ID,
        "runbook_day_id": state.runbook_day_id,
        "state_path": str(state_path),
        "stage_summary_json": str(stage_summary_json),
        "stage_summary_txt": str(stage_summary_txt),
        "latest_stage_summary_json": str(stage_summary_paths["latest_json"]),
        "latest_stage_summary_txt": str(stage_summary_paths["latest_txt"]),
        "command_results": [
            step["result_json_ref"]
            for step in stage_summary["steps"]
            if step.get("result_json_ref")
        ],
        "rendered_commands": rendered_commands,
        "paper_test_confirmed": confirm_paper_test,
        "dry_run": dry_run,
        "eod_dryrun_report_json": state.artifacts.get("eod_dryrun_report_json"),
        "eod_commit_report_json": state.artifacts.get("eod_commit_report_json"),
        "final_status_report_json": state.artifacts.get("final_status_report_json"),
        "next_required_action": stage_summary["summary"].get("next_required_action"),
    }


def _paper_smoke_guard(account_id: str, dry_run: bool, confirm_paper_test: bool) -> str | None:
    if dry_run:
        return None
    if not confirm_paper_test:
        return "paper_test_confirmation_required"
    account_id_lower = str(account_id or "").lower()
    if "paper" not in account_id_lower and "test" not in account_id_lower:
        return "paper_account_required"
    return None


def _blocked_stage_b_payload(reason: str, dry_run: bool, confirm_paper_test: bool) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "stage_id": STAGE_B_ID,
        "reason": reason,
        "dry_run": dry_run,
        "paper_test_confirmed": confirm_paper_test,
    }


def _blocked_stage_c_payload(reason: str, dry_run: bool, confirm_paper_test: bool) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "stage_id": STAGE_C_ID,
        "canonical_stage_id": STAGE_C_ID,
        "reason": reason,
        "dry_run": dry_run,
        "paper_test_confirmed": confirm_paper_test,
    }


def _blocked_stage_d_preview_payload(reason: str, dry_run: bool, confirm_paper_test: bool) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "stage_id": STAGE_D_PREVIEW_ID,
        "canonical_stage_id": STAGE_D_ID,
        "reason": reason,
        "dry_run": dry_run,
        "paper_test_confirmed": confirm_paper_test,
    }


def _blocked_stage_d_append_payload(reason: str, dry_run: bool, confirm_paper_test: bool) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "stage_id": STAGE_D_ID,
        "canonical_stage_id": STAGE_D_ID,
        "reason": reason,
        "dry_run": dry_run,
        "paper_test_confirmed": confirm_paper_test,
    }


def _blocked_stage_e_payload(reason: str, dry_run: bool, confirm_paper_test: bool) -> dict[str, Any]:
    return {
        "runner_result": "BLOCKED",
        "stage_id": STAGE_E_ID,
        "canonical_stage_id": STAGE_E_ID,
        "reason": reason,
        "dry_run": dry_run,
        "paper_test_confirmed": confirm_paper_test,
    }


def _stage_b_precondition_error(state: RunbookState) -> str | None:
    if state.stage_status.get(STAGE_A_ID) != "PASS":
        return "stage_a_not_pass"
    if state.stage_status.get("GATE1") != "PASS":
        return "gate1_not_pass"
    if state.last_error:
        return "active_last_error"
    if state.stage_status.get(STAGE_B_ID) == "PASS":
        return "stage_b_already_pass"
    for record in state.idempotency_records.values():
        if record.get("command_key") == "execution_commit" and record.get("status") == "PASS":
            return "execution_commit_already_recorded"
    return None


def _stage_c_precondition_error(state: RunbookState, workspace: Path) -> str | None:
    if state.stage_status.get(STAGE_A_ID) != "PASS":
        return "stage_a_not_pass"
    if state.stage_status.get("GATE1") != "PASS":
        return "gate1_not_pass"
    if state.stage_status.get(STAGE_B_ID) != "PASS":
        return "stage_b_not_pass"
    if state.last_error:
        return "active_last_error"
    commit_ref = state.artifacts.get("execution_commit_report_json")
    if not commit_ref or not _artifact_ref_exists(workspace, commit_ref):
        return "execution_commit_report_required"
    verification_ref = state.artifacts.get("stage_b_verification_json")
    if not verification_ref:
        return "stage_b_verification_required"
    verification_path = _artifact_ref_path(workspace, verification_ref)
    if not verification_path.exists():
        return "stage_b_verification_required"
    try:
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "stage_b_verification_required"
    if verification.get("schema_version") != "stage_b_verification.v1":
        return "stage_b_verification_required"
    if str(verification.get("runner_result") or "").upper() != "PASS":
        return "stage_b_verification_required"
    if _int_payload(verification, "committed_row_count") <= 0:
        return "stage_b_verification_required"
    if _int_payload(verification, "failed_count") != 0:
        return "stage_b_verification_required"
    return None


def _stage_d_preview_precondition_error(state: RunbookState, workspace: Path) -> str | None:
    if state.stage_status.get(STAGE_A_ID) != "PASS":
        return "stage_a_not_pass"
    if state.stage_status.get("GATE1") != "PASS":
        return "gate1_not_pass"
    if state.stage_status.get(STAGE_B_ID) != "PASS":
        return "stage_b_not_pass"
    if _stage_b_verification_error(state, workspace):
        return "stage_b_verification_required"
    if state.stage_status.get(STAGE_C_ID) != "PASS":
        return "stage_c_required"
    if state.stage_status.get("GATE2") != "PASS":
        return "gate2_required"
    gate2_ref = state.artifacts.get("gate2_readiness_json")
    if not gate2_ref or not _artifact_ref_exists(workspace, gate2_ref):
        return "gate2_required"
    try:
        gate2 = json.loads(_artifact_ref_path(workspace, gate2_ref).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "gate2_required"
    if gate2.get("schema_version") != "gate2_review_readiness.v1":
        return "gate2_required"
    if str(gate2.get("runner_result") or "").upper() != "PASS":
        return "gate2_required"
    if not (
        state.artifacts.get("manual_review_template_csv")
        or state.artifacts.get("notion_review_template_report_json")
    ):
        return "manual_review_template_required"
    if state.last_error:
        return "active_last_error"
    return None


def _stage_d_append_precondition_error(state: RunbookState, workspace: Path) -> str | None:
    base_error = _stage_d_preview_precondition_error(state, workspace)
    if base_error:
        if base_error != "active_last_error" or not _stage_d_sync_retry_allowed(state, workspace):
            return base_error
    if state.stage_status.get(STAGE_D_ID) == "PASS":
        return "stage_d_already_pass"
    preview_ref = state.artifacts.get("review_preview_json")
    if not preview_ref or not _artifact_ref_exists(workspace, preview_ref):
        return "review_preview_required"
    try:
        preview = json.loads(_artifact_ref_path(workspace, preview_ref).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "review_preview_required"
    preview_error = _review_preview_append_readiness_error(preview, state)
    if preview_error:
        return preview_error
    return None


def _stage_e_precondition_error(state: RunbookState, workspace: Path) -> str | None:
    if state.stage_status.get(STAGE_A_ID) != "PASS":
        return "stage_a_not_pass"
    if state.stage_status.get("GATE1") != "PASS":
        return "gate1_not_pass"
    if state.stage_status.get(STAGE_B_ID) != "PASS":
        return "stage_b_not_pass"
    if _stage_b_verification_error(state, workspace):
        return "stage_b_verification_required"
    if state.stage_status.get(STAGE_C_ID) != "PASS":
        return "stage_c_required"
    if state.stage_status.get("GATE2") != "PASS":
        return "gate2_required"
    if state.stage_status.get(STAGE_D_ID) != "PASS":
        return "stage_d_required"
    if state.stage_status.get(STAGE_E_ID) == "PASS":
        return "stage_e_already_pass"
    if state.last_error and not _stage_e_final_status_retry_allowed(state, workspace):
        return "active_last_error"
    for artifact_name in ("review_append_report_json", "review_status_sync_report_json"):
        artifact_ref = state.artifacts.get(artifact_name)
        if not artifact_ref or not _artifact_ref_exists(workspace, artifact_ref):
            return f"{artifact_name}_required"
    return None


def _stage_e_final_status_retry_allowed(state: RunbookState, workspace: Path) -> bool:
    reason = ""
    if isinstance(state.last_error, dict):
        reason = str(state.last_error.get("reason") or "")
    if "final_status" not in reason:
        return False
    key = _eod_commit_idempotency_key(state, workspace)
    if not key:
        return False
    record = state.idempotency_records.get(key)
    if not record or record.get("status") != "PASS":
        return False
    report_ref = state.artifacts.get("eod_commit_report_json")
    return bool(report_ref and _artifact_ref_exists(workspace, report_ref))


def _stage_d_sync_retry_allowed(state: RunbookState, workspace: Path) -> bool:
    reason = ""
    if isinstance(state.last_error, dict):
        reason = str(state.last_error.get("reason") or "")
    if "sync_review_status" not in reason:
        return False
    key = _review_append_idempotency_key(state, workspace)
    if not key:
        return False
    record = state.idempotency_records.get(key)
    if not record or record.get("status") != "PASS":
        return False
    report_ref = state.artifacts.get("review_append_report_json")
    return bool(report_ref and _artifact_ref_exists(workspace, report_ref))


def _review_preview_append_readiness_error(preview: dict[str, Any], state: RunbookState) -> str | None:
    if str(preview.get("account_id") or "").strip() != state.frozen_context.account_id:
        return "review_preview_context_mismatch"
    if str(preview.get("review_date") or "").strip() != state.frozen_context.trade_date:
        return "review_preview_context_mismatch"
    if _int_payload(preview, "candidate_count") <= 0:
        return "review_preview_not_append_ready"
    if _int_payload(preview, "fail_count") != 0:
        return "review_preview_not_append_ready"
    duplicate_candidates = preview.get("duplicate_candidates")
    if isinstance(duplicate_candidates, list) and duplicate_candidates:
        return "review_preview_not_append_ready"
    append_allowed = str(preview.get("append_allowed") or "").strip().lower()
    if append_allowed != "true":
        return "review_preview_not_append_ready"
    return None


def _stage_b_verification_error(state: RunbookState, workspace: Path) -> str | None:
    verification_ref = state.artifacts.get("stage_b_verification_json")
    if not verification_ref or not _artifact_ref_exists(workspace, verification_ref):
        return "stage_b_verification_required"
    verification_path = _artifact_ref_path(workspace, verification_ref)
    try:
        verification = json.loads(verification_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "stage_b_verification_required"
    if verification.get("schema_version") != "stage_b_verification.v1":
        return "stage_b_verification_required"
    if str(verification.get("runner_result") or "").upper() != "PASS":
        return "stage_b_verification_required"
    return None


def _artifact_ref_path(workspace: Path, artifact_ref: str) -> Path:
    path = Path(str(artifact_ref))
    return path if path.is_absolute() else workspace / path


def _artifact_ref_exists(workspace: Path, artifact_ref: str) -> bool:
    return _artifact_ref_path(workspace, artifact_ref).exists()


def _recover_stale_stage_b_running(state: RunbookState) -> tuple[RunbookState, str | None]:
    if state.current_stage != STAGE_B_ID or state.current_status != "RUNNING":
        return state, None
    if state.artifacts.get("execution_commit_report_json"):
        return state, "stage_b_running_with_commit_report"
    for record in state.idempotency_records.values():
        if record.get("command_key") == "execution_commit" and record.get("status") == "PASS":
            return state, "stage_b_running_with_committed_idempotency"
    timestamp = _next_recovery_timestamp(state)
    stage_status = dict(state.stage_status)
    stage_status[STAGE_B_ID] = "PENDING"
    event = {
        "event_type": "stale_stage_recovered",
        "stage_id": STAGE_B_ID,
        "step_id": None,
        "status": "PENDING",
        "reason": "stage_b_running_without_commit_artifact_or_pass_idempotency",
        "created_at": timestamp,
    }
    return (
        replace(
            state,
            updated_at=timestamp,
            current_stage="GATE1",
            current_status="PASS",
            stage_status=stage_status,
            last_error=None,
            history=[*state.history, event],
        ),
        None,
    )


def _next_recovery_timestamp(state: RunbookState) -> str:
    try:
        previous = datetime.fromisoformat(state.updated_at)
    except ValueError:
        return datetime.now().isoformat(timespec="microseconds")
    now = datetime.now(previous.tzinfo).replace(tzinfo=previous.tzinfo)
    if now <= previous:
        now = previous + timedelta(microseconds=1)
    return now.isoformat(timespec="microseconds")


def _execution_reconciliation_preview_command() -> RunbookCommand:
    base = registry.get_command("execution_preview")
    return replace(
        base,
        command_key="execution_reconciliation_preview",
        display_name="Execution reconciliation preview",
        argv_template=(
            "scripts\\runbook_execution_reconciliation_preview.py",
            "--workspace",
            "{workspace}",
            "--account-id",
            "{account_id}",
            "--data-date",
            "{data_date}",
            "--trade-date",
            "{trade_date}",
        ),
        produces_artifacts=("execution_reconciliation_preview_json", "execution_reconciliation_preview_md"),
        expected_outputs=("runner_result", "execution_reconciliation_preview_json"),
        success_criteria="runner_result=PASS and warning/needs_review/blocked counts are zero",
    )


def _run_stage_b_command(
    state: RunbookState,
    workspace: Path,
    repo_root: Path,
    command: RunbookCommand,
    dry_run: bool,
    timeout_sec: int,
) -> tuple[dict[str, Any], str, list[str]]:
    artifact_refs = _stage_b_render_artifacts(state.artifacts, workspace)
    artifact_refs["workspace"] = str(workspace)
    rendered_argv = render_argv_template(command, state.frozen_context, artifact_refs)
    argv = normalize_python_script_argv(rendered_argv, repo_root)
    if dry_run:
        process = {"executed": False, "exit_code": None, "duration_ms": None}
        artifacts = _dry_run_stage_b_artifacts(command)
        result = runbook_result.create_command_result(
            state,
            command,
            "PASS",
            "Dry-run only; command not executed.",
            artifact_refs=artifacts,
            raw_payload={},
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, "", ""), rendered_argv

    execution = run_allowlisted_command(argv, repo_root, timeout_sec)
    stdout = str(execution.get("stdout") or "")
    stderr = str(execution.get("stderr") or "")
    raw_payload = _parse_stdout_json(stdout)
    exit_code = execution.get("exit_code")
    process = {
        "executed": True,
        "exit_code": exit_code,
        "duration_ms": execution.get("duration_ms"),
    }
    if exit_code != 0:
        result = runbook_result.create_command_result(
            state,
            command,
            "FAILED",
            "Command failed.",
            raw_payload=raw_payload,
            blockers=[stderr.strip() or f"exit_code={exit_code}"],
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr), rendered_argv

    validation = _validate_stage_b_payload(command.command_key, raw_payload)
    if validation["artifact_refs"]:
        validation["artifact_refs"] = _pin_stage_b_artifact_refs(
            workspace,
            state.runbook_day_id,
            validation["artifact_refs"],
        )
    result = runbook_result.create_command_result(
        state,
        command,
        validation["runner_result"],
        validation["message"],
        artifact_refs=validation["artifact_refs"],
        raw_payload=raw_payload,
        blockers=validation["blockers"],
        process=process,
        workspace=workspace,
    )
    return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr), rendered_argv


def _run_stage_c_command(
    state: RunbookState,
    workspace: Path,
    repo_root: Path,
    command: RunbookCommand,
    dry_run: bool,
    timeout_sec: int,
) -> tuple[dict[str, Any], str, list[str]]:
    artifact_refs = _stage_b_render_artifacts(state.artifacts, workspace)
    artifact_refs["workspace"] = str(workspace)
    rendered_argv = render_argv_template(command, state.frozen_context, artifact_refs)
    argv = normalize_python_script_argv(rendered_argv, repo_root)
    if dry_run:
        process = {"executed": False, "exit_code": None, "duration_ms": None}
        artifacts = _dry_run_stage_c_artifacts(command)
        result = runbook_result.create_command_result(
            state,
            command,
            "PASS",
            "Dry-run only; command not executed.",
            artifact_refs=artifacts,
            raw_payload={},
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, "", ""), rendered_argv

    execution = run_allowlisted_command(argv, repo_root, timeout_sec)
    stdout = str(execution.get("stdout") or "")
    stderr = str(execution.get("stderr") or "")
    raw_payload = _parse_stdout_json(stdout)
    exit_code = execution.get("exit_code")
    process = {
        "executed": True,
        "exit_code": exit_code,
        "duration_ms": execution.get("duration_ms"),
    }
    if exit_code != 0:
        result = runbook_result.create_command_result(
            state,
            command,
            "FAILED",
            "Command failed.",
            raw_payload=raw_payload,
            blockers=[stderr.strip() or f"exit_code={exit_code}"],
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr), rendered_argv

    validation = _validate_stage_c_payload(command.command_key, raw_payload)
    if validation["artifact_refs"]:
        validation["artifact_refs"] = _pin_artifact_refs(
            workspace,
            state.runbook_day_id,
            validation["artifact_refs"],
            "review_prep",
        )
    result = runbook_result.create_command_result(
        state,
        command,
        validation["runner_result"],
        validation["message"],
        artifact_refs=validation["artifact_refs"],
        raw_payload=raw_payload,
        blockers=validation["blockers"],
        process=process,
        workspace=workspace,
    )
    return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr), rendered_argv


def _run_stage_d_preview_command(
    state: RunbookState,
    workspace: Path,
    repo_root: Path,
    command: RunbookCommand,
    dry_run: bool,
    timeout_sec: int,
) -> tuple[dict[str, Any], str, list[str]]:
    artifact_refs = _stage_b_render_artifacts(state.artifacts, workspace)
    artifact_refs["workspace"] = str(workspace)
    rendered_argv = render_argv_template(command, state.frozen_context, artifact_refs)
    argv = normalize_python_script_argv(rendered_argv, repo_root)
    if dry_run:
        process = {"executed": False, "exit_code": None, "duration_ms": None}
        artifacts = _dry_run_stage_d_preview_artifacts(command)
        result = runbook_result.create_command_result(
            state,
            command,
            "PASS",
            "Dry-run only; command not executed.",
            artifact_refs=artifacts,
            raw_payload={},
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, "", ""), rendered_argv

    execution = run_allowlisted_command(argv, repo_root, timeout_sec)
    stdout = str(execution.get("stdout") or "")
    stderr = str(execution.get("stderr") or "")
    raw_payload = _parse_stdout_json(stdout)
    exit_code = execution.get("exit_code")
    process = {
        "executed": True,
        "exit_code": exit_code,
        "duration_ms": execution.get("duration_ms"),
    }
    if exit_code != 0:
        result = runbook_result.create_command_result(
            state,
            command,
            "FAILED",
            "Command failed.",
            raw_payload=raw_payload,
            blockers=[stderr.strip() or f"exit_code={exit_code}"],
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr), rendered_argv

    validation = _validate_stage_d_preview_payload(command.command_key, raw_payload, state)
    if validation["artifact_refs"]:
        validation["artifact_refs"] = _pin_artifact_refs(
            workspace,
            state.runbook_day_id,
            validation["artifact_refs"],
            "stage_d",
        )
    result = runbook_result.create_command_result(
        state,
        command,
        validation["runner_result"],
        validation["message"],
        artifact_refs=validation["artifact_refs"],
        raw_payload=raw_payload,
        warnings=validation["warnings"],
        blockers=validation["blockers"],
        process=process,
        workspace=workspace,
    )
    return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr), rendered_argv


def _execute_stage_d_append_step(
    state: RunbookState,
    workspace: Path,
    state_path: Path,
    repo_root: Path,
    command: RunbookCommand,
    dry_run: bool,
    timeout_sec: int,
    idempotency_key: str | None,
) -> tuple[RunbookState, dict[str, Any], list[str], str, str]:
    try:
        command_result, log_text, rendered_argv = _run_stage_d_append_command(
            state,
            workspace,
            repo_root,
            command,
            dry_run,
            timeout_sec,
        )
        return state, command_result, rendered_argv, log_text, "PASS"
    except Exception as exc:
        if command.command_key == "review_append" and idempotency_key:
            state = runbook_state.mark_idempotency_failed(
                state,
                idempotency_key,
                f"review_append_exception:{type(exc).__name__}",
            )
            runbook_state.save_state(state, state_path)
        command_result = runbook_result.create_command_result(
            state,
            command,
            "FAILED",
            f"Stage D command raised {type(exc).__name__}.",
            raw_payload={},
            blockers=[str(exc)],
            process={"executed": False, "exit_code": None, "duration_ms": None},
            workspace=workspace,
        )
        return state, command_result, [], f"exception: {type(exc).__name__}: {exc}\n", "FAILED"


def _apply_stage_d_append_step_result(
    state: RunbookState,
    state_path: Path,
    workspace: Path,
    command: RunbookCommand,
    command_result: dict[str, Any],
    command_json_path: Path,
    command_txt_path: Path,
    idempotency_key: str | None,
) -> RunbookState:
    runner_result = command_result["runner_result"]
    if runner_result == "PASS":
        artifact_refs = command_result.get("outputs", {}).get("artifact_refs", {})
        state = runbook_state.complete_step(
            state,
            command.step_id,
            STAGE_D_ID,
            artifact_refs,
            workspace,
        )
        if command.command_key == "review_append" and idempotency_key:
            state = runbook_state.mark_idempotency_pass(
                state,
                idempotency_key,
                result_ref=artifact_refs.get("review_append_report_json"),
            )
        runbook_state.save_state(state, state_path)
        return state

    if command.command_key == "review_append" and idempotency_key:
        state = runbook_state.mark_idempotency_failed(
            state,
            idempotency_key,
            f"review_append_{runner_result.lower()}",
        )
    if runner_result == "BLOCKED":
        state = runbook_state.block_stage(
            state,
            STAGE_D_ID,
            f"stage_d_step_blocked:{command.command_key}",
            {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
        )
    else:
        state = runbook_state.fail_stage(
            state,
            STAGE_D_ID,
            f"stage_d_step_failed:{command.command_key}",
            {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
        )
    runbook_state.save_state(state, state_path)
    return state


def _execute_stage_e_step(
    state: RunbookState,
    workspace: Path,
    state_path: Path,
    repo_root: Path,
    command: RunbookCommand,
    dry_run: bool,
    timeout_sec: int,
    idempotency_key: str | None,
) -> tuple[RunbookState, dict[str, Any], list[str], str, str]:
    try:
        command_result, log_text, rendered_argv = _run_stage_e_command(
            state,
            workspace,
            repo_root,
            command,
            dry_run,
            timeout_sec,
        )
        return state, command_result, rendered_argv, log_text, "PASS"
    except Exception as exc:
        if command.command_key == "eod_commit" and idempotency_key:
            state = runbook_state.mark_idempotency_failed(
                state,
                idempotency_key,
                f"eod_commit_exception:{type(exc).__name__}",
            )
            runbook_state.save_state(state, state_path)
        command_result = runbook_result.create_command_result(
            state,
            command,
            "FAILED",
            f"Stage E command raised {type(exc).__name__}.",
            raw_payload={},
            blockers=[str(exc)],
            process={"executed": False, "exit_code": None, "duration_ms": None},
            workspace=workspace,
        )
        return state, command_result, [], f"exception: {type(exc).__name__}: {exc}\n", "FAILED"


def _apply_stage_e_step_result(
    state: RunbookState,
    state_path: Path,
    workspace: Path,
    command: RunbookCommand,
    command_result: dict[str, Any],
    command_json_path: Path,
    command_txt_path: Path,
    idempotency_key: str | None,
) -> RunbookState:
    runner_result = command_result["runner_result"]
    if runner_result == "PASS":
        artifact_refs = command_result.get("outputs", {}).get("artifact_refs", {})
        if command.command_key == "final_status":
            artifact_refs = {
                **artifact_refs,
                "final_status_report_json": runbook_state.canonicalize_artifact_ref(str(command_json_path), workspace),
                "final_status_report_md": runbook_state.canonicalize_artifact_ref(str(command_txt_path), workspace),
            }
        state = runbook_state.complete_step(
            state,
            command.step_id,
            STAGE_E_ID,
            artifact_refs,
            workspace,
        )
        if command.command_key == "eod_commit" and idempotency_key:
            state = runbook_state.mark_idempotency_pass(
                state,
                idempotency_key,
                result_ref=artifact_refs.get("eod_commit_report_json"),
            )
        runbook_state.save_state(state, state_path)
        return state

    if command.command_key == "eod_commit" and idempotency_key:
        state = runbook_state.mark_idempotency_failed(
            state,
            idempotency_key,
            f"eod_commit_{runner_result.lower()}",
        )
    if runner_result in {"BLOCKED", "WARNING"}:
        state = runbook_state.block_stage(
            state,
            STAGE_E_ID,
            f"stage_e_step_blocked:{command.command_key}",
            {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
        )
    else:
        state = runbook_state.fail_stage(
            state,
            STAGE_E_ID,
            f"stage_e_step_failed:{command.command_key}",
            {"command_result_json": str(command_json_path), "command_result_txt": str(command_txt_path)},
        )
    runbook_state.save_state(state, state_path)
    return state


def _run_stage_d_append_command(
    state: RunbookState,
    workspace: Path,
    repo_root: Path,
    command: RunbookCommand,
    dry_run: bool,
    timeout_sec: int,
) -> tuple[dict[str, Any], str, list[str]]:
    artifact_refs = _stage_b_render_artifacts(state.artifacts, workspace)
    artifact_refs["workspace"] = str(workspace)
    rendered_argv = render_argv_template(command, state.frozen_context, artifact_refs)
    argv = normalize_python_script_argv(rendered_argv, repo_root)
    if dry_run:
        process = {"executed": False, "exit_code": None, "duration_ms": None}
        artifacts = _dry_run_stage_d_append_artifacts(command)
        result = runbook_result.create_command_result(
            state,
            command,
            "PASS",
            "Dry-run only; command not executed.",
            artifact_refs=artifacts,
            raw_payload={},
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, "", ""), rendered_argv

    execution = run_allowlisted_command(argv, repo_root, timeout_sec)
    stdout = str(execution.get("stdout") or "")
    stderr = str(execution.get("stderr") or "")
    raw_payload = _parse_stdout_json(stdout)
    exit_code = execution.get("exit_code")
    process = {
        "executed": True,
        "exit_code": exit_code,
        "duration_ms": execution.get("duration_ms"),
    }
    if exit_code != 0:
        result = runbook_result.create_command_result(
            state,
            command,
            "FAILED",
            "Command failed.",
            raw_payload=raw_payload,
            blockers=[stderr.strip() or f"exit_code={exit_code}"],
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr), rendered_argv

    validation = _validate_stage_d_append_payload(command.command_key, raw_payload, state)
    if validation["artifact_refs"]:
        validation["artifact_refs"] = _pin_artifact_refs(
            workspace,
            state.runbook_day_id,
            validation["artifact_refs"],
            "stage_d",
        )
    result = runbook_result.create_command_result(
        state,
        command,
        validation["runner_result"],
        validation["message"],
        artifact_refs=validation["artifact_refs"],
        raw_payload=raw_payload,
        warnings=validation["warnings"],
        blockers=validation["blockers"],
        process=process,
        workspace=workspace,
    )
    return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr), rendered_argv


def _run_stage_e_command(
    state: RunbookState,
    workspace: Path,
    repo_root: Path,
    command: RunbookCommand,
    dry_run: bool,
    timeout_sec: int,
) -> tuple[dict[str, Any], str, list[str]]:
    artifact_refs = _stage_b_render_artifacts(state.artifacts, workspace)
    artifact_refs["workspace"] = str(workspace)
    rendered_argv = render_argv_template(command, state.frozen_context, artifact_refs)
    argv = normalize_python_script_argv(rendered_argv, repo_root)
    if dry_run:
        process = {"executed": False, "exit_code": None, "duration_ms": None}
        artifacts = _dry_run_stage_e_artifacts(command)
        result = runbook_result.create_command_result(
            state,
            command,
            "PASS",
            "Dry-run only; command not executed.",
            artifact_refs=artifacts,
            raw_payload={},
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, "", ""), rendered_argv

    execution = run_allowlisted_command(argv, repo_root, timeout_sec)
    stdout = str(execution.get("stdout") or "")
    stderr = str(execution.get("stderr") or "")
    raw_payload = _parse_stdout_json(stdout)
    exit_code = execution.get("exit_code")
    process = {
        "executed": True,
        "exit_code": exit_code,
        "duration_ms": execution.get("duration_ms"),
    }
    if exit_code != 0:
        result = runbook_result.create_command_result(
            state,
            command,
            "FAILED",
            "Command failed.",
            raw_payload=raw_payload,
            blockers=[stderr.strip() or f"exit_code={exit_code}"],
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr), rendered_argv

    validation = _validate_stage_e_payload(command.command_key, raw_payload, state)
    if validation["artifact_refs"]:
        validation["artifact_refs"] = _pin_artifact_refs(
            workspace,
            state.runbook_day_id,
            validation["artifact_refs"],
            "stage_e",
        )
    result = runbook_result.create_command_result(
        state,
        command,
        validation["runner_result"],
        validation["message"],
        artifact_refs=validation["artifact_refs"],
        raw_payload=raw_payload,
        warnings=validation["warnings"],
        blockers=validation["blockers"],
        process=process,
        workspace=workspace,
    )
    return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr), rendered_argv


def _stage_b_render_artifacts(artifacts: dict[str, str], workspace: Path) -> dict[str, str]:
    rendered: dict[str, str] = {}
    for key, value in artifacts.items():
        text = str(value)
        if not text or text.startswith("embedded:"):
            rendered[key] = text
            continue
        path = Path(text)
        rendered[key] = str(path if path.is_absolute() else workspace / path)
    if "execution_commit_report_json" in rendered:
        rendered["execution_commit_report"] = rendered["execution_commit_report_json"]
    if "review_append_report_json" in rendered:
        rendered["review_commit_report"] = rendered["review_append_report_json"]
    if "eod_dryrun_report_json" in rendered:
        rendered["eod_dryrun_result"] = rendered["eod_dryrun_report_json"]
    if "eod_commit_report_json" in rendered:
        rendered["eod_commit_report"] = rendered["eod_commit_report_json"]
    return rendered


def _pin_stage_b_artifact_refs(
    workspace: Path,
    runbook_day_id: str,
    artifact_refs: dict[str, str],
) -> dict[str, str]:
    return _pin_artifact_refs(workspace, runbook_day_id, artifact_refs, "stage_b")


def _pin_artifact_refs(
    workspace: Path,
    runbook_day_id: str,
    artifact_refs: dict[str, str],
    stage_subdir: str,
) -> dict[str, str]:
    pinned: dict[str, str] = {}
    destination_dir = workspace / "artifacts" / runbook_day_id / stage_subdir
    destination_dir.mkdir(parents=True, exist_ok=True)
    workspace_resolved = workspace.resolve(strict=False)
    for artifact_name, artifact_ref in artifact_refs.items():
        if not artifact_ref:
            continue
        source_path = Path(str(artifact_ref))
        if not source_path.is_absolute():
            source_path = (Path.cwd() / source_path).resolve(strict=False)
        else:
            source_path = source_path.resolve(strict=False)
        try:
            source_path.relative_to(workspace_resolved)
            pinned[artifact_name] = runbook_state.canonicalize_artifact_ref(str(source_path), workspace)
            continue
        except ValueError:
            pass
        if not source_path.exists():
            raise ValueError(f"artifact_not_found:{artifact_name}:{source_path}")
        destination_path = destination_dir / source_path.name
        shutil.copy2(source_path, destination_path)
        pinned[artifact_name] = runbook_state.canonicalize_artifact_ref(str(destination_path), workspace)
    return pinned


def _dry_run_stage_b_artifacts(command: RunbookCommand) -> dict[str, str]:
    if command.command_key == "execution_preview":
        return {
            "execution_preview_json": "dry_run/manual_execution_import_preview.json",
            "execution_preview_md": "dry_run/manual_execution_import_preview.md",
        }
    if command.command_key == "execution_reconciliation_preview":
        return {
            "execution_reconciliation_preview_json": "dry_run/execution_reconciliation_preview.json",
            "execution_reconciliation_preview_md": "dry_run/execution_reconciliation_preview.md",
        }
    if command.command_key == "execution_commit":
        return {
            "execution_commit_report_json": "dry_run/manual_execution_import_commit.json",
            "execution_commit_report_md": "dry_run/manual_execution_import_commit.md",
        }
    if command.command_key == "sync_execution_status":
        return {"execution_status_sync_report": "dry_run/manual_execution_status_sync.json"}
    return {}


def _dry_run_stage_c_artifacts(command: RunbookCommand) -> dict[str, str]:
    if command.command_key == "daily_review":
        return {
            "daily_review_report_md": "dry_run/paper_daily_review_summary.md",
            "manual_review_template_csv": "dry_run/paper_manual_review_log_template.csv",
            "manual_review_template_md": "dry_run/paper_manual_review_log_template.md",
        }
    if command.command_key == "export_review_template":
        return {
            "notion_review_template_report_json": "dry_run/manual_review_template_export.json",
            "notion_review_template_report_md": "dry_run/manual_review_template_export.md",
        }
    return {}


def _dry_run_stage_d_preview_artifacts(command: RunbookCommand) -> dict[str, str]:
    if command.command_key == "review_preview":
        return {
            "review_preview_json": "dry_run/manual_review_import_preview.json",
            "review_preview_md": "dry_run/manual_review_import_preview.md",
        }
    return {}


def _dry_run_stage_d_append_artifacts(command: RunbookCommand) -> dict[str, str]:
    if command.command_key == "review_append":
        return {
            "review_append_report_json": "dry_run/manual_review_import_commit.json",
            "review_append_report_md": "dry_run/manual_review_import_commit.md",
            "review_commit_report": "dry_run/manual_review_import_commit.json",
        }
    if command.command_key == "sync_review_status":
        return {
            "review_status_sync_report_json": "dry_run/manual_review_status_sync.json",
            "review_status_sync_report_md": "dry_run/manual_review_status_sync.md",
        }
    return {}


def _dry_run_stage_e_artifacts(command: RunbookCommand) -> dict[str, str]:
    if command.command_key == "eod_dryrun":
        return {
            "eod_dryrun_report_json": "dry_run/eod_dryrun.json",
            "eod_dryrun_report_md": "dry_run/eod_dryrun.md",
            "eod_dryrun_result": "dry_run/eod_dryrun.json",
        }
    if command.command_key == "eod_commit":
        return {
            "eod_commit_report_json": "dry_run/eod_commit.json",
            "eod_commit_report_md": "dry_run/eod_commit.md",
            "eod_commit_report": "dry_run/eod_commit.json",
        }
    if command.command_key == "final_status":
        return {
            "final_status_report_json": "dry_run/final_status.json",
            "final_status_report_md": "dry_run/final_status.md",
        }
    return {}


def _validate_stage_b_payload(command_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if command_key == "execution_preview":
        return _validate_execution_preview_payload(payload)
    if command_key == "execution_reconciliation_preview":
        return _validate_reconciliation_preview_payload(payload)
    if command_key == "execution_commit":
        return _validate_execution_commit_payload(payload)
    if command_key == "sync_execution_status":
        return _validate_execution_sync_payload(payload)
    return _payload_validation("PASS", "Command completed successfully.", {}, [])


def _validate_stage_c_payload(command_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if command_key == "daily_review":
        return _validate_daily_review_payload(payload)
    if command_key == "export_review_template":
        return _validate_export_review_template_payload(payload)
    return _payload_validation("PASS", "Command completed successfully.", {}, [])


def _validate_stage_d_preview_payload(
    command_key: str,
    payload: dict[str, Any],
    state: RunbookState,
) -> dict[str, Any]:
    if command_key == "review_preview":
        return _validate_review_preview_payload(payload, state)
    return _payload_validation("PASS", "Command completed successfully.", {}, [])


def _validate_stage_d_append_payload(
    command_key: str,
    payload: dict[str, Any],
    state: RunbookState,
) -> dict[str, Any]:
    if command_key == "review_append":
        return _validate_review_append_payload(payload, state)
    if command_key == "sync_review_status":
        return _validate_review_sync_payload(payload, state)
    return _payload_validation("PASS", "Command completed successfully.", {}, [])


def _validate_stage_e_payload(
    command_key: str,
    payload: dict[str, Any],
    state: RunbookState,
) -> dict[str, Any]:
    if command_key == "eod_dryrun":
        return _validate_eod_dryrun_payload(payload, state)
    if command_key == "eod_commit":
        return _validate_eod_commit_payload(payload, state)
    if command_key == "final_status":
        return _validate_final_status_payload(payload, state)
    return _payload_validation("PASS", "Command completed successfully.", {}, [])


def _validate_review_preview_payload(payload: dict[str, Any], state: RunbookState) -> dict[str, Any]:
    blockers = []
    warnings = []
    account_id = str(payload.get("account_id") or "").strip()
    review_date = str(payload.get("review_date") or "").strip()
    if account_id != state.frozen_context.account_id:
        blockers.append("account_id must match frozen context")
    if review_date != state.frozen_context.trade_date:
        blockers.append("review_date must match trade_date")
    if _int_payload(payload, "candidate_count") <= 0:
        blockers.append("candidate_count must be greater than 0")
    if _int_payload(payload, "fail_count") != 0:
        blockers.append("fail_count must be 0")
    if _int_payload(payload, "blocked_count") != 0:
        blockers.append("blocked_count must be 0")
    append_allowed = str(payload.get("append_allowed") or "").strip().lower()
    if append_allowed == "false":
        blockers.append("append_allowed must not be false")
    elif append_allowed == "true_with_warnings":
        warnings.append("append_allowed is true_with_warnings")
    json_path = str(payload.get("json_path") or payload.get("preview_json_path") or "").strip()
    markdown_path = str(payload.get("markdown_path") or payload.get("preview_markdown_path") or "").strip()
    if not json_path or not Path(json_path).exists():
        blockers.append("preview json_path must exist")
    if markdown_path and not Path(markdown_path).exists():
        blockers.append("preview markdown_path must exist")
    elif not markdown_path:
        blockers.append("preview markdown_path must exist")
    artifacts = _existing_artifacts_from_payload(
        payload,
        {
            "json_path": "review_preview_json",
            "preview_json_path": "review_preview_json",
            "markdown_path": "review_preview_md",
            "preview_markdown_path": "review_preview_md",
        },
    )
    runner_result = "FAILED" if any("must exist" in blocker for blocker in blockers) else "BLOCKED" if blockers else "WARNING" if warnings else "PASS"
    message = (
        "Manual review import preview artifact is pinned."
        if runner_result == "PASS"
        else "Manual review import preview has warnings."
        if runner_result == "WARNING"
        else "Manual review import preview failed validation."
    )
    return _payload_validation(
        runner_result,
        message,
        artifacts if runner_result in {"PASS", "WARNING"} else {},
        blockers,
        warnings,
    )


def _validate_review_append_payload(payload: dict[str, Any], state: RunbookState) -> dict[str, Any]:
    blockers = []
    status = str(payload.get("status") or payload.get("runner_result") or "").upper()
    if status not in {"COMMITTED", "PASS"}:
        blockers.append("status must be COMMITTED/PASS")
    if str(payload.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("account_id must match frozen context")
    if str(payload.get("review_date") or "").strip() != state.frozen_context.trade_date:
        blockers.append("review_date must match trade_date")
    if _int_payload(payload, "appended_count") <= 0:
        blockers.append("appended_count must be greater than 0")
    if _int_payload(payload, "failed_count") != 0:
        blockers.append("failed_count must be 0")
    commit_json = str(payload.get("commit_json_path") or payload.get("json_path") or "").strip()
    commit_md = str(payload.get("commit_markdown_path") or payload.get("markdown_path") or "").strip()
    if not commit_json or not Path(commit_json).exists():
        blockers.append("commit_json_path must exist")
    if commit_md and not Path(commit_md).exists():
        blockers.append("commit_markdown_path must exist")
    elif not commit_md:
        blockers.append("commit_markdown_path must exist")
    artifacts = {
        "review_append_report_json": commit_json,
        "review_append_report_md": commit_md,
        "review_commit_report": commit_json,
    }
    return _payload_validation(
        "FAILED" if any("must exist" in blocker for blocker in blockers) else "BLOCKED" if blockers else "PASS",
        "Manual review append report is pinned." if not blockers else "Manual review append failed validation.",
        artifacts if not blockers else {},
        blockers,
    )


def _validate_review_sync_payload(payload: dict[str, Any], state: RunbookState) -> dict[str, Any]:
    blockers = []
    if str(payload.get("overall_status") or "").upper() != "SUCCESS":
        blockers.append("overall_status must be SUCCESS")
    if str(payload.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("account_id must match frozen context")
    if str(payload.get("review_date") or "").strip() != state.frozen_context.trade_date:
        blockers.append("review_date must match trade_date")
    candidate_count = _int_payload(payload, "candidate_count")
    if candidate_count <= 0:
        blockers.append("candidate_count must be greater than 0")
    if _int_payload(payload, "updated_count") != candidate_count:
        blockers.append("updated_count must equal candidate_count")
    if _int_payload(payload, "failed_count") != 0:
        blockers.append("failed_count must be 0")
    sync_json = str(payload.get("sync_json_path") or "").strip()
    sync_md = str(payload.get("sync_markdown_path") or "").strip()
    if not sync_json or not Path(sync_json).exists():
        blockers.append("sync_json_path must exist")
    if sync_md and not Path(sync_md).exists():
        blockers.append("sync_markdown_path must exist")
    elif not sync_md:
        blockers.append("sync_markdown_path must exist")
    artifacts = {
        "review_status_sync_report_json": sync_json,
        "review_status_sync_report_md": sync_md,
    }
    return _payload_validation(
        "FAILED" if any("must exist" in blocker for blocker in blockers) else "BLOCKED" if blockers else "PASS",
        "Notion review status sync completed." if not blockers else "Notion review status sync failed validation.",
        artifacts if not blockers else {},
        blockers,
    )


def _validate_eod_dryrun_payload(payload: dict[str, Any], state: RunbookState) -> dict[str, Any]:
    blockers = []
    status = str(payload.get("runner_result") or payload.get("status") or "").upper()
    if status != "PASS":
        blockers.append("runner_result/status must be PASS")
    if str(payload.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("account_id must match frozen context")
    date_value = str(payload.get("date") or payload.get("trade_date") or "").strip()
    if date_value != state.frozen_context.trade_date:
        blockers.append("date must match trade_date")
    if _int_payload(payload, "fail_count") != 0:
        blockers.append("fail_count must be 0")
    if _int_payload(payload, "blocked_count") != 0:
        blockers.append("blocked_count must be 0")
    if str(payload.get("commit_allowed")).lower() != "true":
        blockers.append("commit_allowed must be true")
    dryrun_json = str(payload.get("json_path") or payload.get("dryrun_json_path") or "").strip()
    dryrun_md = str(payload.get("markdown_path") or payload.get("dryrun_markdown_path") or "").strip()
    if not dryrun_json or not Path(dryrun_json).exists():
        blockers.append("dryrun json_path must exist")
    if dryrun_md and not Path(dryrun_md).exists():
        blockers.append("dryrun markdown_path must exist")
    elif not dryrun_md:
        blockers.append("dryrun markdown_path must exist")
    artifacts = {
        "eod_dryrun_report_json": dryrun_json,
        "eod_dryrun_report_md": dryrun_md,
        "eod_dryrun_result": dryrun_json,
    }
    return _payload_validation(
        "FAILED" if any("must exist" in blocker for blocker in blockers) else "BLOCKED" if blockers else "PASS",
        "EOD dry-run report is pinned." if not blockers else "EOD dry-run failed validation.",
        artifacts if not blockers else {},
        blockers,
    )


def _validate_eod_commit_payload(payload: dict[str, Any], state: RunbookState) -> dict[str, Any]:
    blockers = []
    status = str(payload.get("status") or payload.get("runner_result") or "").upper()
    if status not in {"COMMITTED", "PASS"}:
        blockers.append("status must be COMMITTED/PASS")
    if str(payload.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("account_id must match frozen context")
    date_value = str(payload.get("date") or payload.get("trade_date") or "").strip()
    if date_value != state.frozen_context.trade_date:
        blockers.append("date must match trade_date")
    if _int_payload(payload, "failed_count") != 0:
        blockers.append("failed_count must be 0")
    for field in ("current_state_written", "account_snapshot_written", "position_snapshot_written"):
        if payload.get(field) is not True:
            blockers.append(f"{field} must be true")
    commit_json = str(payload.get("json_path") or payload.get("commit_json_path") or "").strip()
    commit_md = str(payload.get("markdown_path") or payload.get("commit_markdown_path") or "").strip()
    if not commit_json or not Path(commit_json).exists():
        blockers.append("commit json_path must exist")
    if commit_md and not Path(commit_md).exists():
        blockers.append("commit markdown_path must exist")
    elif not commit_md:
        blockers.append("commit markdown_path must exist")
    artifacts = {
        "eod_commit_report_json": commit_json,
        "eod_commit_report_md": commit_md,
        "eod_commit_report": commit_json,
    }
    return _payload_validation(
        "FAILED" if any("must exist" in blocker for blocker in blockers) else "BLOCKED" if blockers else "PASS",
        "EOD commit report is pinned." if not blockers else "EOD commit failed validation.",
        artifacts if not blockers else {},
        blockers,
    )


def _validate_final_status_payload(payload: dict[str, Any], state: RunbookState) -> dict[str, Any]:
    blockers = []
    warnings = []
    status = str(
        payload.get("runner_result")
        or payload.get("overall_status")
        or payload.get("workflow_status")
        or ""
    ).upper()
    if str(payload.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("account_id must match frozen context")
    date_value = str(payload.get("trade_date") or payload.get("date") or payload.get("target_date") or "").strip()
    if date_value and date_value != state.frozen_context.trade_date:
        blockers.append("date must match trade_date")
    unresolved_count = _int_payload(payload, "unresolved_error_count")
    if unresolved_count != 0:
        blockers.append("unresolved_error_count must be 0")
    if status == "WARNING":
        warnings.append("final_status returned WARNING")
    elif status not in {"PASS", "OK", "READY", "DONE"}:
        blockers.append("final_status must be PASS")
    runner_result = "BLOCKED" if blockers else "WARNING" if warnings else "PASS"
    return _payload_validation(
        runner_result,
        "Final status is PASS." if runner_result == "PASS" else "Final status requires operator review.",
        {},
        blockers,
        warnings,
    )


def _validate_daily_review_payload(payload: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    status = str(payload.get("status") or "").upper()
    validation_result = str(payload.get("validation_result") or "").upper()
    if status and status != "PASS":
        blockers.append("status must be PASS")
    if validation_result == "FAIL":
        blockers.append("validation_result must not be FAIL")
    template_csv = str(payload.get("manual_review_template_csv") or "").strip()
    template_md = str(payload.get("manual_review_template_md") or "").strip()
    if not template_csv or not Path(template_csv).exists():
        blockers.append("manual_review_template_csv must exist")
    if not template_md or not Path(template_md).exists():
        blockers.append("manual_review_template_md must exist")
    artifacts = _existing_artifacts_from_payload(
        payload,
        {
            "daily_review_report_md": "daily_review_report_md",
            "report_index_md": "report_index_md",
            "manual_review_template_csv": "manual_review_template_csv",
            "manual_review_template_md": "manual_review_template_md",
            "validation_report_md": "validation_report_md",
            "validation_issues_csv": "validation_issues_csv",
        },
    )
    return _payload_validation(
        "FAILED" if blockers else "PASS",
        "Daily review artifacts are pinned." if not blockers else "Daily review failed validation.",
        artifacts if not blockers else {},
        blockers,
    )


def _validate_export_review_template_payload(payload: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    candidate_count = _int_payload(payload, "candidate_count")
    if candidate_count <= 0:
        blockers.append("candidate_count must be greater than 0")
    if _int_payload(payload, "failed_count") != 0:
        blockers.append("failed_count must be 0")
    processed_count = (
        _int_payload(payload, "create_count")
        + _int_payload(payload, "update_count")
        + _int_payload(payload, "skip_count")
    )
    if processed_count < candidate_count:
        blockers.append("create_count + update_count + skip_count must cover candidate_count")
    source_template_path = str(payload.get("source_template_path") or "").strip()
    if source_template_path and not Path(source_template_path).exists():
        blockers.append("source_template_path must exist")
    artifacts = _existing_artifacts_from_payload(
        payload,
        {
            "source_template_path": "manual_review_template_csv",
            "json_path": "notion_review_template_report_json",
            "report_json_path": "notion_review_template_report_json",
            "markdown_path": "notion_review_template_report_md",
            "report_markdown_path": "notion_review_template_report_md",
        },
    )
    return _payload_validation(
        "FAILED" if blockers else "PASS",
        "Manual review template was exported to Notion." if not blockers else "Manual review template export failed validation.",
        artifacts if not blockers else {},
        blockers,
    )


def _existing_artifacts_from_payload(payload: dict[str, Any], mapping: dict[str, str]) -> dict[str, str]:
    artifacts: dict[str, str] = {}
    for payload_key, artifact_key in mapping.items():
        artifact_ref = str(payload.get(payload_key) or "").strip()
        if artifact_ref and Path(artifact_ref).exists():
            artifacts[artifact_key] = artifact_ref
    return artifacts


def _validate_execution_preview_payload(payload: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if _int_payload(payload, "candidate_count") <= 0:
        blockers.append("candidate_count must be greater than 0")
    if _int_payload(payload, "fail_count") != 0:
        blockers.append("fail_count must be 0")
    if str(payload.get("commit_allowed")).lower() != "true":
        blockers.append("commit_allowed must be true")
    json_path = str(payload.get("json_path") or "").strip()
    markdown_path = str(payload.get("markdown_path") or "").strip()
    if not json_path or not Path(json_path).exists():
        blockers.append("json_path must exist")
    artifacts = {
        "execution_preview_json": json_path,
        "execution_preview_md": markdown_path,
    }
    return _payload_validation(
        "BLOCKED" if blockers else "PASS",
        "Execution import preview is pinned." if not blockers else "Execution import preview is not commit-ready.",
        artifacts if not blockers else {},
        blockers,
    )


def _validate_reconciliation_preview_payload(payload: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if str(payload.get("runner_result") or "").upper() != "PASS":
        blockers.append("reconciliation runner_result must be PASS")
    for field in ("blocked_count", "needs_review_count", "warning_count", "missing_count", "extra_count"):
        if _int_payload(payload, field) != 0:
            blockers.append(f"{field} must be 0")
    preview_json = str(payload.get("preview_json") or "").strip()
    preview_md = str(payload.get("preview_md") or "").strip()
    if not preview_json or not Path(preview_json).exists():
        blockers.append("preview_json must exist")
    artifacts = {
        "execution_reconciliation_preview_json": preview_json,
        "execution_reconciliation_preview_md": preview_md,
    }
    return _payload_validation(
        "BLOCKED" if blockers else "PASS",
        "Execution reconciliation preview is pinned." if not blockers else "Execution reconciliation preview is not PASS.",
        artifacts if not blockers else {},
        blockers,
    )


def _validate_execution_commit_payload(payload: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if str(payload.get("status") or "").upper() != "COMMITTED":
        blockers.append("status must be COMMITTED")
    if _int_payload(payload, "committed_row_count") <= 0:
        blockers.append("committed_row_count must be greater than 0")
    for field in ("current_state_written", "account_snapshot_written", "position_snapshot_written"):
        if payload.get(field) is not True:
            blockers.append(f"{field} must be true")
    commit_json = str(payload.get("commit_json_path") or "").strip()
    commit_md = str(payload.get("commit_markdown_path") or "").strip()
    if not commit_json or not Path(commit_json).exists():
        blockers.append("commit_json_path must exist")
    artifacts = {
        "execution_commit_report_json": commit_json,
        "execution_commit_report_md": commit_md,
    }
    return _payload_validation(
        "FAILED" if blockers else "PASS",
        "Execution commit report is pinned." if not blockers else "Execution commit result failed validation.",
        artifacts if not blockers else {},
        blockers,
    )


def _validate_execution_sync_payload(payload: dict[str, Any]) -> dict[str, Any]:
    blockers = []
    if str(payload.get("overall_status") or "").upper() != "SUCCESS":
        blockers.append("overall_status must be SUCCESS")
    candidate_count = _int_payload(payload, "candidate_count")
    if _int_payload(payload, "updated_count") != candidate_count:
        blockers.append("updated_count must equal candidate_count")
    if _int_payload(payload, "failed_count") != 0:
        blockers.append("failed_count must be 0")
    sync_json = str(payload.get("sync_json_path") or "").strip()
    sync_md = str(payload.get("sync_markdown_path") or "").strip()
    if not sync_json or not Path(sync_json).exists():
        blockers.append("sync_json_path must exist")
    artifacts = {
        "execution_status_sync_report": sync_json,
        "execution_status_sync_report_json": sync_json,
        "execution_status_sync_report_md": sync_md,
    }
    return _payload_validation(
        "FAILED" if blockers else "PASS",
        "Notion execution status sync completed." if not blockers else "Notion execution status sync failed validation.",
        artifacts if not blockers else {},
        blockers,
    )


def _payload_validation(
    runner_result: str,
    message: str,
    artifact_refs: dict[str, str],
    blockers: list[str],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "runner_result": runner_result,
        "message": message,
        "artifact_refs": artifact_refs,
        "blockers": blockers,
        "warnings": list(warnings or []),
    }


def _blocked_command_result(
    state: RunbookState,
    workspace: Path,
    command: RunbookCommand,
    message: str,
) -> dict[str, Any]:
    return runbook_result.create_command_result(
        state,
        command,
        "BLOCKED",
        message,
        raw_payload={},
        blockers=[message],
        process={"executed": False, "exit_code": None, "duration_ms": None},
        workspace=workspace,
    )


def _skipped_stage_d_append_result(
    state: RunbookState,
    workspace: Path,
    command: RunbookCommand,
    message: str,
) -> dict[str, Any]:
    artifacts: dict[str, str] = {}
    report_ref = state.artifacts.get("review_append_report_json")
    report_md = state.artifacts.get("review_append_report_md")
    if report_ref:
        artifacts["review_append_report_json"] = report_ref
        artifacts["review_commit_report"] = report_ref
    if report_md:
        artifacts["review_append_report_md"] = report_md
    return runbook_result.create_command_result(
        state,
        command,
        "SKIPPED",
        message,
        artifact_refs=artifacts,
        raw_payload={"reason_code": "review_append_already_committed"},
        process={"executed": False, "exit_code": None, "duration_ms": None},
        workspace=workspace,
    )


def _skipped_stage_e_commit_result(
    state: RunbookState,
    workspace: Path,
    command: RunbookCommand,
    message: str,
) -> dict[str, Any]:
    artifacts: dict[str, str] = {}
    report_ref = state.artifacts.get("eod_commit_report_json")
    report_md = state.artifacts.get("eod_commit_report_md")
    if report_ref:
        artifacts["eod_commit_report_json"] = report_ref
        artifacts["eod_commit_report"] = report_ref
    if report_md:
        artifacts["eod_commit_report_md"] = report_md
    return runbook_result.create_command_result(
        state,
        command,
        "SKIPPED",
        message,
        artifact_refs=artifacts,
        raw_payload={"reason_code": "eod_commit_already_committed"},
        process={"executed": False, "exit_code": None, "duration_ms": None},
        workspace=workspace,
    )


def _review_append_idempotency_key(state: RunbookState, workspace: Path) -> str | None:
    preview_ref = state.artifacts.get("review_preview_json")
    if not preview_ref:
        return None
    try:
        return runbook_state.build_idempotency_key(
            state,
            "review_append",
            {"review_preview_json": preview_ref},
            workspace,
        )
    except ValueError:
        return None


def _eod_commit_idempotency_key(state: RunbookState, workspace: Path) -> str | None:
    dryrun_ref = state.artifacts.get("eod_dryrun_report_json") or state.artifacts.get("eod_dryrun_result")
    if not dryrun_ref:
        return None
    try:
        return runbook_state.build_idempotency_key(
            state,
            "eod_commit",
            {"eod_dryrun_report_json": dryrun_ref},
            workspace,
        )
    except ValueError:
        return None


def _write_command_result_and_log(
    workspace: Path,
    state: RunbookState,
    command: RunbookCommand,
    command_result: dict[str, Any],
    log_text: str,
) -> tuple[Path, Path]:
    command_json_path, command_txt_path = runbook_result.write_command_result(
        workspace,
        state,
        command,
        command_result,
    )
    _write_command_log(workspace, command_json_path, log_text)
    return command_json_path, command_txt_path


def _int_payload(payload: dict[str, Any], field: str) -> int:
    try:
        return int(payload.get(field) or 0)
    except (TypeError, ValueError):
        return 0


def _last_raw_value(command_results: list[dict[str, Any]], field: str) -> Any:
    for result in reversed(command_results):
        raw_payload = result.get("raw_payload")
        if isinstance(raw_payload, dict) and field in raw_payload:
            return raw_payload.get(field)
    return None


def _run_stage_a_command(
    state: RunbookState,
    workspace: Path,
    repo_root: Path,
    command: RunbookCommand,
    dry_run: bool,
    timeout_sec: int,
) -> tuple[dict[str, Any], str]:
    rendered_argv = render_argv_template(command, state.frozen_context, state.artifacts)
    argv = normalize_python_script_argv(rendered_argv, repo_root)
    if dry_run:
        process = {
            "executed": False,
            "exit_code": None,
            "duration_ms": None,
        }
        result = runbook_result.create_command_result(
            state,
            command,
            "PASS",
            "Dry-run only; command not executed.",
            raw_payload={},
            process=process,
            workspace=workspace,
        )
        return result, _format_command_log(rendered_argv, argv, repo_root, process, "", "")

    execution = run_allowlisted_command(argv, repo_root, timeout_sec)
    stdout = str(execution.get("stdout") or "")
    stderr = str(execution.get("stderr") or "")
    exit_code = execution.get("exit_code")
    runner_result = "PASS" if exit_code == 0 else "FAILED"
    process = {
        "executed": True,
        "exit_code": exit_code,
        "duration_ms": execution.get("duration_ms"),
    }
    result = runbook_result.create_command_result(
        state,
        command,
        runner_result,
        "Command completed successfully." if runner_result == "PASS" else "Command failed.",
        raw_payload=_parse_stdout_json(stdout),
        blockers=[] if runner_result == "PASS" else [stderr.strip() or f"exit_code={exit_code}"],
        process=process,
        workspace=workspace,
    )
    return result, _format_command_log(rendered_argv, argv, repo_root, process, stdout, stderr)


def _parse_stdout_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    parsed = _extract_last_json_value(text)
    if parsed is None:
        return {}
    return parsed if isinstance(parsed, dict) else {"json": parsed}


def _extract_last_json_value(text: str) -> Any | None:
    decoder = json.JSONDecoder()
    candidates: list[Any] = []
    for index, char in enumerate(text):
        if char not in "{[":
            continue
        try:
            parsed, end_index = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if text[index + end_index :].strip():
            continue
        candidates.append(parsed)
    if candidates:
        return candidates[-1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _format_command_log(
    rendered_argv: Sequence[str],
    argv: Sequence[str],
    cwd: Path,
    process: dict[str, Any],
    stdout: str,
    stderr: str,
) -> str:
    return "\n".join(
        [
            f"rendered_argv: {json.dumps(list(rendered_argv), ensure_ascii=False)}",
            f"normalized_argv: {json.dumps(list(argv), ensure_ascii=False)}",
            f"argv: {json.dumps(list(argv), ensure_ascii=False)}",
            f"cwd: {cwd}",
            f"exit_code: {process.get('exit_code')}",
            f"duration_ms: {process.get('duration_ms')}",
            "stdout:",
            stdout,
            "stderr:",
            stderr,
            "",
        ]
    )


def _write_command_log(workspace: Path, command_json_path: Path, log_text: str) -> None:
    result = json.loads(command_json_path.read_text(encoding="utf-8"))
    log_ref = result.get("outputs", {}).get("log_ref")
    if not log_ref:
        return
    log_path = workspace / str(log_ref)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(log_text, encoding="utf-8")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Runbook stage runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage_a = subparsers.add_parser("stage-a", help="Run Stage A Step 0-5")
    stage_a.add_argument("--workspace", type=Path, required=True)
    stage_a.add_argument("--account-id", required=True)
    stage_a.add_argument("--data-date", required=True)
    stage_a.add_argument("--trade-date", required=True)
    stage_a.add_argument("--timezone", default="Asia/Seoul")
    stage_a.add_argument("--dry-run", action="store_true")
    stage_a.add_argument("--confirm-paper-test", action="store_true")
    stage_a.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)

    stage_b = subparsers.add_parser("stage-b", help="Run Stage B Step 7-9")
    stage_b.add_argument("--workspace", type=Path, required=True)
    stage_b.add_argument("--account-id", required=True)
    stage_b.add_argument("--data-date", required=True)
    stage_b.add_argument("--trade-date", required=True)
    stage_b.add_argument("--timezone", default="Asia/Seoul")
    stage_b.add_argument("--dry-run", action="store_true")
    stage_b.add_argument("--confirm-paper-test", action="store_true")
    stage_b.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)

    stage_c = subparsers.add_parser("stage-c", help="Run Stage C Step 10-11 review prep")
    stage_c.add_argument("--workspace", type=Path, required=True)
    stage_c.add_argument("--account-id", required=True)
    stage_c.add_argument("--data-date", required=True)
    stage_c.add_argument("--trade-date", required=True)
    stage_c.add_argument("--timezone", default="Asia/Seoul")
    stage_c.add_argument("--dry-run", action="store_true")
    stage_c.add_argument("--confirm-paper-test", action="store_true")
    stage_c.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)

    stage_b_review = subparsers.add_parser("stage-b-review", help="Deprecated alias for stage-c")
    stage_b_review.add_argument("--workspace", type=Path, required=True)
    stage_b_review.add_argument("--account-id", required=True)
    stage_b_review.add_argument("--data-date", required=True)
    stage_b_review.add_argument("--trade-date", required=True)
    stage_b_review.add_argument("--timezone", default="Asia/Seoul")
    stage_b_review.add_argument("--dry-run", action="store_true")
    stage_b_review.add_argument("--confirm-paper-test", action="store_true")
    stage_b_review.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)

    gate2 = subparsers.add_parser("gate2", help="Check Gate 2 manual review readiness")
    gate2.add_argument("--workspace", type=Path, required=True)
    gate2.add_argument("--account-id", required=True)
    gate2.add_argument("--data-date", required=True)
    gate2.add_argument("--trade-date", required=True)
    gate2.add_argument("--timezone", default="Asia/Seoul")
    gate2.add_argument("--confirm-paper-test", action="store_true")

    stage_d_preview = subparsers.add_parser("stage-d-preview", help="Run Stage D Step 13 review preview")
    stage_d_preview.add_argument("--workspace", type=Path, required=True)
    stage_d_preview.add_argument("--account-id", required=True)
    stage_d_preview.add_argument("--data-date", required=True)
    stage_d_preview.add_argument("--trade-date", required=True)
    stage_d_preview.add_argument("--timezone", default="Asia/Seoul")
    stage_d_preview.add_argument("--dry-run", action="store_true")
    stage_d_preview.add_argument("--confirm-paper-test", action="store_true")
    stage_d_preview.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)

    stage_d_append = subparsers.add_parser("stage-d-append", help="Run Stage D Step 14-15 review append and sync")
    stage_d_append.add_argument("--workspace", type=Path, required=True)
    stage_d_append.add_argument("--account-id", required=True)
    stage_d_append.add_argument("--data-date", required=True)
    stage_d_append.add_argument("--trade-date", required=True)
    stage_d_append.add_argument("--timezone", default="Asia/Seoul")
    stage_d_append.add_argument("--dry-run", action="store_true")
    stage_d_append.add_argument("--confirm-paper-test", action="store_true")
    stage_d_append.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)

    stage_e = subparsers.add_parser("stage-e", help="Run Stage E Step 16-18 EOD close")
    stage_e.add_argument("--workspace", type=Path, required=True)
    stage_e.add_argument("--account-id", required=True)
    stage_e.add_argument("--data-date", required=True)
    stage_e.add_argument("--trade-date", required=True)
    stage_e.add_argument("--timezone", default="Asia/Seoul")
    stage_e.add_argument("--dry-run", action="store_true")
    stage_e.add_argument("--confirm-paper-test", action="store_true")
    stage_e.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "stage-a":
        result = run_stage_a(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            timezone=args.timezone,
            dry_run=args.dry_run,
            confirm_paper_test=args.confirm_paper_test,
            timeout_sec=args.timeout_sec,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("runner_result") == "PASS" else 1
    if args.command == "stage-b":
        result = run_stage_b(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            timezone=args.timezone,
            dry_run=args.dry_run,
            confirm_paper_test=args.confirm_paper_test,
            timeout_sec=args.timeout_sec,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("runner_result") == "PASS" else 1
    if args.command == "stage-c":
        result = run_stage_c(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            timezone=args.timezone,
            dry_run=args.dry_run,
            confirm_paper_test=args.confirm_paper_test,
            timeout_sec=args.timeout_sec,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("runner_result") == "PASS" else 1
    if args.command == "stage-b-review":
        result = run_stage_b_review(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            timezone=args.timezone,
            dry_run=args.dry_run,
            confirm_paper_test=args.confirm_paper_test,
            timeout_sec=args.timeout_sec,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("runner_result") == "PASS" else 1
    if args.command == "gate2":
        result = check_gate2(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            timezone=args.timezone,
            confirm_paper_test=args.confirm_paper_test,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("runner_result") in {"PASS", "WAIT"} else 1
    if args.command == "stage-d-preview":
        result = run_stage_d_preview(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            timezone=args.timezone,
            dry_run=args.dry_run,
            confirm_paper_test=args.confirm_paper_test,
            timeout_sec=args.timeout_sec,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("runner_result") in {"PASS", "WARNING"} else 1
    if args.command == "stage-d-append":
        result = run_stage_d_append(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            timezone=args.timezone,
            dry_run=args.dry_run,
            confirm_paper_test=args.confirm_paper_test,
            timeout_sec=args.timeout_sec,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("runner_result") == "PASS" else 1
    if args.command == "stage-e":
        result = run_stage_e(
            workspace=args.workspace,
            account_id=args.account_id,
            data_date=args.data_date,
            trade_date=args.trade_date,
            timezone=args.timezone,
            dry_run=args.dry_run,
            confirm_paper_test=args.confirm_paper_test,
            timeout_sec=args.timeout_sec,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("runner_result") == "PASS" else 1
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
