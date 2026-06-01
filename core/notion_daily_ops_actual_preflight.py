from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Callable

from core.notion_account_keys import normalize_notion_account_id
from core.notion_client import NotionAPIError
from core.notion_daily_ops_status_exporter import build_daily_ops_status_external_key
from core.notion_duplicate_audit import (
    CLASS_CREATE_CANDIDATE,
    CLASS_DUPLICATE_BLOCKER,
    CLASS_QUERY_ERROR,
    CLASS_SETTINGS_ERROR,
    CLASS_UPDATE_CANDIDATE,
    DuplicateAuditResult,
    NotionDuplicateAuditError,
    audit_daily_ops_status_duplicate,
    normalize_daily_ops_status_date,
)
from core.notion_schema_validator import FAIL, PASS, WARNING, validate_selected_data_sources
from core.notion_settings import (
    NotionSettings,
    NotionSettingsError,
    get_notion_data_source_id,
    get_notion_token,
)


DAILY_OPS_STATUS_PREFLIGHT_TARGET = "daily_ops_status"
PAPER_SANDBOX_ACCOUNT_ID = "paper_sandbox"
SKIPPED = "SKIPPED"

ACTION_ACTUAL_ALLOWED = "actual_allowed_only_after_explicit_user_approval"
ACTION_REVIEW_WARNINGS = "review_warnings_before_explicit_user_approval"
ACTION_STOP_FAILED = "stop_actual_preflight_failed"


def _safe_message(value: object, *, env: dict[str, str] | None = None) -> str:
    message = str(value)
    environ = env if env is not None else os.environ
    sensitive_values = [
        environ.get("NOTION_TOKEN") or "",
        environ.get("NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID") or "",
    ]
    for sensitive in sensitive_values:
        sensitive = sensitive.strip()
        if sensitive:
            message = message.replace(sensitive, "****")
    return re.sub(r"(/data_sources/)[^/\s]+", r"\1****", message)


@dataclass(frozen=True)
class PreflightCheck:
    name: str
    status: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "message": self.message}


@dataclass(frozen=True)
class DailyOpsActualPreflightResult:
    target: str
    account_id: str
    status_date: str
    external_key: str
    overall_status: str
    checks: list[PreflightCheck]
    duplicate_audit: dict[str, Any]
    schema_validation_result: str
    allowed_actual_command: str
    recommended_action: str
    write_executed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "account_id": self.account_id,
            "status_date": self.status_date,
            "external_key": self.external_key,
            "overall_status": self.overall_status,
            "checks": [check.to_dict() for check in self.checks],
            "duplicate_audit": dict(self.duplicate_audit),
            "schema_validation_result": self.schema_validation_result,
            "allowed_actual_command": self.allowed_actual_command,
            "recommended_action": self.recommended_action,
            "write_executed": False,
        }


SchemaValidator = Callable[..., list[Any]]
DuplicateAuditor = Callable[..., DuplicateAuditResult]


def _overall_status(checks: list[PreflightCheck]) -> str:
    if any(check.status == FAIL for check in checks):
        return FAIL
    if any(check.status == WARNING for check in checks):
        return WARNING
    return PASS


def _recommended_action(overall_status: str) -> str:
    if overall_status == FAIL:
        return ACTION_STOP_FAILED
    if overall_status == WARNING:
        return ACTION_REVIEW_WARNINGS
    return ACTION_ACTUAL_ALLOWED


def _safe_duplicate_payload(result: DuplicateAuditResult | None) -> dict[str, Any]:
    if result is None:
        return {}
    return result.to_dict()


def run_daily_ops_status_actual_preflight(
    *,
    client: Any,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    account_id: str,
    status_date: str,
    external_key: str | None = None,
    expected_page_id: str | None = None,
    env: dict[str, str] | None = None,
    schema_validator: SchemaValidator = validate_selected_data_sources,
    duplicate_auditor: DuplicateAuditor = audit_daily_ops_status_duplicate,
) -> DailyOpsActualPreflightResult:
    environ = env if env is not None else os.environ
    checks: list[PreflightCheck] = []
    duplicate_result: DuplicateAuditResult | None = None
    schema_status = SKIPPED

    try:
        resolved_account_id = normalize_notion_account_id(account_id)
    except Exception as exc:
        resolved_account_id = str(account_id or "")
        resolved_date = str(status_date or "")
        resolved_key = str(external_key or "")
        checks.append(PreflightCheck("account_scope_check", FAIL, f"Invalid account_id: {_safe_message(exc, env=environ)}"))
        return _build_result(resolved_account_id, resolved_date, resolved_key, checks, duplicate_result, schema_status)

    try:
        resolved_date = normalize_daily_ops_status_date(status_date)
        expected_key = build_daily_ops_status_external_key(resolved_account_id, resolved_date)
        provided_key = str(external_key or "").strip()
        resolved_key = provided_key or expected_key
        if provided_key and provided_key != expected_key:
            checks.append(
                PreflightCheck(
                    "external_key_check",
                    FAIL,
                    "External Key does not match account_id/status_date.",
                )
            )
        else:
            checks.append(PreflightCheck("external_key_check", PASS, "External Key matches account_id/status_date."))
    except Exception as exc:
        resolved_date = str(status_date or "")
        resolved_key = str(external_key or "")
        checks.append(PreflightCheck("external_key_check", FAIL, f"Invalid date or External Key: {_safe_message(exc, env=environ)}"))
        return _build_result(resolved_account_id, resolved_date, resolved_key, checks, duplicate_result, schema_status)

    if resolved_account_id != PAPER_SANDBOX_ACCOUNT_ID:
        checks.append(
            PreflightCheck(
                "account_scope_check",
                FAIL,
                "Only paper_sandbox is currently allowed for Daily Ops Status actual readiness.",
            )
        )
    else:
        checks.append(PreflightCheck("account_scope_check", PASS, "Account scope is paper_sandbox."))

    try:
        get_notion_token(settings, env=environ)
        get_notion_data_source_id(
            settings,
            DAILY_OPS_STATUS_PREFLIGHT_TARGET,
            env=environ,
            env_override="NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID",
        )
        checks.append(PreflightCheck("settings_env_check", PASS, "Token and Daily Ops Status data source are configured."))
    except NotionSettingsError as exc:
        checks.append(PreflightCheck("settings_env_check", FAIL, f"Missing Notion setting: {_safe_message(exc, env=environ)}"))
        return _build_result(resolved_account_id, resolved_date, resolved_key, checks, duplicate_result, schema_status)

    try:
        schema_results = schema_validator(
            client=client,
            settings=settings,
            mapping_root=mapping_root,
            targets=[DAILY_OPS_STATUS_PREFLIGHT_TARGET],
            env=environ,
        )
        schema_status = schema_results[0].status if schema_results else FAIL
        if schema_status == FAIL:
            checks.append(PreflightCheck("schema_validation_check", FAIL, "Daily Ops Status schema validation failed."))
        elif schema_status == WARNING:
            checks.append(PreflightCheck("schema_validation_check", WARNING, "Daily Ops Status schema validation returned warnings."))
        else:
            checks.append(PreflightCheck("schema_validation_check", PASS, "Daily Ops Status schema validation passed."))
    except (NotionAPIError, NotionSettingsError, KeyError, ValueError) as exc:
        schema_status = FAIL
        checks.append(
            PreflightCheck(
                "schema_validation_check",
                FAIL,
                f"Daily Ops Status schema validation could not complete: {_safe_message(exc, env=environ)}",
            )
        )

    try:
        duplicate_result = duplicate_auditor(
            client=client,
            settings=settings,
            mapping_root=mapping_root,
            account_id=resolved_account_id,
            status_date=resolved_date,
            external_key=resolved_key,
            expected_page_id=expected_page_id,
        )
        classification = duplicate_result.classification
        if classification in {CLASS_DUPLICATE_BLOCKER, CLASS_SETTINGS_ERROR, CLASS_QUERY_ERROR}:
            checks.append(PreflightCheck("duplicate_audit_check", FAIL, f"Duplicate audit returned {classification}."))
        elif classification in {CLASS_CREATE_CANDIDATE, CLASS_UPDATE_CANDIDATE}:
            checks.append(PreflightCheck("duplicate_audit_check", PASS, f"Duplicate audit returned {classification}."))
        else:
            checks.append(PreflightCheck("duplicate_audit_check", FAIL, f"Duplicate audit requires manual review: {classification}."))
    except (NotionDuplicateAuditError, NotionSettingsError, NotionAPIError) as exc:
        checks.append(PreflightCheck("duplicate_audit_check", FAIL, f"Duplicate audit failed: {_safe_message(exc, env=environ)}"))

    if expected_page_id:
        checks.append(PreflightCheck("command_gate_check", PASS, "Expected page_id was provided for rerun consistency."))
    else:
        checks.append(PreflightCheck("command_gate_check", WARNING, "expected_page_id was not provided; operator confirmation is still required."))

    return _build_result(resolved_account_id, resolved_date, resolved_key, checks, duplicate_result, schema_status)


def _build_result(
    account_id: str,
    status_date: str,
    external_key: str,
    checks: list[PreflightCheck],
    duplicate_result: DuplicateAuditResult | None,
    schema_status: str,
) -> DailyOpsActualPreflightResult:
    overall = _overall_status(checks)
    return DailyOpsActualPreflightResult(
        target=DAILY_OPS_STATUS_PREFLIGHT_TARGET,
        account_id=account_id,
        status_date=status_date,
        external_key=external_key,
        overall_status=overall,
        checks=checks,
        duplicate_audit=_safe_duplicate_payload(duplicate_result),
        schema_validation_result=schema_status,
        allowed_actual_command=(
            "python scripts\\export_paper_to_notion.py --daily-ops-status "
            "--account-id paper_sandbox --confirm-actual --json"
        ),
        recommended_action=_recommended_action(overall),
        write_executed=False,
    )
