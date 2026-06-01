from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.notion_account_keys import normalize_notion_account_id
from core.notion_client import NotionClient, notion_date, notion_number, notion_rich_text, notion_select, notion_title
from core.notion_mapping import get_mapping_section, resolve_notion_property_name
from core.notion_settings import NotionSettings, NotionSettingsError, get_notion_data_source_id
from core.notion_schema_validator import PASS, validate_data_source_schema
from core.paper_account_paths import build_paper_account_paths
from core.paper_status import run_paper_status


class NotionDailyOpsStatusExportError(RuntimeError):
    pass


DAILY_OPS_STATUS_SCHEMA_VERSION = "daily_ops_status.v1"
DAILY_OPS_STATUS_TARGET = "daily_ops_status"
DAILY_OPS_STATUS_ACTUAL_ALLOWED_ACCOUNT_ID = "paper_sandbox"


def build_daily_ops_status_external_key(account_id: str, status_date: str) -> str:
    resolved_account_id = normalize_notion_account_id(account_id)
    normalized_date = str(status_date).strip()
    if not normalized_date:
        raise NotionDailyOpsStatusExportError("status_date is required for Daily Ops Status external key.")
    return f"daily_ops_status:{resolved_account_id}:{normalized_date}"


def derive_daily_ops_status_blocking_reason(status: dict[str, Any]) -> str:
    workflow_status = str(status.get("workflow_status") or "").strip()
    if workflow_status == "NO_PLAN":
        return "daily plan missing"
    if workflow_status == "PLAN_READY":
        return "snapshot/current state missing"
    if workflow_status == "COMMITTED":
        return "reports/review not ready"
    if workflow_status == "REVIEW_READY":
        return "review append pending"
    if workflow_status == "REVIEW_PARTIAL":
        return "pending review rows remain"
    if workflow_status == "UNKNOWN_OR_INCOMPLETE":
        return "inspect status details"
    return ""


def build_daily_ops_status_payload(
    status: dict[str, Any],
    account_id: str,
    mapping: dict[str, str],
    *,
    dry_run: bool,
    checked_at: str | None = None,
) -> dict[str, Any]:
    resolved_account_id = normalize_notion_account_id(account_id)
    status_date = str(status.get("date") or "").strip()
    if not status_date:
        raise NotionDailyOpsStatusExportError("Daily Ops Status export requires a resolved status date.")

    checked_at_value = checked_at or datetime.now(timezone.utc).isoformat()
    external_key = build_daily_ops_status_external_key(resolved_account_id, status_date)
    source_root = (
        ((status.get("paths") or {}).get("paper_root"))
        or status.get("account_root")
        or ""
    )

    properties: dict[str, Any] = {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"{resolved_account_id} {status_date} Daily Ops Status"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(external_key),
        resolve_notion_property_name(mapping, "account_id"): notion_select(resolved_account_id),
        resolve_notion_property_name(mapping, "status_date"): notion_date(status_date),
        resolve_notion_property_name(mapping, "workflow_status"): notion_select(
            str(status.get("workflow_status") or "UNKNOWN_OR_INCOMPLETE")
        ),
        resolve_notion_property_name(mapping, "review_progress_status"): notion_select(
            str(status.get("review_progress_status") or "UNKNOWN")
        ),
        resolve_notion_property_name(mapping, "review_completion_ratio"): notion_number(
            float(status.get("review_completion_ratio") or 0.0)
        ),
        resolve_notion_property_name(mapping, "next_recommended_command"): notion_rich_text(
            str(status.get("next_recommended_command") or "")
        ),
        resolve_notion_property_name(mapping, "blocking_reason"): notion_rich_text(
            derive_daily_ops_status_blocking_reason(status)
        ),
        resolve_notion_property_name(mapping, "plan_exists"): _notion_checkbox(bool(status.get("plan_exists"))),
        resolve_notion_property_name(mapping, "current_state_exists"): _notion_checkbox(
            bool(status.get("current_state_exists"))
        ),
        resolve_notion_property_name(mapping, "account_snapshot_exists"): _notion_checkbox(
            bool(status.get("account_snapshot_exists"))
        ),
        resolve_notion_property_name(mapping, "position_snapshot_exists"): _notion_checkbox(
            bool(status.get("position_snapshot_exists"))
        ),
        resolve_notion_property_name(mapping, "execution_log_rows_for_date"): notion_number(
            int(status.get("execution_log_rows_for_date") or 0)
        ),
        resolve_notion_property_name(mapping, "reports_ready"): _notion_checkbox(bool(status.get("reports_ready"))),
        resolve_notion_property_name(mapping, "daily_review_summary_exists"): _notion_checkbox(
            bool(status.get("paper_daily_review_summary_exists"))
        ),
        resolve_notion_property_name(mapping, "performance_summary_exists"): _notion_checkbox(
            bool(status.get("paper_performance_summary_exists"))
        ),
        resolve_notion_property_name(mapping, "review_template_exists"): _notion_checkbox(
            bool(status.get("review_template_exists"))
        ),
        resolve_notion_property_name(mapping, "review_template_row_count"): notion_number(
            int(status.get("review_template_row_count") or 0)
        ),
        resolve_notion_property_name(mapping, "manual_review_log_exists"): _notion_checkbox(
            bool(status.get("manual_review_log_exists"))
        ),
        resolve_notion_property_name(mapping, "manual_review_log_row_count"): notion_number(
            int(status.get("manual_review_log_row_count") or 0)
        ),
        resolve_notion_property_name(mapping, "review_answered_row_count"): notion_number(
            int(status.get("review_answered_row_count") or 0)
        ),
        resolve_notion_property_name(mapping, "review_pending_row_count"): notion_number(
            int(status.get("review_pending_row_count") or 0)
        ),
        resolve_notion_property_name(mapping, "last_status_checked_at"): notion_date(checked_at_value),
        resolve_notion_property_name(mapping, "sync_status"): notion_select("DRY_RUN" if dry_run else "SYNCED"),
        resolve_notion_property_name(mapping, "schema_version"): notion_rich_text(
            DAILY_OPS_STATUS_SCHEMA_VERSION
        ),
        resolve_notion_property_name(mapping, "source_root"): notion_rich_text(str(source_root)),
    }

    review_validation_result = str(status.get("review_validation_result") or "").strip()
    if review_validation_result:
        properties[resolve_notion_property_name(mapping, "review_validation_result")] = notion_select(
            review_validation_result
        )

    properties[resolve_notion_property_name(mapping, "synced_at")] = notion_date(checked_at_value)

    return properties


def export_daily_ops_status_dry_run(
    *,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    account_id: str | None = None,
    date_str: str | None = None,
    paper_root: Path | None = None,
) -> dict[str, Any]:
    resolved_account_id = normalize_notion_account_id(account_id)
    account_paths = build_paper_account_paths(
        resolved_account_id,
        account_root=paper_root,
        create=False,
    )
    status = run_paper_status(date_str, account_paths=account_paths)
    mapping = get_mapping_section(mapping_root, DAILY_OPS_STATUS_TARGET)
    checked_at = datetime.now(timezone.utc).isoformat()
    properties = build_daily_ops_status_payload(
        status,
        resolved_account_id,
        mapping,
        dry_run=True,
        checked_at=checked_at,
    )
    status_date = str(status.get("date") or "").strip()
    if not status_date:
        raise NotionDailyOpsStatusExportError("Daily Ops Status dry-run could not resolve a status date.")

    try:
        data_source_id = get_notion_data_source_id(
            settings,
            DAILY_OPS_STATUS_TARGET,
            env_override="NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID",
        )
        data_source_configured = True
    except NotionSettingsError:
        data_source_id = ""
        data_source_configured = False

    return {
        "target": DAILY_OPS_STATUS_TARGET,
        "dry_run": True,
        "would_write": False,
        "account_id": resolved_account_id,
        "status_date": status_date,
        "external_key": build_daily_ops_status_external_key(resolved_account_id, status_date),
        "workflow_status": status.get("workflow_status"),
        "review_progress_status": status.get("review_progress_status"),
        "data_source_key": DAILY_OPS_STATUS_TARGET,
        "data_source_id": data_source_id,
        "data_source_configured": data_source_configured,
        "notion_properties": properties,
        "source_status": status,
    }


def export_daily_ops_status_actual(
    *,
    client: NotionClient,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    account_id: str | None = None,
    date_str: str | None = None,
    paper_root: Path | None = None,
) -> dict[str, Any]:
    resolved_account_id = normalize_notion_account_id(account_id)
    if resolved_account_id != DAILY_OPS_STATUS_ACTUAL_ALLOWED_ACCOUNT_ID:
        raise NotionDailyOpsStatusExportError(
            "Daily Ops Status actual export is limited to account_id=paper_sandbox in this stage."
        )

    data_source_id = get_notion_data_source_id(
        settings,
        DAILY_OPS_STATUS_TARGET,
        env_override="NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID",
    )
    actual_schema = client.get_data_source_schema(data_source_id)
    validation = validate_data_source_schema(
        target=DAILY_OPS_STATUS_TARGET,
        data_source_id=data_source_id,
        actual_schema=actual_schema,
        mapping_root=mapping_root,
    )
    if validation.status != PASS:
        raise NotionDailyOpsStatusExportError(
            f"Daily Ops Status schema validation must pass before actual export; got {validation.status}."
        )

    account_paths = build_paper_account_paths(
        resolved_account_id,
        account_root=paper_root,
        create=False,
    )
    status = run_paper_status(date_str, account_paths=account_paths)
    mapping = get_mapping_section(mapping_root, DAILY_OPS_STATUS_TARGET)
    synced_at = datetime.now(timezone.utc).isoformat()
    properties = build_daily_ops_status_payload(
        status,
        resolved_account_id,
        mapping,
        dry_run=False,
        checked_at=synced_at,
    )
    status_date = str(status.get("date") or "").strip()
    if not status_date:
        raise NotionDailyOpsStatusExportError("Daily Ops Status actual export could not resolve a status date.")

    external_key = build_daily_ops_status_external_key(resolved_account_id, status_date)
    external_key_property = resolve_notion_property_name(mapping, "external_key")
    upsert = client.upsert_page_by_external_key(
        data_source_id=data_source_id,
        external_key=external_key,
        external_key_property=external_key_property,
        properties=properties,
    )
    action = "update" if upsert.action == "updated" else "create"
    return {
        "target": DAILY_OPS_STATUS_TARGET,
        "dry_run": False,
        "actual_export": True,
        "would_write": True,
        "account_id": resolved_account_id,
        "status_date": status_date,
        "external_key": external_key,
        "action": action,
        "page_id": upsert.page_id,
        "workflow_status": status.get("workflow_status"),
        "review_progress_status": status.get("review_progress_status"),
        "sync_status": "SYNCED",
        "synced_at": synced_at,
        "data_source_key": DAILY_OPS_STATUS_TARGET,
        "data_source_id": data_source_id,
        "data_source_configured": True,
        "notion_properties": properties,
        "source_status": status,
    }


def _notion_checkbox(value: bool) -> dict[str, Any]:
    return {"checkbox": bool(value)}
