from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_client import NotionClient  # noqa: E402
from core.notion_daily_ops_actual_preflight import run_daily_ops_status_actual_preflight  # noqa: E402
from core.notion_mapping import load_notion_property_mapping  # noqa: E402
from core.notion_settings import NotionSettingsError, get_notion_token, load_notion_settings  # noqa: E402

load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only Daily Ops Status actual preflight. "
            "This command does not execute Notion actual export or write."
        )
    )
    parser.add_argument("--account-id", required=True, help="Paper account id. Currently only paper_sandbox can pass.")
    parser.add_argument("--date", required=True, help="Status date in YYYY-MM-DD or YYYYMMDD format.")
    parser.add_argument("--external-key", help="Optional External Key; must match account/date when provided.")
    parser.add_argument("--expected-page-id", help="Optional expected Notion page id for update rerun checks.")
    parser.add_argument("--json", action="store_true", help="Print JSON result.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = load_notion_settings(allow_missing=True)
    mapping_root = load_notion_property_mapping()
    try:
        token = get_notion_token(settings)
    except NotionSettingsError:
        token = "preflight-token-placeholder"
    client = NotionClient(token)
    result = run_daily_ops_status_actual_preflight(
        client=client,
        settings=settings,
        mapping_root=mapping_root,
        account_id=args.account_id,
        status_date=args.date,
        external_key=args.external_key,
        expected_page_id=args.expected_page_id,
    )
    payload = result.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print("DAILY OPS STATUS ACTUAL PREFLIGHT")
        print(
            f"  account_id={payload['account_id']} status_date={payload['status_date']} "
            f"overall_status={payload['overall_status']} write_executed=false"
        )
        print(f"  recommended_action={payload['recommended_action']}")
    return 1 if payload["overall_status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
