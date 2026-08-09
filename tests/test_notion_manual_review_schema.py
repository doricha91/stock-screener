from __future__ import annotations

from copy import deepcopy

import pytest

from core.notion_exporters import build_manual_review_template_properties
from core.notion_manual_review_schema import (
    MANUAL_REVIEW_OPTION_CONTRACTS,
    MANUAL_REVIEW_PROPERTY_TYPES,
    ManualReviewSchemaError,
    assess_manual_review_schema,
    build_position_follow_up_additive_patch,
    validate_manual_review_create_payload,
)
from scripts.manage_notion_manual_review_schema import manage_manual_review_schema


DATA_SOURCE_ID = "36c6806c-e0e1-80cf-899e-000b35353cc2"


def _mapping() -> dict[str, str]:
    return {
        "name": "Name",
        "external_key": "External Key",
        "account_id": "Account ID",
        "review_date": "Review Date",
        "symbol": "Symbol",
        "question_id": "Question ID",
        "question": "Question",
        "manual_answer": "Manual Answer",
        "review_status": "Review Status",
        "follow_up_needed": "Follow-up Needed",
        "review_tag": "Review Tag",
        "reviewer_note": "Reviewer Note",
        "source_template_key": "Source Template Key",
        "validation_status": "Validation Status",
        "validation_message": "Validation Message",
        "import_status": "Import Status",
        "imported_at": "Imported At",
        "synced_at": "Synced At",
    }


def _schema(*, include_position_follow_up: bool = True) -> dict:
    properties = {}
    for logical, property_type in MANUAL_REVIEW_PROPERTY_TYPES.items():
        options = list(MANUAL_REVIEW_OPTION_CONTRACTS.get(logical, ()))
        if logical == "review_tag" and not include_position_follow_up:
            options.remove("position_follow_up")
        type_body = {}
        if property_type in {"select", "multi_select"}:
            type_body["options"] = [
                {"id": f"{logical}-{index}", "name": option, "color": "default"}
                for index, option in enumerate(options)
            ]
        properties[_mapping()[logical]] = {
            "id": f"id-{logical}",
            "name": _mapping()[logical],
            "type": property_type,
            property_type: type_body,
        }
    return {
        "id": DATA_SOURCE_ID,
        "parent": {"database_id": "database-page-id"},
        "properties": properties,
    }


def _properties(symbol: str, question_id: str, review_tag: str) -> dict:
    return build_manual_review_template_properties(
        {
            "symbol": symbol,
            "question_id": question_id,
            "question_text": "Question",
            "review_tag": review_tag,
            "source_worksheet_path": "scope.json",
        },
        _mapping(),
        account_id="paper_pilot_202606",
        review_date="2026-08-10",
        external_key=f"manual_review:paper_pilot_202606:2026-08-10:{symbol}:{question_id}",
    )


@pytest.mark.parametrize(
    ("symbol", "question_id", "review_tag"),
    [
        ("AMCR", "position_review_1", "position_follow_up"),
        ("CMG", "execution_review_1", "execution_quality"),
        ("ACCOUNT", "account_review_1", "position_sizing"),
    ],
)
def test_representative_create_payloads_match_live_schema_shape(symbol, question_id, review_tag) -> None:
    properties = _properties(symbol, question_id, review_tag)
    assert properties["Review Tag"] == {"multi_select": [{"name": review_tag}]}
    assert validate_manual_review_create_payload(properties, _schema()) == []


def test_missing_position_follow_up_is_the_only_additive_migration() -> None:
    result = assess_manual_review_schema(_schema(include_position_follow_up=False), _mapping())
    assert result["runner_result"] == "MIGRATION_REQUIRED"
    assert result["missing_options"] == {"review_tag": ["position_follow_up"]}
    assert result["additive_apply_allowed"] is True
    assert result["destructive_changes"] == []


def test_complete_schema_assessment_passes_all_mappings_types_and_options() -> None:
    result = assess_manual_review_schema(_schema(), _mapping())
    assert result["runner_result"] == "PASS"
    assert result["checked_property_count"] == 18
    assert all(row["exists"] and row["compatible"] for row in result["properties"])


def test_review_tag_wrong_type_is_blocked_not_migrated() -> None:
    schema = _schema()
    schema["properties"]["Review Tag"]["type"] = "select"
    result = assess_manual_review_schema(schema, _mapping())
    assert result["runner_result"] == "BLOCKED"
    assert result["additive_apply_allowed"] is False
    with pytest.raises(ManualReviewSchemaError):
        build_position_follow_up_additive_patch(schema, _mapping())


def test_additive_patch_preserves_every_existing_option() -> None:
    schema = _schema(include_position_follow_up=False)
    patch = build_position_follow_up_additive_patch(schema, _mapping())
    options = patch["Review Tag"]["multi_select"]["options"]
    assert [item["id"] for item in options[:-1]] == [
        option["id"] for option in schema["properties"]["Review Tag"]["multi_select"]["options"]
    ]
    assert options[-1] == {"name": "position_follow_up", "color": "default"}


class FakeSchemaClient:
    def __init__(self, schema: dict):
        self.schema = schema
        self.updates: list[tuple[str, dict]] = []

    def get_data_source_schema(self, data_source_id: str) -> dict:
        assert data_source_id == DATA_SOURCE_ID
        return self.schema

    def update_data_source_properties(self, data_source_id: str, properties: dict) -> dict:
        self.updates.append((data_source_id, properties))
        updated = deepcopy(self.schema)
        updated["properties"]["Review Tag"]["multi_select"]["options"].append(
            {"id": "new-option", "name": "position_follow_up", "color": "default"}
        )
        self.schema = updated
        return updated


def test_schema_apply_requires_exact_confirmation_and_is_additive(monkeypatch) -> None:
    monkeypatch.setenv("NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID", DATA_SOURCE_ID)
    client = FakeSchemaClient(_schema(include_position_follow_up=False))
    with pytest.raises(ManualReviewSchemaError):
        manage_manual_review_schema(apply=True, client=client)
    result = manage_manual_review_schema(
        apply=True,
        confirm_data_source_id=DATA_SOURCE_ID,
        confirm_additive_option="position_follow_up",
        client=client,
    )
    assert result["runner_result"] == "PASS"
    assert result["applied"] is True
    assert len(client.updates) == 1
