from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.notion_account_keys import normalize_notion_account_id
from core.notion_daily_ops_status_exporter import build_daily_ops_status_external_key
from core.notion_mapping import get_mapping_section, resolve_notion_property_name
from core.notion_settings import NotionSettings, get_notion_data_source_id


DAILY_OPS_STATUS_AUDIT_TARGET = "daily_ops_status"

CLASS_CREATE_CANDIDATE = "create_candidate"
CLASS_UPDATE_CANDIDATE = "update_candidate"
CLASS_DUPLICATE_BLOCKER = "duplicate_blocker"
CLASS_MANUAL_REVIEW_REQUIRED = "manual_review_required"
CLASS_SETTINGS_ERROR = "settings_error"
CLASS_QUERY_ERROR = "query_error"

ACTION_SAFE_TO_CREATE = "safe_to_create_after_required_preflight"
ACTION_SAFE_TO_UPDATE = "safe_to_update_after_required_preflight"
ACTION_STOP_DUPLICATE = "stop_actual_duplicate_detected"
ACTION_STOP_MANUAL_REVIEW = "stop_actual_manual_review_required"
ACTION_STOP_SETTINGS_ERROR = "stop_actual_settings_error"
ACTION_STOP_QUERY_ERROR = "stop_actual_query_error"


class NotionDuplicateAuditError(RuntimeError):
    pass


def _mask_identifier(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 4:
        return "****"
    return f"****{text[-4:]}"


@dataclass(frozen=True)
class DuplicateAuditResult:
    target: str
    account_id: str
    status_date: str
    external_key: str
    match_count: int
    page_ids: list[str]
    classification: str
    recommended_action: str
    write_executed: bool = False
    expected_page_id: str = ""
    data_source_id: str = ""
    external_key_property: str = ""
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "account_id": self.account_id,
            "status_date": self.status_date,
            "external_key": self.external_key,
            "match_count": self.match_count,
            "page_ids": list(self.page_ids),
            "classification": self.classification,
            "recommended_action": self.recommended_action,
            "write_executed": False,
            "expected_page_id": self.expected_page_id,
            "data_source_id": _mask_identifier(self.data_source_id),
            "external_key_property": self.external_key_property,
            "error": self.error,
        }


def normalize_daily_ops_status_date(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise NotionDuplicateAuditError("--date is required when --external-key is not provided.")
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    raise NotionDuplicateAuditError("Daily Ops Status audit date must be YYYY-MM-DD or YYYYMMDD.")


def resolve_daily_ops_status_audit_key(
    *,
    account_id: str,
    status_date: str | None = None,
    external_key: str | None = None,
) -> tuple[str, str, str, bool]:
    resolved_account_id = normalize_notion_account_id(account_id)
    resolved_date = normalize_daily_ops_status_date(status_date)
    expected_key = build_daily_ops_status_external_key(resolved_account_id, resolved_date)
    provided_key = str(external_key or "").strip()
    if provided_key and provided_key != expected_key:
        return resolved_account_id, resolved_date, provided_key, False
    return resolved_account_id, resolved_date, expected_key, True


def classify_duplicate_audit_matches(
    *,
    target: str,
    account_id: str,
    status_date: str,
    external_key: str,
    page_ids: list[str],
    expected_page_id: str | None = None,
    key_matches_inputs: bool = True,
    data_source_id: str = "",
    external_key_property: str = "",
    error: str = "",
) -> DuplicateAuditResult:
    normalized_expected_page_id = str(expected_page_id or "").strip()
    match_count = len(page_ids)
    if error:
        classification = CLASS_QUERY_ERROR
        recommended_action = ACTION_STOP_QUERY_ERROR
    elif not key_matches_inputs:
        classification = CLASS_MANUAL_REVIEW_REQUIRED
        recommended_action = ACTION_STOP_MANUAL_REVIEW
    elif normalized_expected_page_id and match_count == 1 and page_ids[0] != normalized_expected_page_id:
        classification = CLASS_MANUAL_REVIEW_REQUIRED
        recommended_action = ACTION_STOP_MANUAL_REVIEW
    elif match_count == 0:
        classification = CLASS_CREATE_CANDIDATE
        recommended_action = ACTION_SAFE_TO_CREATE
    elif match_count == 1:
        classification = CLASS_UPDATE_CANDIDATE
        recommended_action = ACTION_SAFE_TO_UPDATE
    else:
        classification = CLASS_DUPLICATE_BLOCKER
        recommended_action = ACTION_STOP_DUPLICATE

    return DuplicateAuditResult(
        target=target,
        account_id=account_id,
        status_date=status_date,
        external_key=external_key,
        match_count=match_count,
        page_ids=list(page_ids),
        classification=classification,
        recommended_action=recommended_action,
        expected_page_id=normalized_expected_page_id,
        data_source_id=data_source_id,
        external_key_property=external_key_property,
        error=error,
    )


def audit_daily_ops_status_duplicate(
    *,
    client: Any,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    account_id: str,
    status_date: str | None = None,
    external_key: str | None = None,
    expected_page_id: str | None = None,
) -> DuplicateAuditResult:
    resolved_account_id, resolved_date, resolved_key, key_matches_inputs = resolve_daily_ops_status_audit_key(
        account_id=account_id,
        status_date=status_date,
        external_key=external_key,
    )
    data_source_id = get_notion_data_source_id(
        settings,
        DAILY_OPS_STATUS_AUDIT_TARGET,
        env_override="NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID",
    )
    mapping = get_mapping_section(mapping_root, DAILY_OPS_STATUS_AUDIT_TARGET)
    external_key_property = resolve_notion_property_name(mapping, "external_key")
    matches = client.query_by_external_key(
        data_source_id,
        resolved_key,
        external_key_property,
    )
    page_ids = [str(item.get("id") or "").strip() for item in matches if str(item.get("id") or "").strip()]
    return classify_duplicate_audit_matches(
        target=DAILY_OPS_STATUS_AUDIT_TARGET,
        account_id=resolved_account_id,
        status_date=resolved_date,
        external_key=resolved_key,
        page_ids=page_ids,
        expected_page_id=expected_page_id,
        key_matches_inputs=key_matches_inputs,
        data_source_id=data_source_id,
        external_key_property=external_key_property,
    )
