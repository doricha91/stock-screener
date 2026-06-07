from __future__ import annotations

from typing import Any

from core.paper_status import WORKFLOW_REVIEW_DONE


DONE = "DONE"
READY = "READY"
BLOCKED = "BLOCKED"
WARNING = "WARNING"
UNKNOWN = "UNKNOWN"

NOTION_PASS = "PASS"
NOTION_BLOCKED = "BLOCKED"
NOTION_WARNING = "WARNING"
NOTION_SKIPPED = "SKIPPED"

ACTION_NONE = "NONE"
ACTION_RUN_NEXT_COMMAND = "RUN_NEXT_COMMAND"
ACTION_CHECK_NOTION = "CHECK_NOTION"
ACTION_RUN_PREVIEW = "RUN_PREVIEW"
ACTION_RUN_COMMIT = "RUN_COMMIT"
ACTION_RUN_SYNC = "RUN_SYNC"
ACTION_RESOLVE_CONFLICT = "RESOLVE_CONFLICT"

SYNCED_STATUSES = {"COMMITTED", "SYNCED", "STATUS_SYNCED", "IMPORT_SYNCED"}
READY_STATUSES = {"READY"}
EXECUTION_TEMPLATE_STATUSES = {"DRAFT", "READY", "COMMITTED", "SYNCED"}
REVIEW_TEMPLATE_STATUSES = {"PENDING", "READY", "REVIEWED", "COMMITTED", "SYNCED"}
REVIEW_READY_STATUSES = {"READY", "REVIEWED", "ANSWERED"}


def apply_reconciliation(
    stages: list[dict[str, Any]],
    *,
    workflow_status: str | None = None,
) -> dict[str, Any]:
    """Apply local/Notion reconciliation fields and final stage status updates."""

    by_name = {str(stage.get("stage_name")): stage for stage in stages}
    for stage in stages:
        _init_reconciliation_fields(stage)

    for stage in stages:
        if not stage.get("reconciliation_checked"):
            continue
        result = _reconcile_stage(stage, by_name, workflow_status=workflow_status)
        _apply_result(stage, result)

    return _summary(stages, workflow_status=workflow_status)


def _init_reconciliation_fields(stage: dict[str, Any]) -> None:
    notion_checked = bool(stage.get("notion_checked"))
    notion_status = str(stage.get("notion_status") or NOTION_SKIPPED)
    checked = notion_checked and notion_status != NOTION_SKIPPED
    stage["local_stage_status"] = str(stage.get("status") or UNKNOWN)
    stage["notion_stage_status"] = notion_status if checked else None
    stage["reconciliation_checked"] = checked
    stage["reconciliation_status"] = None
    stage["reconciliation_rule_id"] = None
    stage["reconciliation_reason"] = None


def _reconcile_stage(
    stage: dict[str, Any],
    by_name: dict[str, dict[str, Any]],
    *,
    workflow_status: str | None,
) -> dict[str, Any]:
    name = str(stage.get("stage_name") or "")
    notion_status = str(stage.get("notion_status") or NOTION_SKIPPED)
    if notion_status == NOTION_BLOCKED or stage.get("notion_errors"):
        return _result(
            BLOCKED,
            f"OPER9_6_{name}_NOTION_BLOCKED",
            "Notion read returned BLOCKED or mismatch errors; risky next command is suppressed.",
            suppress_next=True,
            conflict=True,
        )

    if name == "DAILY_PLAN_NOTION_EXPORT":
        return _daily_plan_export(stage, by_name)
    if name == "MANUAL_EXECUTION_TEMPLATE":
        return _manual_execution_template(stage, by_name)
    if name == "MANUAL_EXECUTION_PREVIEW":
        return _manual_execution_preview(stage)
    if name == "MANUAL_EXECUTION_COMMIT":
        return _manual_execution_commit(stage)
    if name == "MANUAL_EXECUTION_STATUS_SYNC":
        return _manual_execution_status_sync(stage, workflow_status=workflow_status)
    if name == "MANUAL_REVIEW_TEMPLATE":
        return _manual_review_template(stage, by_name)
    if name == "MANUAL_REVIEW_PREVIEW":
        return _manual_review_preview(stage)
    if name == "MANUAL_REVIEW_APPEND":
        return _manual_review_append(stage)
    if name == "MANUAL_REVIEW_STATUS_SYNC":
        return _manual_review_status_sync(stage, workflow_status=workflow_status)
    if name == "FINAL_STATUS":
        return _final_status(stage, workflow_status=workflow_status)
    return _generic_reconciliation(stage)


def _daily_plan_export(stage: dict[str, Any], by_name: dict[str, dict[str, Any]]) -> dict[str, Any]:
    plan_status = _local_status(by_name.get("DAILY_PLAN"))
    has_rows = _has_rows(stage)
    if plan_status == DONE and has_rows:
        return _result(DONE, "OPER9_6_DAILY_PLAN_LOCAL_AND_NOTION_PRESENT", "Local Daily Plan and Notion Daily Plan rows are both present.", suppress_next=True)
    if plan_status == DONE:
        return _result(READY, "OPER9_6_DAILY_PLAN_LOCAL_ONLY", "Local Daily Plan exists; Notion export is still needed.")
    if has_rows:
        return _result(
            WARNING,
            "OPER9_6_DAILY_PLAN_NOTION_WITHOUT_LOCAL",
            "Notion Daily Plan rows exist without a local Daily Plan source artifact.",
            suppress_next=True,
            conflict=True,
        )
    return _result(BLOCKED, "OPER9_6_DAILY_PLAN_MISSING_BOTH", "Daily Plan source artifact is missing; generate the local plan first.", suppress_next=True)


def _manual_execution_template(stage: dict[str, Any], by_name: dict[str, dict[str, Any]]) -> dict[str, Any]:
    plan_status = _local_status(by_name.get("DAILY_PLAN"))
    has_rows = _has_any_status(stage, EXECUTION_TEMPLATE_STATUSES) or _has_rows(stage)
    if plan_status != DONE and has_rows:
        return _result(
            WARNING,
            "OPER9_6_EXEC_TEMPLATE_NOTION_WITHOUT_LOCAL_PLAN",
            "Manual Execution rows exist in Notion without a local Daily Plan source artifact.",
            suppress_next=True,
            conflict=True,
        )
    if plan_status != DONE:
        return _result(BLOCKED, "OPER9_6_EXEC_TEMPLATE_LOCAL_PLAN_MISSING", "Daily Plan JSON sidecar is required before exporting Manual Execution rows.", suppress_next=True)
    if has_rows:
        return _result(DONE, "OPER9_6_EXEC_TEMPLATE_NOTION_ROWS_PRESENT", "Manual Execution rows are present in Notion.", suppress_next=True)
    return _result(READY, "OPER9_6_EXEC_TEMPLATE_LOCAL_PLAN_ONLY", "Local Daily Plan exists; Manual Execution template export is still needed.")


def _manual_execution_preview(stage: dict[str, Any]) -> dict[str, Any]:
    local = _local_status(stage)
    ready_rows = _count_status(stage, READY_STATUSES)
    missing_price = int((stage.get("notion_details") or {}).get("missing_actual_price_count") or 0)
    if local in {DONE, WARNING} and ready_rows == 0:
        return _result(
            WARNING,
            "OPER9_6_EXEC_PREVIEW_LOCAL_WITHOUT_READY_NOTION",
            "Execution preview exists, but Notion no longer has READY rows for this date.",
            suppress_next=True,
            conflict=True,
        )
    if local in {DONE, WARNING}:
        return _result(local, "OPER9_6_EXEC_PREVIEW_LOCAL_VALID", "Local execution preview is valid.", suppress_next=True, conflict=local == WARNING)
    if ready_rows > 0 and missing_price > 0:
        return _result(
            WARNING,
            "OPER9_6_EXEC_PREVIEW_READY_MISSING_PRICE",
            "Notion READY rows include blank Actual Price values.",
            conflict=True,
        )
    if ready_rows > 0:
        return _result(READY, "OPER9_6_EXEC_PREVIEW_READY_ROWS", "Notion READY rows exist and local execution preview is missing.")
    return _result(UNKNOWN, "OPER9_6_EXEC_PREVIEW_NO_READY_ROWS", "No Notion READY rows or local execution preview were found.", suppress_next=True)


def _manual_execution_commit(stage: dict[str, Any]) -> dict[str, Any]:
    local = _local_status(stage)
    if local == DONE:
        return _result(DONE, "OPER9_6_EXEC_COMMIT_LOCAL_REPORT_PRESENT", "Local execution commit report exists.", suppress_next=True)
    if local == WARNING:
        return _result(WARNING, "OPER9_6_EXEC_COMMIT_LEDGER_WITHOUT_REPORT", "Ledger or snapshot evidence exists without a matching commit report; commit is not recommended.", suppress_next=True, conflict=True)
    if _has_any_status(stage, SYNCED_STATUSES):
        return _result(
            BLOCKED,
            "OPER9_6_EXEC_COMMIT_NOTION_COMMITTED_WITHOUT_LOCAL",
            "Notion is COMMITTED/SYNCED, but the local source-of-truth commit report is missing.",
            suppress_next=True,
            conflict=True,
        )
    if local == READY:
        return _result(READY, "OPER9_6_EXEC_COMMIT_PREVIEW_VALID", "Local execution preview is valid and commit report is missing.")
    return _result(BLOCKED, "OPER9_6_EXEC_COMMIT_PREVIEW_MISSING", "Execution preview is required before commit recommendation.", suppress_next=True)


def _manual_execution_status_sync(stage: dict[str, Any], *, workflow_status: str | None) -> dict[str, Any]:
    local = _local_status(stage)
    if local == BLOCKED and _has_any_status(stage, SYNCED_STATUSES):
        return _result(
            BLOCKED,
            "OPER9_6_EXEC_SYNC_NOTION_SYNCED_WITHOUT_LOCAL_COMMIT",
            "Notion is COMMITTED/SYNCED, but the local execution commit report is missing.",
            suppress_next=True,
            conflict=True,
        )
    if local == BLOCKED:
        return _result(BLOCKED, "OPER9_6_EXEC_SYNC_LOCAL_COMMIT_MISSING", "Execution commit report is required for status sync.", suppress_next=True)
    if _has_any_status(stage, SYNCED_STATUSES):
        return _result(DONE, "OPER9_6_EXEC_SYNC_NOTION_SYNCED", "Local execution commit report exists and Notion status is COMMITTED/SYNCED.", suppress_next=True)
    if workflow_status == WORKFLOW_REVIEW_DONE:
        return _result(
            WARNING,
            "OPER9_6_EXEC_SYNC_REVIEW_DONE_NOTION_UNSYNCED",
            "Local workflow_status is REVIEW_DONE, but Notion execution status sync is not fully reflected.",
            suppress_next=True,
            conflict=True,
        )
    return _result(READY, "OPER9_6_EXEC_SYNC_LOCAL_COMMIT_UNSYNCED", "Local execution commit report exists; Notion status sync is still needed.")


def _manual_review_template(stage: dict[str, Any], by_name: dict[str, dict[str, Any]]) -> dict[str, Any]:
    review_ready = _local_status(by_name.get("DAILY_REVIEW")) == DONE or _local_status(stage) != BLOCKED
    has_rows = _has_any_status(stage, REVIEW_TEMPLATE_STATUSES) or _has_rows(stage)
    if not review_ready:
        return _result(BLOCKED, "OPER9_6_REVIEW_TEMPLATE_LOCAL_TEMPLATE_MISSING", "Local review template is required before Manual Review export.", suppress_next=True)
    if has_rows:
        return _result(DONE, "OPER9_6_REVIEW_TEMPLATE_NOTION_ROWS_PRESENT", "Manual Review rows are present in Notion.", suppress_next=True)
    return _result(READY, "OPER9_6_REVIEW_TEMPLATE_LOCAL_ONLY", "Local review template exists; Manual Review Notion export is still needed.")


def _manual_review_preview(stage: dict[str, Any]) -> dict[str, Any]:
    local = _local_status(stage)
    ready_rows = _count_status(stage, REVIEW_READY_STATUSES)
    if local in {DONE, WARNING} and ready_rows == 0:
        return _result(
            WARNING,
            "OPER9_6_REVIEW_PREVIEW_LOCAL_WITHOUT_READY_NOTION",
            "Review preview exists, but Notion has no READY/reviewed rows for this date.",
            suppress_next=True,
            conflict=True,
        )
    if local in {DONE, WARNING}:
        return _result(local, "OPER9_6_REVIEW_PREVIEW_LOCAL_VALID", "Local review preview is valid.", suppress_next=True, conflict=local == WARNING)
    if ready_rows > 0:
        return _result(READY, "OPER9_6_REVIEW_PREVIEW_READY_ROWS", "Notion review READY/reviewed rows exist and local review preview is missing.")
    return _result(UNKNOWN, "OPER9_6_REVIEW_PREVIEW_NO_READY_ROWS", "No Notion review READY/reviewed rows or local review preview were found.", suppress_next=True)


def _manual_review_append(stage: dict[str, Any]) -> dict[str, Any]:
    local = _local_status(stage)
    if local == DONE:
        return _result(DONE, "OPER9_6_REVIEW_APPEND_LOCAL_REPORT_PRESENT", "Local review commit report exists.", suppress_next=True)
    if local == WARNING:
        return _result(WARNING, "OPER9_6_REVIEW_APPEND_LOG_WITHOUT_REPORT", "Review log rows exist without a matching review commit report; append is not recommended.", suppress_next=True, conflict=True)
    if _has_any_status(stage, SYNCED_STATUSES):
        return _result(
            BLOCKED,
            "OPER9_6_REVIEW_APPEND_NOTION_COMMITTED_WITHOUT_LOCAL",
            "Notion review status is committed/synced, but the local review commit report is missing.",
            suppress_next=True,
            conflict=True,
        )
    if local == READY:
        return _result(READY, "OPER9_6_REVIEW_APPEND_PREVIEW_VALID", "Local review preview is valid and review commit report is missing.")
    return _result(BLOCKED, "OPER9_6_REVIEW_APPEND_PREVIEW_MISSING", "Review preview is required before append recommendation.", suppress_next=True)


def _manual_review_status_sync(stage: dict[str, Any], *, workflow_status: str | None) -> dict[str, Any]:
    local = _local_status(stage)
    if local == BLOCKED:
        return _result(BLOCKED, "OPER9_6_REVIEW_SYNC_LOCAL_COMMIT_MISSING", "Review commit report is required for status sync.", suppress_next=True)
    if _has_any_status(stage, SYNCED_STATUSES):
        return _result(DONE, "OPER9_6_REVIEW_SYNC_NOTION_SYNCED", "Local review commit report exists and Notion review status is committed/synced.", suppress_next=True)
    if workflow_status == WORKFLOW_REVIEW_DONE:
        return _result(
            WARNING,
            "OPER9_6_REVIEW_SYNC_REVIEW_DONE_NOTION_UNSYNCED",
            "Local workflow_status is REVIEW_DONE, but Notion review status sync is not fully reflected.",
            suppress_next=True,
            conflict=True,
        )
    return _result(READY, "OPER9_6_REVIEW_SYNC_LOCAL_COMMIT_UNSYNCED", "Local review commit report exists; Notion review status sync is still needed.")


def _final_status(stage: dict[str, Any], *, workflow_status: str | None) -> dict[str, Any]:
    if workflow_status == WORKFLOW_REVIEW_DONE and _has_unsynced_notion(stage):
        return _result(
            WARNING,
            "OPER9_6_FINAL_REVIEW_DONE_NOTION_UNSYNCED",
            "Local workflow_status is REVIEW_DONE, but Notion sync status is not fully reflected.",
            suppress_next=True,
            conflict=True,
        )
    if workflow_status == WORKFLOW_REVIEW_DONE:
        return _result(DONE, "OPER9_6_FINAL_REVIEW_DONE", "Local workflow_status is REVIEW_DONE.", suppress_next=True)
    return _generic_reconciliation(stage)


def _generic_reconciliation(stage: dict[str, Any]) -> dict[str, Any]:
    local = _local_status(stage)
    notion_status = str(stage.get("notion_status") or NOTION_SKIPPED)
    if notion_status == NOTION_PASS:
        return _result(local, f"OPER9_6_{stage.get('stage_name')}_NOTION_PASS", "Notion read passed; local source-of-truth status remains authoritative.")
    if notion_status == NOTION_WARNING:
        return _result(WARNING, f"OPER9_6_{stage.get('stage_name')}_NOTION_WARNING", "Notion read returned warnings.", conflict=True)
    return _result(local, f"OPER9_6_{stage.get('stage_name')}_LOCAL_ONLY", "No specific reconciliation rule changed the local status.")


def _apply_result(stage: dict[str, Any], result: dict[str, Any]) -> None:
    stage["reconciliation_status"] = result["status"]
    stage["reconciliation_rule_id"] = result["rule_id"]
    stage["reconciliation_reason"] = result["reason"]
    stage["_reconciliation_conflict"] = bool(result.get("conflict"))
    stage["status"] = result["status"]
    if result.get("suppress_next"):
        stage["next_command"] = None
        stage["next_action"] = None


def _summary(stages: list[dict[str, Any]], *, workflow_status: str | None) -> dict[str, Any]:
    checked = [stage for stage in stages if stage.get("reconciliation_checked")]
    conflicts = [stage for stage in checked if stage.get("_reconciliation_conflict")]
    blocking = [stage for stage in conflicts if stage.get("reconciliation_status") == BLOCKED]
    warning = [stage for stage in conflicts if stage.get("reconciliation_status") == WARNING]
    ready = [stage for stage in checked if stage.get("reconciliation_status") == READY]
    if not checked:
        action = ACTION_NONE
    elif blocking:
        action = ACTION_RESOLVE_CONFLICT
    elif warning:
        action = ACTION_RESOLVE_CONFLICT
    elif workflow_status == WORKFLOW_REVIEW_DONE:
        action = ACTION_NONE
    elif ready:
        action = _action_for_ready_stage(str(ready[0].get("stage_name") or ""))
    else:
        action = ACTION_NONE
    return {
        "checked": bool(checked),
        "has_conflicts": bool(conflicts),
        "conflict_count": len(conflicts),
        "blocking_conflict_count": len(blocking),
        "warning_conflict_count": len(warning),
        "recommended_operator_action": action,
    }


def _action_for_ready_stage(stage_name: str) -> str:
    if stage_name in {"MANUAL_EXECUTION_PREVIEW", "MANUAL_REVIEW_PREVIEW"}:
        return ACTION_RUN_PREVIEW
    if stage_name in {"MANUAL_EXECUTION_COMMIT", "MANUAL_REVIEW_APPEND"}:
        return ACTION_RUN_COMMIT
    if stage_name in {"MANUAL_EXECUTION_STATUS_SYNC", "MANUAL_REVIEW_STATUS_SYNC"}:
        return ACTION_RUN_SYNC
    if stage_name in {"DAILY_PLAN_NOTION_EXPORT", "MANUAL_EXECUTION_TEMPLATE", "MANUAL_REVIEW_TEMPLATE"}:
        return ACTION_RUN_NEXT_COMMAND
    return ACTION_CHECK_NOTION


def _result(
    status: str,
    rule_id: str,
    reason: str,
    *,
    suppress_next: bool = False,
    conflict: bool = False,
) -> dict[str, Any]:
    return {
        "status": status,
        "rule_id": rule_id,
        "reason": reason,
        "suppress_next": suppress_next,
        "conflict": conflict,
    }


def _local_status(stage: dict[str, Any] | None) -> str:
    if not stage:
        return UNKNOWN
    return str(stage.get("local_stage_status") or stage.get("status") or UNKNOWN)


def _has_rows(stage: dict[str, Any]) -> bool:
    return int(stage.get("notion_row_count") or 0) > 0


def _count_status(stage: dict[str, Any], statuses: set[str]) -> int:
    counts = stage.get("notion_status_counts") or {}
    return sum(int(counts.get(status) or counts.get(status.lower()) or 0) for status in statuses)


def _has_any_status(stage: dict[str, Any], statuses: set[str]) -> bool:
    return _count_status(stage, statuses) > 0


def _has_unsynced_notion(stage: dict[str, Any]) -> bool:
    if not stage.get("reconciliation_checked"):
        return False
    if not _has_rows(stage):
        return False
    return not _has_any_status(stage, SYNCED_STATUSES)
