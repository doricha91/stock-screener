from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scripts import runbook_result
from scripts import runbook_completion_evidence
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
    "runbook_completion_evidence",
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


def load_workspace_json_artifact(
    workspace: Path,
    artifact_ref: object,
) -> tuple[dict[str, Any] | None, Path | None, str | None]:
    cleaned = str(artifact_ref or "").strip()
    if not cleaned:
        return None, None, "artifact_ref_missing"
    try:
        path = runbook_completion_evidence.resolve_workspace_ref(workspace, cleaned)
    except runbook_completion_evidence.CompletionEvidenceError as exc:
        reason_map = {
            "workspace_ref_outside_workspace": "artifact_ref_outside_workspace",
            "workspace_ref_missing": "artifact_file_missing",
            "workspace_ref_not_file": "artifact_file_missing",
        }
        return None, None, reason_map.get(exc.reason, exc.reason)
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
    account_root: Path | None = None,
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
    standard_evidence = payload.get("runbook_completion_evidence")
    completion_manifest = payload.get("completion_manifest")
    if workspace is not None or account_root is not None:
        if not isinstance(completion_manifest, dict):
            blockers.append("final_status completion_manifest must be an object")
        elif completion_manifest.get("schema_version") != runbook_completion_evidence.MANIFEST_SCHEMA_VERSION:
            blockers.append("final_status completion_manifest schema is invalid")
    if completion_mode == FINAL_STATUS_COMPLETION_STANDARD:
        if payload.get("workflow_status") != FINAL_STATUS_WORKFLOW_COMPLETE:
            blockers.append(f"final_status workflow_status must be {FINAL_STATUS_WORKFLOW_COMPLETE}")
        if completion_proof is not None:
            blockers.append("final_status standard completion_proof must be null")
        if workspace is not None and account_root is not None:
            if not isinstance(standard_evidence, dict):
                blockers.append("final_status standard runbook_completion_evidence must be an object")
            else:
                try:
                    current_standard_evidence = runbook_completion_evidence.build_standard_completion_context(
                        workspace, state
                    )
                except (OSError, ValueError) as exc:
                    blockers.append(
                        "final_status standard evidence invalid:"
                        f"{getattr(exc, 'reason', type(exc).__name__)}"
                    )
                else:
                    if standard_evidence != current_standard_evidence:
                        blockers.append("final_status standard runbook_completion_evidence mismatch")
    elif completion_mode == FINAL_STATUS_COMPLETION_NO_ACTION:
        if not isinstance(payload.get("workflow_status"), str) or not payload.get("workflow_status"):
            blockers.append("final_status no-action workflow_status must be a non-empty string")
        if not isinstance(completion_proof, dict):
            blockers.append("final_status no-action completion_proof must be an object")
        if standard_evidence is not None:
            blockers.append("final_status no-action runbook_completion_evidence must be null")
    else:
        blockers.append("final_status completion_mode is invalid")

    if (workspace is None) != (account_root is None):
        blockers.append("final_status completion source context is required")
    elif workspace is not None and account_root is not None and isinstance(completion_manifest, dict):
        source_validation = runbook_completion_evidence.validate_completion_sources(
            workspace,
            state,
            account_root,
            stored_payload=payload,
            stored_manifest=completion_manifest,
        )
        blockers.extend(f"final_status completion source invalid:{item}" for item in source_validation["blockers"])
        if completion_mode == FINAL_STATUS_COMPLETION_NO_ACTION and isinstance(completion_proof, dict):
            try:
                from scripts.runbook_no_action import build_no_action_completion_context

                expected_proof = build_no_action_completion_context(workspace, state, account_root=account_root)
            except (OSError, ValueError) as exc:
                blockers.append(f"final_status no-action proof invalid:{getattr(exc, 'reason', type(exc).__name__)}")
            else:
                if completion_proof != expected_proof:
                    blockers.append("final_status no-action completion_proof mismatch")

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
    account_root: Path,
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
    stored_manifest, _, manifest_error = load_workspace_json_artifact(
        workspace, state.artifacts.get("completion_manifest_json")
    )
    if manifest_error:
        blockers.append(f"completion_manifest_json:{manifest_error}")
    if isinstance(raw_payload, dict):
        blockers.extend(
            f"final_status_report_json:payload:{item}"
            for item in validate_final_status_payload(raw_payload, state, workspace, account_root)
        )
        source_validation = runbook_completion_evidence.validate_completion_sources(
            workspace,
            state,
            account_root,
            stored_payload=raw_payload,
            stored_manifest=stored_manifest,
        )
        blockers.extend(f"final_status_report_json:sources:{item}" for item in source_validation["blockers"])
    else:
        blockers.append("final_status_report_json:raw_payload_invalid")
    return {"valid": not blockers, "blockers": blockers}


def validate_legacy_stored_final_status(
    workspace: Path,
    state: RunbookState,
) -> dict[str, Any]:
    """Validate the historical pre-Stage-F terminal contract without rewriting it."""
    payload, final_path, error = load_workspace_json_artifact(
        workspace, state.artifacts.get("final_status_report_json")
    )
    if error:
        return {"valid": False, "blockers": [f"final_status_report_json:{error}"]}
    blockers = [f"final_status_report_json:schema:{item}" for item in runbook_result.validate_command_result(payload)]
    expected_context = {
        "account_id": state.frozen_context.account_id,
        "data_date": state.frozen_context.data_date,
        "trade_date": state.frozen_context.trade_date,
    }
    process = payload.get("process")
    summary = payload.get("summary")
    if payload.get("runner_result") != "PASS":
        blockers.append("final_status_report_json:runner_result_not_pass")
    if payload.get("runbook_day_id") != state.runbook_day_id:
        blockers.append("final_status_report_json:runbook_day_id_mismatch")
    if payload.get("frozen_context") != expected_context:
        blockers.append("final_status_report_json:frozen_context_mismatch")
    if payload.get("stage_id") != "E" or payload.get("step_id") != 18:
        blockers.append("final_status_report_json:stage_step_mismatch")
    if payload.get("command_key") != "final_status":
        blockers.append("final_status_report_json:command_key_mismatch")
    if not isinstance(process, dict) or process.get("executed") is not True or process.get("exit_code") != 0:
        blockers.append("final_status_report_json:process_not_successful")
    if not isinstance(summary, dict) or bool(summary.get("blockers")):
        blockers.append("final_status_report_json:summary_blocked")

    raw_payload = payload.get("raw_payload")
    if not isinstance(raw_payload, dict):
        blockers.append("final_status_report_json:raw_payload_invalid")
    else:
        expected_values = {
            "schema_version": FINAL_STATUS_SCHEMA_VERSION,
            **expected_context,
            "overall_status": "PASS",
            "workflow_status": FINAL_STATUS_WORKFLOW_COMPLETE,
        }
        for field, expected in expected_values.items():
            if raw_payload.get(field) != expected:
                blockers.append(f"final_status_report_json:payload:{field}_mismatch")
        expected_flags = {
            "read_only": True,
            "write_executed": False,
            "operation_write_executed": False,
            "notion_api_called": False,
            "commit_append_executed": False,
        }
        for field, expected in expected_flags.items():
            if raw_payload.get(field) is not expected or not isinstance(raw_payload.get(field), bool):
                blockers.append(f"final_status_report_json:payload:{field}_mismatch")
        live_enabled = raw_payload.get("notion_live_read_enabled")
        live_called = raw_payload.get("notion_live_read_called")
        if not isinstance(live_enabled, bool) or not isinstance(live_called, bool) or live_called != live_enabled:
            blockers.append("final_status_report_json:payload:notion_live_read_contract_invalid")
        live_errors = raw_payload.get("notion_live_read_errors")
        if live_errors is not None and (not isinstance(live_errors, list) or live_errors):
            blockers.append("final_status_report_json:payload:notion_live_read_errors_present")
        for field in ("blockers", "warnings"):
            if not isinstance(raw_payload.get(field), list) or raw_payload.get(field):
                blockers.append(f"final_status_report_json:payload:{field}_not_empty")
        terminal_summary = raw_payload.get("summary")
        if not isinstance(terminal_summary, dict) or terminal_summary.get("terminal") is not True:
            blockers.append("final_status_report_json:payload:not_terminal")
        if not isinstance(terminal_summary, dict) or terminal_summary.get("needs_attention") is not False:
            blockers.append("final_status_report_json:payload:needs_attention")
        if raw_payload.get("next_command") is not None or raw_payload.get("next_action") is not None:
            blockers.append("final_status_report_json:payload:next_action_present")

    latest_path = workspace / "stage_runs" / state.runbook_day_id / "latest_E.json"
    latest, _, latest_error = load_workspace_json_artifact(workspace, latest_path)
    if latest_error:
        blockers.append(f"latest_stage_e:{latest_error}")
    else:
        blockers.extend(f"latest_stage_e:schema:{item}" for item in runbook_result.validate_stage_summary(latest))
        if (
            latest.get("runner_result") != "PASS"
            or latest.get("stage_status") != "PASS"
            or latest.get("runbook_day_id") != state.runbook_day_id
            or latest.get("frozen_context") != expected_context
            or latest.get("stage_id") != "E"
        ):
            blockers.append("latest_stage_e:contract_mismatch")
        steps = latest.get("steps")
        matches = [
            item
            for item in steps if isinstance(item, dict)
            and item.get("step_id") == 18
            and item.get("command_key") == "final_status"
        ] if isinstance(steps, list) else []
        if len(matches) != 1 or matches[0].get("runner_result") != "PASS":
            blockers.append("latest_stage_e:final_status_step_invalid")
        else:
            try:
                summary_result_path = runbook_completion_evidence.resolve_workspace_ref(
                    workspace, matches[0].get("result_json_ref")
                )
            except runbook_completion_evidence.CompletionEvidenceError as exc:
                blockers.append(f"latest_stage_e:result_ref:{exc.reason}")
            else:
                if final_path is None or summary_result_path != final_path:
                    blockers.append("latest_stage_e:result_ref_mismatch")
    return {"valid": not blockers, "blockers": blockers}


def validate_legacy_stage_e_completion_evidence(
    workspace: Path,
    state: RunbookState,
) -> dict[str, Any]:
    commit = validate_stored_eod_commit(workspace, state)
    final_status = validate_legacy_stored_final_status(workspace, state)
    blockers = [*commit["blockers"], *final_status["blockers"]]
    return {"valid": not blockers, "blockers": blockers}


def validate_stage_e_completion_evidence(
    workspace: Path,
    state: RunbookState,
    account_root: Path,
) -> dict[str, Any]:
    commit = validate_stored_eod_commit(workspace, state)
    final_status = validate_stored_final_status(workspace, state, account_root)
    blockers = [*commit["blockers"], *final_status["blockers"]]
    return {"valid": not blockers, "blockers": blockers}
