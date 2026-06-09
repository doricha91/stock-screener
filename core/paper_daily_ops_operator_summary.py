from __future__ import annotations

from typing import Any

ACTION_NONE = "NONE"
ACTION_RUN_NEXT_COMMAND = "RUN_NEXT_COMMAND"
ACTION_CHECK_NOTION = "CHECK_NOTION"
ACTION_RUN_PREVIEW = "RUN_PREVIEW"
ACTION_RUN_COMMIT = "RUN_COMMIT"
ACTION_RUN_SYNC = "RUN_SYNC"
ACTION_RESOLVE_CONFLICT = "RESOLVE_CONFLICT"
ACTION_RESOLVE_BLOCKERS = "RESOLVE_BLOCKERS"
ACTION_WAIT_FOR_INPUT = "WAIT_FOR_INPUT"

SUMMARY_ACTION_MAP = {
    "NONE": ACTION_NONE,
    "RUN_NEXT_COMMAND": ACTION_RUN_NEXT_COMMAND,
    "CHECK_NOTION": ACTION_CHECK_NOTION,
    "WAIT_FOR_INPUT": ACTION_WAIT_FOR_INPUT,
    "REVIEW_WARNINGS": ACTION_CHECK_NOTION,
    "RESOLVE_BLOCKERS": ACTION_RESOLVE_BLOCKERS,
}


def build_operator_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a compact n8n/operator-friendly status summary."""

    stages = list(payload.get("stages") or [])
    stage_counts = dict(payload.get("stage_counts") or {})
    next_command = payload.get("next_command")
    next_action = payload.get("next_action") if isinstance(payload.get("next_action"), dict) else None
    reconciliation_summary = (
        payload.get("reconciliation_summary") if isinstance(payload.get("reconciliation_summary"), dict) else {}
    )
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    terminal = bool(summary.get("terminal"))
    current_stage = _select_current_stage(
        stages,
        next_command=next_command,
        terminal=terminal,
        reconciliation_summary=reconciliation_summary,
    )
    recommended_action = _recommended_operator_action(
        terminal=terminal,
        reconciliation_summary=reconciliation_summary,
        summary=summary,
        next_action=next_action,
        current_stage=current_stage,
    )
    current_step = str(current_stage.get("stage_name")) if current_stage else None
    current_step_status = str(current_stage.get("status")) if current_stage else "UNKNOWN"
    operator_message = _operator_message(
        current_stage,
        terminal=terminal,
        recommended_action=recommended_action,
        has_conflicts=bool(reconciliation_summary.get("has_conflicts")),
    )
    return {
        "title": "Paper Daily Ops",
        "account_id": payload.get("account_id"),
        "data_date": payload.get("data_date"),
        "trade_date": payload.get("trade_date"),
        "workflow_status": payload.get("workflow_status"),
        "overall_status": payload.get("overall_status"),
        "current_step": current_step,
        "current_step_status": current_step_status,
        "operator_message": operator_message,
        "recommended_operator_action": recommended_action,
        "next_command": next_command,
        "command_type": next_action.get("command_type") if next_action else None,
        "risk_level": next_action.get("risk_level") if next_action else None,
        "requires_manual_approval": bool(next_action.get("requires_manual_approval")) if next_action else False,
        "warnings": _operator_warnings(payload, stages),
        "blockers": list(payload.get("blockers") or []),
        "ready_count": int(stage_counts.get("READY") or 0),
        "blocked_count": int(stage_counts.get("BLOCKED") or 0),
        "warning_count": int(stage_counts.get("WARNING") or 0),
        "done_count": int(stage_counts.get("DONE") or 0),
        "unknown_count": int(stage_counts.get("UNKNOWN") or 0),
        "terminal": terminal,
        "notion_live_read_enabled": bool(payload.get("notion_live_read_enabled")),
        "notion_live_read_status": payload.get("notion_live_read_status"),
        "has_reconciliation_conflicts": bool(reconciliation_summary.get("has_conflicts")),
        "conflict_count": int(reconciliation_summary.get("conflict_count") or 0),
    }


def _select_current_stage(
    stages: list[dict[str, Any]],
    *,
    next_command: Any,
    terminal: bool,
    reconciliation_summary: dict[str, Any],
) -> dict[str, Any] | None:
    if terminal:
        return _stage_by_name(stages, "FINAL_STATUS") or {"stage_name": "FINAL_STATUS", "status": "DONE"}
    if str(reconciliation_summary.get("recommended_operator_action") or "") == ACTION_RESOLVE_CONFLICT:
        conflict_stage = _first_conflict_stage(stages)
        if conflict_stage:
            return conflict_stage
    if next_command:
        command_stage = _stage_for_next_command(stages, str(next_command))
        if command_stage:
            return command_stage
    wait_stage = _first_manual_input_wait_stage(stages)
    if wait_stage:
        return wait_stage
    for status in ("BLOCKED", "WARNING", "READY", "UNKNOWN"):
        stage = _first_stage_with_status(stages, status)
        if stage:
            return stage
    return None


def _recommended_operator_action(
    *,
    terminal: bool,
    reconciliation_summary: dict[str, Any],
    summary: dict[str, Any],
    next_action: dict[str, Any] | None,
    current_stage: dict[str, Any] | None,
) -> str:
    if terminal:
        return ACTION_NONE
    reconciliation_action = str(reconciliation_summary.get("recommended_operator_action") or "")
    if reconciliation_action == ACTION_RESOLVE_CONFLICT:
        return reconciliation_action
    if current_stage and _is_manual_input_wait_stage(current_stage):
        return ACTION_WAIT_FOR_INPUT
    if next_action:
        command_type = str(next_action.get("command_type") or "")
        if command_type == "READ_ONLY":
            return ACTION_RUN_NEXT_COMMAND
        if command_type == "LEDGER_WRITE":
            return ACTION_RUN_COMMIT
        if command_type in {"NOTION_WRITE", "STATUS_SYNC"}:
            return ACTION_RUN_SYNC if "sync" in str(next_action.get("command") or "").lower() else ACTION_RUN_NEXT_COMMAND
        if command_type == "UNKNOWN" and str(next_action.get("risk_level") or "") != "DANGEROUS":
            return ACTION_RUN_NEXT_COMMAND
    summary_action = str(summary.get("recommended_operator_action") or ACTION_NONE)
    return SUMMARY_ACTION_MAP.get(summary_action, ACTION_CHECK_NOTION)


def _operator_message(
    stage: dict[str, Any] | None,
    *,
    terminal: bool,
    recommended_action: str,
    has_conflicts: bool,
) -> str:
    if terminal:
        return "Daily ops loop is complete."
    if has_conflicts or recommended_action == ACTION_RESOLVE_CONFLICT:
        return "Local and Notion states conflict. Resolve the conflict before running risky commands."
    if not stage:
        return "Daily ops status is unknown. Check the detailed status JSON."
    name = str(stage.get("stage_name") or "UNKNOWN")
    status = str(stage.get("status") or "UNKNOWN")
    if name == "DATA_FRESHNESS" and status == "READY":
        return "Data freshness check is ready. Run the read-only freshness command first."
    if name == "DAILY_PLAN" and status == "READY":
        return "Daily Plan is ready to generate after data freshness passes."
    if name in {"MANUAL_EXECUTION_STATUS_SYNC", "MANUAL_REVIEW_STATUS_SYNC"} and status == "READY":
        return "Local commit exists. Notion status sync is still needed."
    if _is_manual_execution_draft_wait_stage(stage):
        return "Enter Actual Price and set Status to READY in Notion before running the execution preview."
    if _is_manual_review_pending_wait_stage(stage):
        return "Manual Review rows are pending. Enter Manual Answer and set Review Status to READY/REVIEWED in Notion before running review preview."
    if status == "BLOCKED":
        return "Daily ops is blocked. Resolve blockers before running the next command."
    if status == "WARNING":
        return "Daily ops has warnings. Review warnings before continuing."
    if status == "READY":
        return "The next daily ops step is ready."
    if stage.get("next_command"):
        return "The next daily ops step is ready."
    if status == "DONE":
        return "The current daily ops step is done."
    return "Daily ops status needs review."


def _operator_warnings(payload: dict[str, Any], stages: list[dict[str, Any]]) -> list[str]:
    warnings = list(payload.get("warnings") or [])
    for stage in stages:
        details = stage.get("notion_details") if isinstance(stage.get("notion_details"), dict) else {}
        if details.get("warning_code") == "NOTION_ACCOUNT_ID_SELECT_OPTION_MISSING":
            warning = "Notion Account ID select option may be missing for this account."
            if warning not in warnings:
                warnings.append(warning)
    return warnings


def _stage_by_name(stages: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((stage for stage in stages if stage.get("stage_name") == name), None)


def _stage_for_next_command(stages: list[dict[str, Any]], next_command: str) -> dict[str, Any] | None:
    return next((stage for stage in stages if str(stage.get("next_command") or "") == next_command), None)


def _first_conflict_stage(stages: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next(
        (
            stage
            for stage in stages
            if stage.get("reconciliation_checked")
            and stage.get("reconciliation_status") in {"BLOCKED", "WARNING"}
            and (
                stage.get("notion_errors")
                or stage.get("reconciliation_rule_id")
                or stage.get("notion_warnings")
            )
        ),
        None,
    )


def _first_manual_input_wait_stage(stages: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((stage for stage in stages if _is_manual_input_wait_stage(stage)), None)


def _is_manual_input_wait_stage(stage: dict[str, Any]) -> bool:
    return _is_manual_execution_draft_wait_stage(stage) or _is_manual_review_pending_wait_stage(stage)


def _is_manual_execution_draft_wait_stage(stage: dict[str, Any]) -> bool:
    if stage.get("stage_name") != "MANUAL_EXECUTION_TEMPLATE":
        return False
    if int(stage.get("notion_row_count") or 0) <= 0:
        return False
    counts = stage.get("notion_status_counts") or {}
    draft_count = int(counts.get("DRAFT") or counts.get("draft") or 0)
    ready_count = int(counts.get("READY") or counts.get("ready") or 0)
    missing_price = int((stage.get("notion_details") or {}).get("missing_actual_price_count") or 0)
    return draft_count > 0 and ready_count == 0 and missing_price > 0


def _is_manual_review_pending_wait_stage(stage: dict[str, Any]) -> bool:
    if stage.get("stage_name") not in {"MANUAL_REVIEW_TEMPLATE", "MANUAL_REVIEW_PREVIEW"}:
        return False
    if int(stage.get("notion_row_count") or 0) <= 0:
        return False
    counts = stage.get("notion_status_counts") or {}
    pending_count = int(counts.get("PENDING") or counts.get("pending") or 0)
    draft_count = int(counts.get("DRAFT") or counts.get("draft") or 0)
    ready_count = int(counts.get("READY") or counts.get("ready") or 0)
    reviewed_count = int(counts.get("REVIEWED") or counts.get("reviewed") or 0)
    answered_count = int(counts.get("ANSWERED") or counts.get("answered") or 0)
    return (pending_count > 0 or draft_count > 0) and ready_count == 0 and reviewed_count == 0 and answered_count == 0


def _first_stage_with_status(stages: list[dict[str, Any]], status: str) -> dict[str, Any] | None:
    return next((stage for stage in stages if stage.get("status") == status), None)
