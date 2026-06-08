from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from core.notion_client import NotionAPIError, NotionClient
from core.notion_account_keys import build_daily_plan_external_key
from core.notion_mapping import (
    NotionMappingError,
    get_mapping_section,
    load_notion_property_mapping,
    resolve_notion_property_name,
)
from core.notion_settings import (
    NotionSettings,
    NotionSettingsError,
    get_notion_data_source_id,
    get_notion_token,
    load_notion_settings,
)


PASS = "PASS"
WARNING = "WARNING"
BLOCKED = "BLOCKED"
UNKNOWN = "UNKNOWN"
SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class NotionReadContext:
    account_id: str
    data_date: str
    trade_date: str
    timeout_seconds: int = 30


def build_notion_live_read_status(
    *,
    account_id: str,
    data_date: str,
    trade_date: str,
    timeout_seconds: int = 30,
    client: Any | None = None,
    settings: NotionSettings | None = None,
    mapping_root: dict[str, dict[str, str]] | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    ctx = NotionReadContext(
        account_id=account_id,
        data_date=data_date,
        trade_date=trade_date,
        timeout_seconds=timeout_seconds,
    )
    try:
        resolved_settings = settings or load_notion_settings(allow_missing=True)
        if not resolved_settings.enabled:
            missing_errors = _env_only_requirement_errors(resolved_settings, env=env)
            if missing_errors:
                return _blocked_report(ctx, "; ".join(missing_errors))
        resolved_mapping = mapping_root or load_notion_property_mapping()
        resolved_client = client or NotionClient(
            get_notion_token(resolved_settings, env=env),
            timeout=timeout_seconds,
        )
        stages = {
            "DAILY_PLAN_NOTION_EXPORT": _read_stage(
                ctx,
                lambda: _read_daily_plan(
                    resolved_client,
                    resolved_settings,
                    resolved_mapping,
                    ctx,
                    env=env,
                ),
            ),
            "MANUAL_EXECUTION_TEMPLATE": _read_stage(
                ctx,
                lambda: _read_manual_executions_template(
                    resolved_client,
                    resolved_settings,
                    resolved_mapping,
                    ctx,
                    env=env,
                ),
            ),
            "MANUAL_EXECUTION_PREVIEW": _read_stage(
                ctx,
                lambda: _read_manual_executions_preview(
                    resolved_client,
                    resolved_settings,
                    resolved_mapping,
                    ctx,
                    env=env,
                ),
            ),
            "MANUAL_EXECUTION_STATUS_SYNC": _read_stage(
                ctx,
                lambda: _read_manual_executions_status_sync(
                    resolved_client,
                    resolved_settings,
                    resolved_mapping,
                    ctx,
                    env=env,
                ),
            ),
            "MANUAL_REVIEW_TEMPLATE": _read_stage(
                ctx,
                lambda: _read_manual_reviews_template(
                    resolved_client,
                    resolved_settings,
                    resolved_mapping,
                    ctx,
                    env=env,
                ),
            ),
            "MANUAL_REVIEW_PREVIEW": _read_stage(
                ctx,
                lambda: _read_manual_reviews_preview(
                    resolved_client,
                    resolved_settings,
                    resolved_mapping,
                    ctx,
                    env=env,
                ),
            ),
            "MANUAL_REVIEW_STATUS_SYNC": _read_stage(
                ctx,
                lambda: _read_manual_reviews_status_sync(
                    resolved_client,
                    resolved_settings,
                    resolved_mapping,
                    ctx,
                    env=env,
                ),
            ),
        }
        errors = [error for stage in stages.values() for error in stage["errors"]]
        warnings = [warning for stage in stages.values() for warning in stage["warnings"]]
        overall = _overall_status(stages.values(), errors=errors, warnings=warnings)
        return {
            "enabled": True,
            "called": True,
            "status": overall,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "stage_status_counts": dict(Counter(stage["status"] for stage in stages.values())),
                "total_row_count": sum(int(stage["row_count"]) for stage in stages.values()),
            },
            "stages": stages,
        }
    except (NotionSettingsError, NotionMappingError) as exc:
        return _blocked_report(ctx, str(exc))
    except Exception as exc:
        return {
            "enabled": True,
            "called": True,
            "status": UNKNOWN,
            "errors": [f"Unexpected Notion live read error: {exc}"],
            "warnings": [],
            "summary": {"stage_status_counts": {}, "total_row_count": 0},
            "stages": {},
        }


def _read_stage(ctx: NotionReadContext, reader: Any) -> dict[str, Any]:
    try:
        return reader()
    except NotionAPIError as exc:
        return {
            "status": WARNING,
            "row_count": 0,
            "status_counts": {},
            "errors": [],
            "warnings": [str(exc)],
            "details": {
                "account_id": ctx.account_id,
                "trade_date": ctx.trade_date,
            },
        }

def skipped_notion_live_read_status() -> dict[str, Any]:
    return {
        "enabled": False,
        "called": False,
        "status": SKIPPED,
        "errors": [],
        "warnings": [],
        "summary": {"stage_status_counts": {}, "total_row_count": 0},
        "stages": {},
    }


def _blocked_report(ctx: NotionReadContext, error: str) -> dict[str, Any]:
    return {
        "enabled": True,
        "called": True,
        "status": BLOCKED,
        "errors": [error],
        "warnings": [],
        "summary": {
            "account_id": ctx.account_id,
            "trade_date": ctx.trade_date,
            "stage_status_counts": {},
            "total_row_count": 0,
        },
        "stages": {},
    }


def _env_only_requirement_errors(settings: NotionSettings, *, env: dict[str, str] | None) -> list[str]:
    errors: list[str] = []
    try:
        get_notion_token(settings, env=env)
    except NotionSettingsError as exc:
        errors.append(str(exc))

    required_sources = {
        "daily_plans": "NOTION_DAILY_PLANS_DATA_SOURCE_ID",
        "manual_executions": "NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID",
        "manual_reviews": "NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID",
    }
    for key, env_override in required_sources.items():
        try:
            get_notion_data_source_id(settings, key, env=env, env_override=env_override)
        except NotionSettingsError:
            errors.append(f"Missing required Notion env override: {env_override}.")
    return errors


def _read_daily_plan(
    client: Any,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    ctx: NotionReadContext,
    *,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    mapping = get_mapping_section(mapping_root, "daily_plans")
    pages = client.query_by_external_key(
        _data_source_id(settings, "daily_plans", "NOTION_DAILY_PLANS_DATA_SOURCE_ID", env),
        build_daily_plan_external_key(ctx.account_id, ctx.trade_date),
        resolve_notion_property_name(mapping, "external_key"),
    )
    return _stage_from_pages(
        pages,
        mapping=mapping,
        date_key="plan_date",
        expected_date=ctx.trade_date,
        expected_account_id=ctx.account_id,
        status_keys=("sync_status",),
        pass_when_rows_exist=True,
    )


def _read_manual_executions_template(
    client: Any,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    ctx: NotionReadContext,
    *,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    mapping = get_mapping_section(mapping_root, "manual_executions")
    pages = _query_date_account(
        client,
        _data_source_id(settings, "manual_executions", "NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID", env),
        mapping=mapping,
        date_key="execution_date",
        date_value=ctx.trade_date,
        account_id=ctx.account_id,
    )
    return _stage_from_pages(
        pages,
        mapping=mapping,
        date_key="execution_date",
        expected_date=ctx.trade_date,
        expected_account_id=ctx.account_id,
        status_keys=("status", "import_status"),
        pass_when_rows_exist=True,
    )


def _read_manual_executions_preview(
    client: Any,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    ctx: NotionReadContext,
    *,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    stage = _read_manual_executions_template(client, settings, mapping_root, ctx, env=env)
    ready_rows = int(stage["status_counts"].get("READY", 0))
    missing_price = int(stage["details"].get("missing_actual_price_count", 0))
    if ready_rows > 0 and missing_price == 0:
        stage["status"] = PASS
    elif ready_rows > 0:
        stage["status"] = WARNING
        stage["warnings"].append("Manual Execution READY rows include blank Actual Price values.")
    return stage


def _read_manual_executions_status_sync(
    client: Any,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    ctx: NotionReadContext,
    *,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    mapping = get_mapping_section(mapping_root, "manual_executions")
    pages = _query_date_account(
        client,
        _data_source_id(settings, "manual_executions", "NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID", env),
        mapping=mapping,
        date_key="execution_date",
        date_value=ctx.trade_date,
        account_id=ctx.account_id,
    )
    return _sync_stage_from_pages(
        pages,
        mapping=mapping,
        date_key="execution_date",
        expected_date=ctx.trade_date,
        expected_account_id=ctx.account_id,
        status_key="import_status",
        fallback_status_key="status",
    )


def _read_manual_reviews_template(
    client: Any,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    ctx: NotionReadContext,
    *,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    mapping = get_mapping_section(mapping_root, "manual_reviews")
    pages = _query_date_account(
        client,
        _data_source_id(settings, "manual_reviews", "NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID", env),
        mapping=mapping,
        date_key="review_date",
        date_value=ctx.trade_date,
        account_id=ctx.account_id,
    )
    return _stage_from_pages(
        pages,
        mapping=mapping,
        date_key="review_date",
        expected_date=ctx.trade_date,
        expected_account_id=ctx.account_id,
        status_keys=("review_status", "import_status"),
        pass_when_rows_exist=True,
    )


def _read_manual_reviews_preview(
    client: Any,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    ctx: NotionReadContext,
    *,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    stage = _read_manual_reviews_template(client, settings, mapping_root, ctx, env=env)
    ready_count = int(stage["status_counts"].get("READY", 0))
    reviewed_count = int(stage["status_counts"].get("REVIEWED", 0))
    if ready_count > 0 or reviewed_count > 0:
        stage["status"] = PASS
    return stage


def _read_manual_reviews_status_sync(
    client: Any,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    ctx: NotionReadContext,
    *,
    env: dict[str, str] | None,
) -> dict[str, Any]:
    mapping = get_mapping_section(mapping_root, "manual_reviews")
    pages = _query_date_account(
        client,
        _data_source_id(settings, "manual_reviews", "NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID", env),
        mapping=mapping,
        date_key="review_date",
        date_value=ctx.trade_date,
        account_id=ctx.account_id,
    )
    return _sync_stage_from_pages(
        pages,
        mapping=mapping,
        date_key="review_date",
        expected_date=ctx.trade_date,
        expected_account_id=ctx.account_id,
        status_key="import_status",
        fallback_status_key="review_status",
    )


def _data_source_id(
    settings: NotionSettings,
    key: str,
    env_override: str,
    env: dict[str, str] | None,
) -> str:
    return get_notion_data_source_id(settings, key, env=env, env_override=env_override)


def _query_date_account(
    client: Any,
    data_source_id: str,
    *,
    mapping: dict[str, str],
    date_key: str,
    date_value: str,
    account_id: str,
) -> list[dict[str, Any]]:
    filter_payload = {
        "and": [
            {
                "property": resolve_notion_property_name(mapping, date_key),
                "date": {"equals": date_value},
            },
            {
                "property": resolve_notion_property_name(mapping, "account_id"),
                "select": {"equals": account_id},
            },
        ]
    }
    return client.query_data_source(data_source_id, filter_payload=filter_payload)


def _stage_from_pages(
    pages: list[dict[str, Any]],
    *,
    mapping: dict[str, str],
    date_key: str,
    expected_date: str,
    expected_account_id: str,
    status_keys: tuple[str, ...],
    pass_when_rows_exist: bool,
) -> dict[str, Any]:
    row_count = len(pages)
    errors = _mismatch_errors(
        pages,
        mapping=mapping,
        date_key=date_key,
        expected_date=expected_date,
        expected_account_id=expected_account_id,
    )
    status_counts = _status_counts(pages, mapping=mapping, status_keys=status_keys)
    missing_actual_price_count = _missing_number_count(pages, mapping.get("actual_price"))
    if errors:
        status = BLOCKED
    elif row_count > 0 and pass_when_rows_exist:
        status = PASS
    elif row_count == 0:
        status = UNKNOWN
    else:
        status = WARNING
    return {
        "status": status,
        "row_count": row_count,
        "status_counts": status_counts,
        "errors": errors,
        "warnings": [],
        "details": {
            "missing_actual_price_count": missing_actual_price_count,
        },
    }


def _sync_stage_from_pages(
    pages: list[dict[str, Any]],
    *,
    mapping: dict[str, str],
    date_key: str,
    expected_date: str,
    expected_account_id: str,
    status_key: str,
    fallback_status_key: str,
) -> dict[str, Any]:
    stage = _stage_from_pages(
        pages,
        mapping=mapping,
        date_key=date_key,
        expected_date=expected_date,
        expected_account_id=expected_account_id,
        status_keys=(status_key, fallback_status_key),
        pass_when_rows_exist=False,
    )
    synced_count = sum(
        count
        for status, count in stage["status_counts"].items()
        if status in {"COMMITTED", "SYNCED", "IMPORTED"}
    )
    if stage["errors"]:
        stage["status"] = BLOCKED
    elif int(stage["row_count"]) == 0:
        stage["status"] = UNKNOWN
    elif synced_count == int(stage["row_count"]):
        stage["status"] = PASS
    elif synced_count > 0:
        stage["status"] = WARNING
        stage["warnings"].append("Some Notion rows are synced/committed, but not all rows.")
    else:
        stage["status"] = WARNING
        stage["warnings"].append("Notion rows exist, but no row has COMMITTED/SYNCED/IMPORTED status.")
    return stage


def _mismatch_errors(
    pages: list[dict[str, Any]],
    *,
    mapping: dict[str, str],
    date_key: str,
    expected_date: str,
    expected_account_id: str,
) -> list[str]:
    errors: list[str] = []
    account_property = resolve_notion_property_name(mapping, "account_id")
    date_property = resolve_notion_property_name(mapping, date_key)
    for page in pages:
        properties = page.get("properties") or {}
        account_id = _extract_select(properties, account_property)
        date_value = _extract_date(properties, date_property)
        if account_id and account_id != expected_account_id:
            errors.append(f"Notion account_id mismatch: {account_id} != {expected_account_id}.")
        if date_value and date_value != expected_date:
            errors.append(f"Notion {date_key} mismatch: {date_value} != {expected_date}.")
    return errors


def _status_counts(
    pages: list[dict[str, Any]],
    *,
    mapping: dict[str, str],
    status_keys: tuple[str, ...],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for page in pages:
        properties = page.get("properties") or {}
        for key in status_keys:
            property_name = mapping.get(key)
            if not property_name:
                continue
            value = _extract_select(properties, property_name)
            if value:
                counts[value.upper()] += 1
    return dict(counts)


def _missing_number_count(pages: list[dict[str, Any]], property_name: str | None) -> int:
    if not property_name:
        return 0
    count = 0
    for page in pages:
        value = ((page.get("properties") or {}).get(property_name) or {}).get("number")
        if value is None:
            count += 1
    return count


def _extract_select(properties: dict[str, Any], property_name: str) -> str:
    payload = properties.get(property_name) or {}
    if payload.get("type") == "select":
        return str((payload.get("select") or {}).get("name") or "").strip()
    if payload.get("select"):
        return str((payload.get("select") or {}).get("name") or "").strip()
    return ""


def _extract_date(properties: dict[str, Any], property_name: str) -> str:
    payload = properties.get(property_name) or {}
    if payload.get("type") == "date":
        return str((payload.get("date") or {}).get("start") or "").strip()
    if payload.get("date"):
        return str((payload.get("date") or {}).get("start") or "").strip()
    return ""


def _overall_status(
    stages: Any,
    *,
    errors: list[str],
    warnings: list[str],
) -> str:
    if errors:
        return BLOCKED
    statuses = [stage["status"] for stage in stages]
    if any(status == BLOCKED for status in statuses):
        return BLOCKED
    if warnings or any(status == WARNING for status in statuses):
        return WARNING
    if any(status == UNKNOWN for status in statuses):
        return UNKNOWN
    return PASS
