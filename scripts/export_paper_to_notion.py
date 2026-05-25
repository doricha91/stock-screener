from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_client import NotionClient  # noqa: E402
from core.notion_exporters import export_selected_paper_reports_to_notion  # noqa: E402
from core.notion_mapping import load_notion_property_mapping  # noqa: E402
from core.notion_settings import get_notion_token, load_notion_settings  # noqa: E402

load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export selected paper reports to Notion")
    parser.add_argument("--weekly", action="store_true", help="Export weekly status report")
    parser.add_argument("--benchmark", action="store_true", help="Export benchmark report")
    parser.add_argument("--account-snapshot", action="store_true", help="Export latest account snapshot")
    parser.add_argument("--daily-plan", action="store_true", help="Export latest daily plan")
    parser.add_argument("--daily-review-summary", action="store_true", help="Export daily review summary")
    parser.add_argument("--date", help="Review date for --daily-review-summary in YYYY-MM-DD format")
    parser.add_argument("--all", action="store_true", help="Export all supported targets")
    parser.add_argument("--dry-run", action="store_true", help="Build payload summary without Notion write")
    parser.add_argument("--json", action="store_true", help="Print export summary JSON to stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    export_weekly = args.weekly or args.all
    export_benchmark = args.benchmark or args.all
    export_account_snapshot = args.account_snapshot or args.all
    export_daily_plan = args.daily_plan
    export_daily_review_summary = args.daily_review_summary
    if export_daily_review_summary and not args.date:
        parser.error("--date is required for --daily-review-summary")
    if not any([export_weekly, export_benchmark, export_account_snapshot, export_daily_plan, export_daily_review_summary]):
        parser.error("Select at least one target: --weekly, --benchmark, --account-snapshot, --daily-plan, --daily-review-summary, or --all")

    settings = load_notion_settings(allow_missing=True)
    mapping = load_notion_property_mapping()
    client = None if args.dry_run else NotionClient(get_notion_token(settings))
    results = export_selected_paper_reports_to_notion(
        client=client,
        settings=settings,
        mapping_root=mapping,
        export_weekly=export_weekly,
        export_benchmark=export_benchmark,
        export_account_snapshot=export_account_snapshot,
        export_daily_plan=export_daily_plan,
        export_daily_review_summary=export_daily_review_summary,
        review_date=args.date,
        dry_run=args.dry_run,
    )
    summary = [
        {
            "target": item.target,
            "data_source_key": item.data_source_key,
            "external_key": item.external_key,
            "action": item.action,
            "page_id": item.page_id,
            "source_path": item.source_path,
            "dry_run": item.dry_run,
        }
        for item in results
    ]

    print("PAPER NOTION EXPORT")
    for item in summary:
        print(
            f"  {item['target']}: action={item['action']} "
            f"external_key={item['external_key']} source={item['source_path']}"
        )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
