from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import runbook_command_registry as registry
from scripts import runbook_result
from scripts import runbook_state
from scripts.runbook_command_registry import RunbookCommand
from scripts.runbook_state import RunbookState


STAGE_A_ID = "A"
STAGE_A_STEP_IDS = tuple(range(0, 6))
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


def run_stage_a(
    workspace: Path,
    account_id: str,
    data_date: str,
    trade_date: str,
    timezone: str = "Asia/Seoul",
    dry_run: bool = False,
    repo_root: Path | None = None,
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
    commands: Sequence[RunbookCommand] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace)
    repo_root = repo_root or Path(__file__).resolve().parents[1]
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
        }

    if not runbook_state.context_matches_state(state, account_id, data_date, trade_date):
        state = runbook_state.block_stage(state, STAGE_A_ID, "context_mismatch_existing_runbook_state")
        runbook_state.save_state(state, state_path)
        return {
            "runner_result": "BLOCKED",
            "stage_id": STAGE_A_ID,
            "runbook_day_id": state.runbook_day_id,
            "reason": "context_mismatch_existing_runbook_state",
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

    return {
        "runner_result": stage_summary["runner_result"],
        "stage_id": STAGE_A_ID,
        "runbook_day_id": state.runbook_day_id,
        "state_path": str(state_path),
        "stage_summary_json": str(stage_summary_json),
        "stage_summary_txt": str(stage_summary_txt),
        "command_results": [
            step["result_json_ref"]
            for step in stage_summary["steps"]
            if step.get("result_json_ref")
        ],
    }


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
        return result, _format_command_log(argv, repo_root, process, "", "")

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
    return result, _format_command_log(argv, repo_root, process, stdout, stderr)


def _parse_stdout_json(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {"json": parsed}


def _format_command_log(
    argv: Sequence[str],
    cwd: Path,
    process: dict[str, Any],
    stdout: str,
    stderr: str,
) -> str:
    return "\n".join(
        [
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
    stage_a.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
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
            timeout_sec=args.timeout_sec,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("runner_result") == "PASS" else 1
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
