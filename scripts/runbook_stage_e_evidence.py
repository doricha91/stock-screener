from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import runbook_result
from scripts import runbook_no_action
from scripts.runbook_state import RunbookState


FINAL_STATUS_SCHEMA_VERSION = "mfu_oper9_daily_ops_status.v1"
FINAL_STATUS_WORKFLOW_COMPLETE = "REVIEW_DONE"
FINAL_STATUS_COMPLETION_STANDARD = "STANDARD"
FINAL_STATUS_COMPLETION_NO_ACTION = "NO_ACTION"
FINAL_STATUS_REQUIRED_FIELDS = (
    "schema_version",
    "account_id",
    "data_date",
    "trade_date",
    "overall_status",
    "workflow_status",
    "completion_mode",
    "completion_proof",
    "read_only",
    "write_executed",
    "operation_write_executed",
    "notion_api_called",
    "notion_live_read_enabled",
    "notion_live_read_called",
    "commit_append_executed",
    "blockers",
    "warnings",
    "next_command",
    "next_action",
    "summary",
    "stage_counts",
    "stages",
    "operator_summary",
)


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


def validate_final_status_payload(
    payload: dict[str, Any],
    state: RunbookState,
    workspace: Path | None = None,
) -> list[str]:
    blockers: list[str] = []
    for field in FINAL_STATUS_REQUIRED_FIELDS:
        if field not in payload:
            blockers.append(f"final_status {field} is required")

    expected_strings = {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    for field, expected in expected_strings.items():
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip() or value != expected:
            blockers.append(f"final_status {field} must exactly match frozen context")

    if payload.get("schema_version") != FINAL_STATUS_SCHEMA_VERSION:
        blockers.append(f"final_status schema_version must be {FINAL_STATUS_SCHEMA_VERSION}")
    if payload.get("overall_status") != "PASS":
        blockers.append("final_status overall_status must be PASS")
    if "runner_result" in payload and payload.get("runner_result") != "PASS":
        blockers.append("final_status runner_result contradicts overall_status")

    completion_mode = payload.get("completion_mode")
    completion_proof = payload.get("completion_proof")
    if completion_mode == FINAL_STATUS_COMPLETION_STANDARD:
        if payload.get("workflow_status") != FINAL_STATUS_WORKFLOW_COMPLETE:
            blockers.append(f"final_status workflow_status must be {FINAL_STATUS_WORKFLOW_COMPLETE}")
        if completion_proof is not None:
            blockers.append("final_status standard completion_proof must be null")
    elif completion_mode == FINAL_STATUS_COMPLETION_NO_ACTION:
        if not isinstance(payload.get("workflow_status"), str) or not payload.get("workflow_status"):
            blockers.append("final_status no-action workflow_status must be a non-empty string")
        if not isinstance(completion_proof, dict):
            blockers.append("final_status no-action completion_proof must be an object")
        elif workspace is None:
            blockers.append("final_status no-action workspace is required")
        else:
            try:
                expected_proof = runbook_no_action.build_no_action_completion_context(workspace, state)
            except (OSError, ValueError) as exc:
                reason = getattr(exc, "reason", type(exc).__name__)
                blockers.append(f"final_status no-action proof invalid:{reason}")
            else:
                if completion_proof != expected_proof:
                    blockers.append("final_status no-action completion_proof mismatch")
    else:
        blockers.append("final_status completion_mode is invalid")

    for field in ("blockers", "warnings"):
        value = payload.get(field)
        if not isinstance(value, list):
            blockers.append(f"final_status {field} must be a list")
        elif value:
            blockers.append(f"final_status {field} must be empty")

    expected_flags = {
        "read_only": True,
        "write_executed": False,
        "operation_write_executed": False,
        "commit_append_executed": False,
        "notion_api_called": False,
        "notion_live_read_enabled": False,
        "notion_live_read_called": False,
    }
    for field, expected in expected_flags.items():
        value = payload.get(field)
        if not isinstance(value, bool) or value is not expected:
            blockers.append(f"final_status {field} must be {str(expected).lower()} boolean")

    expected_structures = {
        "summary": dict,
        "stage_counts": dict,
        "stages": list,
        "operator_summary": dict,
    }
    for field, expected_type in expected_structures.items():
        if not isinstance(payload.get(field), expected_type):
            blockers.append(f"final_status {field} must be {expected_type.__name__}")
    summary = payload.get("summary")
    if isinstance(summary, dict):
        if summary.get("terminal") is not True or not isinstance(summary.get("terminal"), bool):
            blockers.append("final_status summary.terminal must be true boolean")
        if summary.get("needs_attention") is not False or not isinstance(summary.get("needs_attention"), bool):
            blockers.append("final_status summary.needs_attention must be false boolean")
    if payload.get("next_command") is not None:
        blockers.append("final_status next_command must be null")
    if payload.get("next_action") is not None:
        blockers.append("final_status next_action must be null")
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
        blockers.extend(
            f"final_status_report_json:payload:{item}"
            for item in validate_final_status_payload(raw_payload, state, workspace)
        )
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
