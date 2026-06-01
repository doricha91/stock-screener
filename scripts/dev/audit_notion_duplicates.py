from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_client import NotionAPIError, NotionClient  # noqa: E402
from core.notion_duplicate_audit import (  # noqa: E402
    DAILY_OPS_STATUS_AUDIT_TARGET,
    NotionDuplicateAuditError,
    audit_daily_ops_status_duplicate,
)
from core.notion_mapping import load_notion_property_mapping  # noqa: E402
from core.notion_settings import NotionSettingsError, get_notion_token, load_notion_settings  # noqa: E402

load_dotenv()


def _safe_error_message(exc: Exception) -> str:
    message = str(exc)
    sensitive_values = [
        os.environ.get("NOTION_TOKEN") or "",
        os.environ.get("NOTION_DAILY_OPS_STATUS_DATA_SOURCE_ID") or "",
    ]
    for value in sensitive_values:
        value = value.strip()
        if value:
            message = message.replace(value, "****")
    return re.sub(r"(/data_sources/)[^/\s]+", r"\1****", message)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only Notion duplicate audit for guarded paper export targets."
    )
    parser.add_argument("--target", required=True, help="Audit target. Currently only daily_ops_status is supported.")
    parser.add_argument("--account-id", required=True, help="Paper account id for the audited External Key")
    parser.add_argument("--date", help="Status date in YYYY-MM-DD or YYYYMMDD format")
    parser.add_argument("--external-key", help="Expected External Key. Must match account/date when provided")
    parser.add_argument("--expected-page-id", help="Optional expected Notion page id for update rerun checks")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.target != DAILY_OPS_STATUS_AUDIT_TARGET:
        parser.error("Only --target daily_ops_status is supported in this stage")
    if not args.date and not args.external_key:
        parser.error("--date or --external-key is required")
    if args.external_key and not args.date:
        parser.error("--date is required when --external-key is provided so account/date consistency can be checked")

    try:
        settings = load_notion_settings(allow_missing=True)
        mapping_root = load_notion_property_mapping()
        client = NotionClient(get_notion_token(settings))
        result = audit_daily_ops_status_duplicate(
            client=client,
            settings=settings,
            mapping_root=mapping_root,
            account_id=args.account_id,
            status_date=args.date,
            external_key=args.external_key,
            expected_page_id=args.expected_page_id,
        )
    except (NotionDuplicateAuditError, NotionSettingsError, NotionAPIError) as exc:
        payload = {
            "target": args.target,
            "account_id": args.account_id,
            "status_date": args.date or "",
            "external_key": args.external_key or "",
            "match_count": 0,
            "page_ids": [],
            "classification": "query_error" if isinstance(exc, NotionAPIError) else "settings_error",
            "recommended_action": "stop_actual_query_error"
            if isinstance(exc, NotionAPIError)
            else "stop_actual_settings_error",
            "write_executed": False,
            "error": _safe_error_message(exc),
        }
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        else:
            print(f"NOTION DUPLICATE AUDIT FAILED\n{exc}")
        return 1

    payload = result.to_dict()
    print("NOTION DUPLICATE AUDIT")
    print(
        f"  target={payload['target']} account_id={payload['account_id']} "
        f"status_date={payload['status_date']} classification={payload['classification']} "
        f"match_count={payload['match_count']} write_executed=false"
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["classification"] in {"create_candidate", "update_candidate", "manual_review_required"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
