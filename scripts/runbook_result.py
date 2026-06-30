from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from scripts.runbook_command_registry import RunbookCommand
from scripts.runbook_state import RunbookState, canonicalize_artifact_refs


COMMAND_RESULT_SCHEMA_VERSION = "runbook_command_result.v1"
STAGE_SUMMARY_SCHEMA_VERSION = "runbook_stage_summary.v1"
COMMAND_RUNS_DIRNAME = "command_runs"
STAGE_RUNS_DIRNAME = "stage_runs"
ALLOWED_RUNNER_RESULTS = {"PASS", "WAIT", "BLOCKED", "FAILED", "WARNING", "SKIPPED"}
RESULT_PRIORITY = ("FAILED", "BLOCKED", "WAIT", "WARNING", "PASS")


def _now_iso(timezone: str) -> str:
    try:
        tz = ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {timezone}") from exc
    return datetime.now(tz).isoformat(timespec="microseconds")


def _filename_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S%f")


def _safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value).strip())
    return cleaned.strip("_") or "unknown"


def _frozen_context_dict(state: RunbookState) -> dict[str, str]:
    return {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }


def get_command_runs_dir(workspace: Path, runbook_day_id: str) -> Path:
    return workspace / COMMAND_RUNS_DIRNAME / _safe_filename_part(runbook_day_id)


def get_stage_runs_dir(workspace: Path, runbook_day_id: str) -> Path:
    return workspace / STAGE_RUNS_DIRNAME / _safe_filename_part(runbook_day_id)


def get_command_result_paths(
    workspace: Path,
    runbook_day_id: str,
    step_id: int,
    command_key: str,
    timestamp: str | None = None,
) -> dict[str, Path]:
    timestamp = timestamp or _filename_timestamp()
    base_name = f"{timestamp}_{step_id:03d}_{_safe_filename_part(command_key)}"
    directory = get_command_runs_dir(workspace, runbook_day_id)
    return {
        "json": directory / f"{base_name}.json",
        "txt": directory / f"{base_name}.txt",
        "log": directory / f"{base_name}.log",
    }


def get_stage_summary_paths(
    workspace: Path,
    runbook_day_id: str,
    stage_id: str,
    timestamp: str | None = None,
) -> dict[str, Path]:
    timestamp = timestamp or _filename_timestamp()
    stage_id_safe = _safe_filename_part(stage_id)
    directory = get_stage_runs_dir(workspace, runbook_day_id)
    return {
        "json": directory / f"{timestamp}_{stage_id_safe}.json",
        "txt": directory / f"{timestamp}_{stage_id_safe}.txt",
        "log": directory / f"{timestamp}_{stage_id_safe}.log",
        "latest_json": directory / f"latest_{stage_id_safe}.json",
        "latest_txt": directory / f"latest_{stage_id_safe}.txt",
    }


def create_command_result(
    state: RunbookState,
    command: RunbookCommand,
    runner_result: str,
    message: str,
    artifact_refs: dict[str, str] | None = None,
    raw_payload: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    blockers: list[str] | None = None,
    process: dict[str, Any] | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    if runner_result not in ALLOWED_RUNNER_RESULTS:
        raise ValueError(f"runner_result is not allowed: {runner_result}")
    timestamp = _now_iso(state.timezone)
    process_data = {
        "executed": False,
        "exit_code": None,
        "duration_ms": None,
    }
    if process:
        process_data.update(process)
    return {
        "schema_version": COMMAND_RESULT_SCHEMA_VERSION,
        "runner_result": runner_result,
        "created_at": timestamp,
        "updated_at": timestamp,
        "runbook_day_id": state.runbook_day_id,
        "frozen_context": _frozen_context_dict(state),
        "stage_id": command.stage_id,
        "step_id": command.step_id,
        "command_key": command.command_key,
        "command_type": command.command_type,
        "process": process_data,
        "outputs": {
            "json_ref": None,
            "txt_ref": None,
            "log_ref": None,
            "artifact_refs": canonicalize_artifact_refs(artifact_refs or {}, workspace),
        },
        "summary": {
            "title": command.display_name,
            "message": message,
            "warnings": list(warnings or []),
            "blockers": list(blockers or []),
            "next_required_action": None,
        },
        "raw_payload": dict(raw_payload or {}),
    }


def validate_command_result(result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_fields = (
        "schema_version",
        "runner_result",
        "created_at",
        "updated_at",
        "runbook_day_id",
        "frozen_context",
        "stage_id",
        "step_id",
        "command_key",
        "command_type",
        "process",
        "outputs",
        "summary",
        "raw_payload",
    )
    for field_name in required_fields:
        if field_name not in result:
            errors.append(f"{field_name} is required")
    if result.get("schema_version") != COMMAND_RESULT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {COMMAND_RESULT_SCHEMA_VERSION}")
    if result.get("runner_result") not in ALLOWED_RUNNER_RESULTS:
        errors.append("runner_result is not allowed")
    frozen_context = result.get("frozen_context")
    if not isinstance(frozen_context, dict):
        errors.append("frozen_context must be an object")
    else:
        for field_name in ("account_id", "data_date", "trade_date"):
            if not frozen_context.get(field_name):
                errors.append(f"frozen_context.{field_name} is required")
    step_id = result.get("step_id")
    if not isinstance(step_id, int) or not 0 <= step_id <= 18:
        errors.append("step_id must be 0..18")
    if not result.get("stage_id"):
        errors.append("stage_id is required")
    if not result.get("command_key"):
        errors.append("command_key is required")
    process = result.get("process")
    if not isinstance(process, dict):
        errors.append("process must be an object")
    else:
        if not isinstance(process.get("executed"), bool):
            errors.append("process.executed must be boolean")
        if process.get("exit_code") is not None and not isinstance(process.get("exit_code"), int):
            errors.append("process.exit_code must be null or integer")
        if process.get("duration_ms") is not None and not isinstance(process.get("duration_ms"), int):
            errors.append("process.duration_ms must be null or integer")
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        errors.append("outputs must be an object")
    else:
        if not isinstance(outputs.get("artifact_refs", {}), dict):
            errors.append("outputs.artifact_refs must be an object")
    summary = result.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
    else:
        if not isinstance(summary.get("warnings", []), list):
            errors.append("summary.warnings must be a list")
        if not isinstance(summary.get("blockers", []), list):
            errors.append("summary.blockers must be a list")
    if not isinstance(result.get("raw_payload", {}), dict):
        errors.append("raw_payload must be an object")
    return errors


def format_command_result_text(result: dict[str, Any]) -> str:
    context = result.get("frozen_context", {})
    summary = result.get("summary", {})
    warnings = summary.get("warnings") if isinstance(summary.get("warnings"), list) else []
    blockers = summary.get("blockers") if isinstance(summary.get("blockers"), list) else []
    next_action = summary.get("next_required_action") or "none"
    return "\n".join(
        [
            f"[{result.get('runner_result')}] Step {result.get('step_id')} {result.get('command_key')}",
            f"Stage: {result.get('stage_id')}",
            f"Account: {context.get('account_id')}",
            f"Data date: {context.get('data_date')}",
            f"Trade date: {context.get('trade_date')}",
            f"Message: {summary.get('message') or ''}",
            f"Warnings: {len(warnings)}",
            f"Blockers: {len(blockers)}",
            f"Next action: {next_action}",
        ]
    )


def write_command_result(
    workspace: Path,
    state: RunbookState,
    command: RunbookCommand,
    result: dict[str, Any],
) -> tuple[Path, Path]:
    paths = get_command_result_paths(workspace, state.runbook_day_id, command.step_id, command.command_key)
    paths["json"].parent.mkdir(parents=True, exist_ok=True)
    result = dict(result)
    outputs = dict(result.get("outputs", {}))
    outputs["json_ref"] = _path_ref(paths["json"], workspace)
    outputs["txt_ref"] = _path_ref(paths["txt"], workspace)
    outputs["log_ref"] = _path_ref(paths["log"], workspace)
    result["outputs"] = outputs
    result["updated_at"] = _now_iso(state.timezone)
    errors = validate_command_result(result)
    if errors:
        raise ValueError("; ".join(errors))
    paths["json"].write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["txt"].write_text(format_command_result_text(result) + "\n", encoding="utf-8")
    return paths["json"], paths["txt"]


def create_stage_summary(
    state: RunbookState,
    stage_id: str,
    command_results: list[dict[str, Any]],
    next_required_action: str | None = None,
    next_stage: str | None = None,
    next_poll_time: str | None = None,
) -> dict[str, Any]:
    timestamp = _now_iso(state.timezone)
    runner_result = _stage_runner_result(command_results)
    counts = _result_counts(command_results)
    warnings: list[str] = []
    blockers: list[str] = []
    artifact_refs: dict[str, str] = {}
    steps: list[dict[str, Any]] = []
    for result in command_results:
        result_summary = result.get("summary", {})
        warnings.extend(result_summary.get("warnings", []) if isinstance(result_summary, dict) else [])
        blockers.extend(result_summary.get("blockers", []) if isinstance(result_summary, dict) else [])
        outputs = result.get("outputs", {})
        if isinstance(outputs, dict) and isinstance(outputs.get("artifact_refs"), dict):
            artifact_refs.update(outputs["artifact_refs"])
        steps.append(
            {
                "step_id": result.get("step_id"),
                "command_key": result.get("command_key"),
                "runner_result": result.get("runner_result"),
                "result_json_ref": outputs.get("json_ref") if isinstance(outputs, dict) else None,
            }
        )
    return {
        "schema_version": STAGE_SUMMARY_SCHEMA_VERSION,
        "runner_result": runner_result,
        "created_at": timestamp,
        "updated_at": timestamp,
        "runbook_day_id": state.runbook_day_id,
        "frozen_context": _frozen_context_dict(state),
        "stage_id": stage_id,
        "stage_status": runner_result,
        "steps": steps,
        "counts": counts,
        "summary": {
            "title": f"Stage {stage_id} summary",
            "message": f"Stage {stage_id} result: {runner_result}",
            "warnings": warnings,
            "blockers": blockers,
            "next_required_action": next_required_action,
            "next_stage": next_stage,
            "next_poll_time": next_poll_time,
        },
        "artifact_refs": artifact_refs,
        "raw_payload": {},
    }


def validate_stage_summary(summary: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_fields = (
        "schema_version",
        "runner_result",
        "created_at",
        "updated_at",
        "runbook_day_id",
        "frozen_context",
        "stage_id",
        "stage_status",
        "steps",
        "counts",
        "summary",
        "artifact_refs",
        "raw_payload",
    )
    for field_name in required_fields:
        if field_name not in summary:
            errors.append(f"{field_name} is required")
    if summary.get("schema_version") != STAGE_SUMMARY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {STAGE_SUMMARY_SCHEMA_VERSION}")
    if summary.get("runner_result") not in ALLOWED_RUNNER_RESULTS:
        errors.append("runner_result is not allowed")
    if summary.get("stage_status") not in ALLOWED_RUNNER_RESULTS:
        errors.append("stage_status is not allowed")
    frozen_context = summary.get("frozen_context")
    if not isinstance(frozen_context, dict):
        errors.append("frozen_context must be an object")
    else:
        for field_name in ("account_id", "data_date", "trade_date"):
            if not frozen_context.get(field_name):
                errors.append(f"frozen_context.{field_name} is required")
    if not isinstance(summary.get("steps"), list):
        errors.append("steps must be a list")
    if not isinstance(summary.get("counts"), dict):
        errors.append("counts must be an object")
    if not isinstance(summary.get("summary"), dict):
        errors.append("summary must be an object")
    if not isinstance(summary.get("artifact_refs", {}), dict):
        errors.append("artifact_refs must be an object")
    if not isinstance(summary.get("raw_payload", {}), dict):
        errors.append("raw_payload must be an object")
    return errors


def format_stage_summary_text(summary: dict[str, Any]) -> str:
    context = summary.get("frozen_context", {})
    counts = summary.get("counts", {})
    summary_text = summary.get("summary", {})
    next_action = summary_text.get("next_required_action") or "none"
    return "\n".join(
        [
            f"[{summary.get('runner_result')}] Stage {summary.get('stage_id')} summary",
            f"Account: {context.get('account_id')}",
            f"Data date: {context.get('data_date')}",
            f"Trade date: {context.get('trade_date')}",
            (
                "Steps: "
                f"{counts.get('total', 0)} total / "
                f"{counts.get('pass', 0)} pass / "
                f"{counts.get('warning', 0)} warning / "
                f"{counts.get('blocked', 0)} blocked / "
                f"{counts.get('failed', 0)} failed"
            ),
            f"Next action: {next_action}",
        ]
    )


def write_stage_summary(
    workspace: Path,
    state: RunbookState,
    stage_summary: dict[str, Any],
) -> tuple[Path, Path]:
    paths = get_stage_summary_paths(workspace, state.runbook_day_id, str(stage_summary.get("stage_id")))
    paths["json"].parent.mkdir(parents=True, exist_ok=True)
    stage_summary = dict(stage_summary)
    stage_summary["updated_at"] = _now_iso(state.timezone)
    errors = validate_stage_summary(stage_summary)
    if errors:
        raise ValueError("; ".join(errors))
    json_text = json.dumps(stage_summary, ensure_ascii=False, indent=2) + "\n"
    txt_text = format_stage_summary_text(stage_summary) + "\n"
    paths["json"].write_text(json_text, encoding="utf-8")
    paths["txt"].write_text(txt_text, encoding="utf-8")
    paths["latest_json"].write_text(json_text, encoding="utf-8")
    paths["latest_txt"].write_text(txt_text, encoding="utf-8")
    return paths["json"], paths["txt"]


def _path_ref(path: Path, workspace: Path) -> str:
    return path.resolve().relative_to(workspace.resolve()).as_posix()


def _stage_runner_result(command_results: list[dict[str, Any]]) -> str:
    results = {result.get("runner_result") for result in command_results}
    if not results:
        return "SKIPPED"
    for candidate in RESULT_PRIORITY:
        if candidate in results:
            return candidate
    return "PASS"


def _result_counts(command_results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {
        "total": len(command_results),
        "pass": 0,
        "warning": 0,
        "wait": 0,
        "blocked": 0,
        "failed": 0,
        "skipped": 0,
    }
    for result in command_results:
        runner_result = result.get("runner_result")
        if runner_result == "PASS":
            counts["pass"] += 1
        elif runner_result == "WARNING":
            counts["warning"] += 1
        elif runner_result == "WAIT":
            counts["wait"] += 1
        elif runner_result == "BLOCKED":
            counts["blocked"] += 1
        elif runner_result == "FAILED":
            counts["failed"] += 1
        elif runner_result == "SKIPPED":
            counts["skipped"] += 1
    return counts
