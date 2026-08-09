from __future__ import annotations

from typing import Any

from core.notion_mapping import resolve_notion_property_name


POSITION_FOLLOW_UP_OPTION = "position_follow_up"

MANUAL_REVIEW_PROPERTY_TYPES = {
    "name": "title",
    "external_key": "rich_text",
    "account_id": "select",
    "review_date": "date",
    "symbol": "rich_text",
    "question_id": "rich_text",
    "question": "rich_text",
    "manual_answer": "rich_text",
    "review_status": "select",
    "follow_up_needed": "select",
    "review_tag": "multi_select",
    "reviewer_note": "rich_text",
    "source_template_key": "rich_text",
    "validation_status": "select",
    "validation_message": "rich_text",
    "import_status": "select",
    "imported_at": "rich_text",
    "synced_at": "rich_text",
}

MANUAL_REVIEW_OPTION_CONTRACTS = {
    "account_id": ("paper_default", "paper_pilot_202606", "paper_orch_smoke_202606"),
    "review_status": ("pending", "reviewed", "deferred", "not_applicable"),
    "follow_up_needed": ("true", "false"),
    "review_tag": (
        "exit_rule",
        "entry_rule",
        "position_sizing",
        "market_regime",
        "risk_management",
        "data_quality",
        "execution_quality",
        "signal_quality",
        "psychology",
        "other",
        POSITION_FOLLOW_UP_OPTION,
    ),
    "validation_status": ("NOT_CHECKED", "PASS", "WARNING", "FAIL"),
    "import_status": ("DRAFT", "READY", "PREVIEWED", "COMMITTED", "SKIPPED"),
}


class ManualReviewSchemaError(RuntimeError):
    pass


def assess_manual_review_schema(
    actual_schema: dict[str, Any],
    mapping: dict[str, str],
) -> dict[str, Any]:
    properties = actual_schema.get("properties") or {}
    if not isinstance(properties, dict):
        raise ManualReviewSchemaError("Manual Reviews schema properties must be an object")

    missing_mapping = sorted(set(MANUAL_REVIEW_PROPERTY_TYPES) - set(mapping))
    duplicate_mappings = sorted(
        name for name in set(mapping.values()) if list(mapping.values()).count(name) > 1
    )
    rows: list[dict[str, Any]] = []
    missing_options: dict[str, list[str]] = {}
    incompatible: list[str] = []

    for logical_field, expected_type in MANUAL_REVIEW_PROPERTY_TYPES.items():
        property_name = mapping.get(logical_field, "")
        actual = properties.get(property_name) if property_name else None
        actual_type = str(actual.get("type") or "") if isinstance(actual, dict) else ""
        option_payload = actual.get(actual_type) if isinstance(actual, dict) else {}
        options = [
            str(option.get("name") or "")
            for option in ((option_payload or {}).get("options") or [])
            if isinstance(option, dict) and str(option.get("name") or "")
        ]
        expected_options = list(MANUAL_REVIEW_OPTION_CONTRACTS.get(logical_field, ()))
        missing = [option for option in expected_options if option not in options]
        if missing:
            missing_options[logical_field] = missing
        compatible = bool(actual) and actual_type == expected_type
        if not compatible:
            incompatible.append(logical_field)
        rows.append(
            {
                "logical_field": logical_field,
                "property": property_name,
                "exists": bool(actual),
                "actual_type": actual_type or None,
                "expected_type": expected_type,
                "options": options,
                "expected_options": expected_options,
                "missing_options": missing,
                "compatible": compatible and not missing,
            }
        )

    only_safe_addition = (
        not missing_mapping
        and not duplicate_mappings
        and not incompatible
        and missing_options == {"review_tag": [POSITION_FOLLOW_UP_OPTION]}
    )
    if missing_mapping or duplicate_mappings or incompatible:
        status = "BLOCKED"
    elif missing_options:
        status = "MIGRATION_REQUIRED" if only_safe_addition else "BLOCKED"
    else:
        status = "PASS"
    return {
        "schema_version": "manual_review_notion_schema_assessment.v1",
        "runner_result": status,
        "data_source_id": str(actual_schema.get("id") or ""),
        "checked_property_count": len(rows),
        "properties": rows,
        "missing_mapping_keys": missing_mapping,
        "duplicate_mapped_properties": duplicate_mappings,
        "incompatible_fields": incompatible,
        "missing_options": missing_options,
        "required_migrations": (
            [{"property": mapping.get("review_tag"), "type": "multi_select", "add_option": POSITION_FOLLOW_UP_OPTION}]
            if only_safe_addition
            else []
        ),
        "additive_apply_allowed": only_safe_addition,
        "destructive_changes": [],
        "would_write": False,
    }


def build_position_follow_up_additive_patch(
    actual_schema: dict[str, Any],
    mapping: dict[str, str],
) -> dict[str, Any]:
    assessment = assess_manual_review_schema(actual_schema, mapping)
    if assessment["runner_result"] == "PASS":
        return {}
    if not assessment["additive_apply_allowed"]:
        raise ManualReviewSchemaError("Schema has incompatible or non-approved differences")
    property_name = resolve_notion_property_name(mapping, "review_tag")
    property_schema = actual_schema["properties"][property_name]
    existing = (property_schema.get("multi_select") or {}).get("options") or []
    preserved: list[dict[str, str]] = []
    for option in existing:
        if not isinstance(option, dict):
            continue
        option_id = str(option.get("id") or "").strip()
        option_name = str(option.get("name") or "").strip()
        if option_id and option_name:
            preserved.append({"id": option_id, "name": option_name})
        elif option_id:
            preserved.append({"id": option_id})
        elif option_name:
            preserved.append({"name": option_name})
    preserved.append({"name": POSITION_FOLLOW_UP_OPTION, "color": "default"})
    return {property_name: {"multi_select": {"options": preserved}}}


def validate_manual_review_create_payload(
    properties: dict[str, Any],
    actual_schema: dict[str, Any],
) -> list[str]:
    schema_properties = actual_schema.get("properties") or {}
    errors: list[str] = []
    for property_name, value in properties.items():
        actual = schema_properties.get(property_name)
        if not isinstance(actual, dict):
            errors.append(f"missing_property:{property_name}")
            continue
        expected_type = str(actual.get("type") or "")
        if expected_type not in value:
            errors.append(f"type_mismatch:{property_name}:expected={expected_type}")
            continue
        if expected_type in {"select", "multi_select"}:
            available = {
                str(option.get("name") or "")
                for option in ((actual.get(expected_type) or {}).get("options") or [])
                if isinstance(option, dict)
            }
            requested = (
                [str((value.get("select") or {}).get("name") or "")]
                if expected_type == "select"
                else [str(item.get("name") or "") for item in value.get("multi_select") or []]
            )
            errors.extend(
                f"missing_option:{property_name}:{option}"
                for option in requested
                if option and option not in available
            )
    return errors
