from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_client import NotionAPIError, NotionClient  # noqa: E402
from core.notion_manual_review_status_sync import (  # noqa: E402
    ManualReviewStatusSyncError,
    sync_manual_review_status,
)
from core.notion_mapping import load_notion_property_mapping  # noqa: E402
from core.notion_settings import (  # noqa: E402
    NotionSettingsError,
    get_notion_data_source_id,
    get_notion_token,
    load_notion_settings,
)

load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sync committed Manual Review results back to Notion status fields using "
            "the PAPER14-7E commit sidecar report."
        )
    )
    parser.add_argument("--date", required=True, help="Review date in YYYY-MM-DD format")
    parser.add_argument("--commit-report", required=True, help="Path to manual review commit report JSON")
    parser.add_argument("--dry-run", action="store_true", help="Build sync payload without updating Notion pages")
    parser.add_argument("--json", action="store_true", help="Print machine-readable result JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    mapping = load_notion_property_mapping()
    settings = load_notion_settings(allow_missing=True)

    data_source_check = "not_checked"
    try:
        get_notion_data_source_id(
            settings,
            "manual_reviews",
            env_override="NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID",
        )
        data_source_check = "configured"
    except NotionSettingsError:
        data_source_check = "missing"

    client: NotionClient | None = None
    if not args.dry_run:
        client = NotionClient(get_notion_token(settings))

    try:
        result = sync_manual_review_status(
            client=client,
            mapping_root=mapping,
            review_date=args.date,
            commit_report_path=Path(args.commit_report),
            dry_run=args.dry_run,
            data_source_check=data_source_check,
        )
    except (ManualReviewStatusSyncError, NotionSettingsError, NotionAPIError) as exc:
        if args.json:
            print(json.dumps({"overall_status": "FAILED", "error": str(exc)}, ensure_ascii=False, indent=2))
        else:
            print(f"MANUAL REVIEW STATUS SYNC FAILED\n{exc}")
        return 1

    payload = result.to_dict()
    mode = "DRY RUN" if args.dry_run else "APPLY"
    print("MANUAL REVIEW STATUS SYNC")
    print(
        f"  mode={mode} date={result.review_date} candidates={result.candidate_count} "
        f"overall_status={result.overall_status}"
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if result.overall_status == "SUCCESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
