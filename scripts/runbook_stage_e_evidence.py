from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import runbook_result
from scripts.runbook_state import RunbookState


FINAL_STATUS_SUCCESS_VALUES = {"PASS", "OK", "READY", "DONE"}


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def load_workspace_json_artifact(
    workspace: Path,
    artifact_ref: object,
) -> tuple[dict[str, Any] | None, Path | None, str | None]:
    cleaned = str(artifact_ref or "").strip()
    if not cleaned:
        return None, None, "artifact_ref_missing"
    candidate = Path(cleaned)
    path = candidate.resolve(strict=False) if candidate.is_absolute() else (workspace / candidate).resolve(strict=False)
    if not _path_is_within(path, workspace):
        return None, None, "artifact_ref_outside_workspace"
    if not path.is_file():
        return None, path, "artifact_file_missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, path, "artifact_json_invalid"
    if not isinstance(payload, dict):
        return None, path, "artifact_json_must_be_object"
    return payload, path, None


def _strict_zero_count(payload: dict[str, Any], field: str, label: str) -> list[str]:
    if field not in payload:
        return [f"{label} {field}_missing"]
    value = payload[field]
    if isinstance(value, bool) or not isinstance(value, int):
        return [f"{label} {field}_type_invalid"]
    if value != 0:
        return [f"{label} {field}_not_zero"]
    return []


def validate_eod_report_common(payload: dict[str, Any], state: RunbookState) -> list[str]:
    blockers: list[str] = []
    if str(payload.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("EOD report account_id must match frozen context.")
    for field in ("date", "trade_date"):
        value = payload.get(field)
        if not isinstance(value, str) or value.strip() != state.frozen_context.trade_date:
            blockers.append(f"EOD report {field} must match trade_date.")
    blockers.extend(_strict_zero_count(payload, "failed_count", "EOD report"))
    blockers.extend(_strict_zero_count(payload, "blocked_count", "EOD report"))
    return blockers


def validate_eod_dryrun_report_payload(payload: dict[str, Any], state: RunbookState) -> list[str]:
    blockers: list[str] = []
    if payload.get("runner_result") != "PASS":
        blockers.append("EOD dry-run runner_result must be PASS.")
    if payload.get("status") != "PASS":
        blockers.append("EOD dry-run status must be PASS.")
    if payload.get("mode") != "dry_run":
        blockers.append("EOD dry-run mode must be dry_run.")
    blockers.extend(validate_eod_report_common(payload, state))
    if payload.get("commit_allowed") is not True:
        blockers.append("EOD dry-run commit_allowed must be true.")
    for field in ("would_write_current_state", "would_write_account_snapshot", "would_write_position_snapshot"):
        if payload.get(field) is not True:
            blockers.append(f"EOD dry-run {field} must be true.")
    return blockers


def validate_eod_commit_report_payload(payload: dict[str, Any], state: RunbookState) -> list[str]:
    blockers: list[str] = []
    if payload.get("runner_result") != "PASS":
        blockers.append("EOD commit runner_result must be PASS.")
    if payload.get("status") != "COMMITTED":
        blockers.append("EOD commit status must be COMMITTED.")
    if payload.get("mode") != "commit":
        blockers.append("EOD commit mode must be commit.")
    blockers.extend(validate_eod_report_common(payload, state))
    for field in ("current_state_written", "account_snapshot_written", "position_snapshot_written"):
        if payload.get(field) is not True:
            blockers.append(f"EOD commit {field} must be true.")
    if payload.get("market_valuation_status") != "success":
        blockers.append("EOD commit market_valuation_status must be success.")
    return blockers


def validate_final_status_payload(payload: dict[str, Any], state: RunbookState) -> list[str]:
    blockers: list[str] = []
    if str(payload.get("account_id") or "").strip() != state.frozen_context.account_id:
        blockers.append("final_status account_id must match frozen context")
    date_fields = ("trade_date", "date", "target_date")
    present_dates = [(field, payload[field]) for field in date_fields if field in payload]
    if not present_dates:
        blockers.append("final_status trade_date is required")
    else:
        for field, value in present_dates:
            if not isinstance(value, str) or value.strip() != state.frozen_context.trade_date:
                blockers.append(f"final_status {field} must match trade_date")
    blockers.extend(_strict_zero_count(payload, "unresolved_error_count", "final_status"))
    status_fields = ("runner_result", "overall_status", "workflow_status")
    present_statuses = [payload[field] for field in status_fields if field in payload]
    if not present_statuses:
        blockers.append("final_status success status is required")
    else:
        status = present_statuses[0]
        if not isinstance(status, str) or status.strip().upper() not in FINAL_STATUS_SUCCESS_VALUES:
            blockers.append("final_status must be PASS")
    return blockers


def validate_stored_eod_commit(
    workspace: Path,
    state: RunbookState,
) -> dict[str, Any]:
    payload, _, error = load_workspace_json_artifact(workspace, state.artifacts.get("eod_commit_report_json"))
    blockers = [f"eod_commit_report_json:{error}"] if error else validate_eod_commit_report_payload(payload, state)
    return {"valid": not blockers, "blockers": blockers}


def validate_stored_final_status(
    workspace: Path,
    state: RunbookState,
) -> dict[str, Any]:
    payload, _, error = load_workspace_json_artifact(workspace, state.artifacts.get("final_status_report_json"))
    if error:
        return {"valid": False, "blockers": [f"final_status_report_json:{error}"]}
    blockers = [f"final_status_report_json:schema:{item}" for item in runbook_result.validate_command_result(payload)]
    expected_context = {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    if payload.get("runner_result") != "PASS":
        blockers.append("final_status_report_json:runner_result_not_pass")
    if payload.get("runbook_day_id") != state.runbook_day_id:
        blockers.append("final_status_report_json:runbook_day_id_mismatch")
    if payload.get("frozen_context") != expected_context:
        blockers.append("final_status_report_json:frozen_context_mismatch")
    if payload.get("stage_id") != "E":
        blockers.append("final_status_report_json:stage_id_mismatch")
    if payload.get("step_id") != 18:
        blockers.append("final_status_report_json:step_id_mismatch")
    if payload.get("command_key") != "final_status":
        blockers.append("final_status_report_json:command_key_mismatch")
    raw_payload = payload.get("raw_payload")
    if isinstance(raw_payload, dict):
        blockers.extend(f"final_status_report_json:payload:{item}" for item in validate_final_status_payload(raw_payload, state))
    else:
        blockers.append("final_status_report_json:raw_payload_invalid")
    return {"valid": not blockers, "blockers": blockers}


def validate_stage_e_completion_evidence(
    workspace: Path,
    state: RunbookState,
) -> dict[str, Any]:
    commit = validate_stored_eod_commit(workspace, state)
    final_status = validate_stored_final_status(workspace, state)
    blockers = [*commit["blockers"], *final_status["blockers"]]
    return {"valid": not blockers, "blockers": blockers}
