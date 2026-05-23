import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_client import (  # noqa: E402
    NotionClient,
    notion_date,
    notion_number,
    notion_rich_text,
    notion_select,
    notion_title,
)
from core.notion_mapping import get_mapping_section, load_notion_property_mapping, resolve_notion_property_name  # noqa: E402
from core.notion_settings import get_notion_data_source_id, get_notion_token, load_notion_settings  # noqa: E402

load_dotenv()


def _build_smoke_properties(mapping: dict[str, str], *, external_key: str, updated: bool) -> dict[str, dict]:
    status_value = "UPDATED" if updated else "PASS"
    number_value = 2 if updated else 1
    note_value = (
        f"Updated from Python smoke test at {datetime.now(timezone.utc).isoformat()}"
        if updated
        else "Created from Python smoke test."
    )
    return {
        resolve_notion_property_name(mapping, "name"): notion_title("Notion API Smoke Test"),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(external_key),
        resolve_notion_property_name(mapping, "status"): notion_select(status_value),
        resolve_notion_property_name(mapping, "smoke_date"): notion_date(date.today().isoformat()),
        resolve_notion_property_name(mapping, "value"): notion_number(number_value),
        resolve_notion_property_name(mapping, "note"): notion_rich_text(note_value),
    }


def _build_smoke_children() -> list[dict]:
    return [
        {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "This page was created by the StockScreener Notion API smoke test."
                        },
                    }
                ]
            },
        }
    ]


def _parse_flags(argv: list[str] | None) -> tuple[bool, bool]:
    args = argv or []
    return ("--check-only" in args, "--create-test" in args or "--unique-key" in args)


def main(argv: list[str] | None = None) -> int:
    check_only, create_test = _parse_flags(argv)

    settings = load_notion_settings(allow_missing=True)
    token = get_notion_token(settings)
    data_source_id = get_notion_data_source_id(
        settings,
        "smoke_test",
        env_override="NOTION_SMOKE_DATA_SOURCE_ID",
    )
    mapping = get_mapping_section(load_notion_property_mapping(), "smoke_test")
    external_key = "notion_smoke_test:stock_screener"
    client = NotionClient(token)

    print("1. Checking token via /users/me ...")
    bot = client.get_bot_user()
    print("   OK:", bot.get("name"), bot.get("type"))

    print("2. Retrieving data source schema ...")
    data_source = client.retrieve_data_source(data_source_id)
    properties = data_source.get("properties", {})
    required_props = {
        resolve_notion_property_name(mapping, "name"),
        resolve_notion_property_name(mapping, "external_key"),
        resolve_notion_property_name(mapping, "status"),
        resolve_notion_property_name(mapping, "smoke_date"),
        resolve_notion_property_name(mapping, "value"),
        resolve_notion_property_name(mapping, "note"),
    }
    missing = required_props - set(properties.keys())
    if missing:
        raise RuntimeError(f"Data source is missing required properties: {sorted(missing)}")
    print("   OK: required properties present")

    if check_only:
        print("CHECK-ONLY PASSED")
        return 0

    if create_test:
        unique_key = f"{external_key}:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
        create_result = client.upsert_page_by_external_key(
            data_source_id=data_source_id,
            external_key=unique_key,
            external_key_property=resolve_notion_property_name(mapping, "external_key"),
            properties=_build_smoke_properties(mapping, external_key=unique_key, updated=False),
            children=_build_smoke_children(),
        )
        print(f"SMOKE CREATE TEST: {create_result.action.upper()} {create_result.page_id}")
        update_result = client.upsert_page_by_external_key(
            data_source_id=data_source_id,
            external_key=unique_key,
            external_key_property=resolve_notion_property_name(mapping, "external_key"),
            properties=_build_smoke_properties(mapping, external_key=unique_key, updated=True),
            children=None,
        )
        print(f"SMOKE UPDATE TEST: {update_result.action.upper()} {update_result.page_id}")
        print("SMOKE TEST PASSED")
        return 0

    print("3. Checking existing smoke row by External Key ...")
    existing = client.query_by_external_key(
        data_source_id,
        external_key,
        resolve_notion_property_name(mapping, "external_key"),
    )
    result = client.upsert_page_by_external_key(
        data_source_id=data_source_id,
        external_key=external_key,
        external_key_property=resolve_notion_property_name(mapping, "external_key"),
        properties=_build_smoke_properties(mapping, external_key=external_key, updated=bool(existing)),
        children=None if existing else _build_smoke_children(),
    )
    print(f"   {result.action.upper()}:", result.page_id)
    print("SMOKE TEST PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        print("SMOKE TEST FAILED:", exc, file=sys.stderr)
        raise
