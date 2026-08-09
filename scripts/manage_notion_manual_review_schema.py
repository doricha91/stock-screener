from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_client import NotionClient  # noqa: E402
from core.notion_manual_review_schema import (  # noqa: E402
    POSITION_FOLLOW_UP_OPTION,
    ManualReviewSchemaError,
    assess_manual_review_schema,
    build_position_follow_up_additive_patch,
)
from core.notion_mapping import get_mapping_section, load_notion_property_mapping  # noqa: E402
from core.notion_settings import (  # noqa: E402
    get_notion_data_source_id,
    get_notion_token,
    load_notion_settings,
)

load_dotenv(ROOT / ".env")


def manage_manual_review_schema(
    *,
    apply: bool = False,
    confirm_data_source_id: str | None = None,
    confirm_additive_option: str | None = None,
    client: NotionClient | None = None,
) -> dict[str, Any]:
    settings = load_notion_settings(allow_missing=True)
    mapping = get_mapping_section(load_notion_property_mapping(), "manual_reviews")
    data_source_id = get_notion_data_source_id(
        settings,
        "manual_reviews",
        env_override="NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID",
    )
    notion = client or NotionClient(get_notion_token(settings))
    actual = notion.get_data_source_schema(data_source_id)
    assessment = assess_manual_review_schema(actual, mapping)
    parent = actual.get("parent") if isinstance(actual.get("parent"), dict) else {}
    assessment["database_page_id"] = str(parent.get("database_id") or "")
    assessment["mode"] = "ASSESS" if not apply else "APPLY"
    if not apply:
        return assessment
    if confirm_data_source_id != data_source_id:
        raise ManualReviewSchemaError("--confirm-data-source-id must exactly match the live data source id")
    if confirm_additive_option != POSITION_FOLLOW_UP_OPTION:
        raise ManualReviewSchemaError(
            f"--confirm-additive-option must be {POSITION_FOLLOW_UP_OPTION}"
        )
    if assessment["runner_result"] == "PASS":
        return {**assessment, "runner_result": "PASS", "applied": False, "would_write": False}
    patch = build_position_follow_up_additive_patch(actual, mapping)
    notion.update_data_source_properties(data_source_id, patch)
    verified = assess_manual_review_schema(notion.get_data_source_schema(data_source_id), mapping)
    if verified["runner_result"] != "PASS":
        raise ManualReviewSchemaError("Additive schema migration did not verify as PASS")
    return {
        **verified,
        "database_page_id": assessment["database_page_id"],
        "mode": "APPLY",
        "applied": True,
        "applied_change": {
            "property": mapping["review_tag"],
            "type": "multi_select",
            "added_option": POSITION_FOLLOW_UP_OPTION,
        },
        "would_write": True,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Assess or explicitly apply the additive Manual Reviews schema contract"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--assess", action="store_true", help="Read-only full schema compatibility audit")
    mode.add_argument("--apply", action="store_true", help="Apply only the approved additive option migration")
    parser.add_argument("--confirm-data-source-id")
    parser.add_argument("--confirm-additive-option")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    try:
        result = manage_manual_review_schema(
            apply=args.apply,
            confirm_data_source_id=args.confirm_data_source_id,
            confirm_additive_option=args.confirm_additive_option,
        )
    except Exception as exc:
        print(json.dumps({"runner_result": "BLOCKED", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["runner_result"] in {"PASS", "MIGRATION_REQUIRED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
