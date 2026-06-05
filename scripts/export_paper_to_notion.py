from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.notion_account_keys import normalize_notion_account_id  # noqa: E402
from core.notion_client import NotionAPIError, NotionClient  # noqa: E402
from core.notion_daily_ops_status_exporter import (  # noqa: E402
    DAILY_OPS_STATUS_TARGET,
    NotionDailyOpsStatusExportError,
    export_daily_ops_status_actual,
    export_daily_ops_status_dry_run,
)
from core.notion_exporters import (  # noqa: E402
    MANUAL_REVIEW_TEMPLATE_TARGET,
    NotionExportError,
    export_manual_review_template_to_notion,
    export_selected_paper_reports_to_notion,
)
from core.notion_mapping import load_notion_property_mapping  # noqa: E402
from core.notion_settings import NotionSettingsError, get_notion_token, load_notion_settings  # noqa: E402

load_dotenv()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Export selected paper reports to Notion")
    parser.add_argument("--account-id", help="Paper account id for account-aware External Key and Account ID payload")
    parser.add_argument("--weekly", action="store_true", help="Export weekly status report")
    parser.add_argument("--benchmark", action="store_true", help="Export benchmark report")
    parser.add_argument("--account-snapshot", action="store_true", help="Export latest account snapshot")
    parser.add_argument("--daily-plan", action="store_true", help="Export latest daily plan")
    parser.add_argument("--daily-review-summary", action="store_true", help="Export daily review summary")
    parser.add_argument("--daily-ops-status", action="store_true", help="Build Daily Ops Status Notion payload summary")
    parser.add_argument("--manual-review-template", action="store_true", help="Export Manual Review template rows")
    parser.add_argument("--date", help="Date for dated exports in YYYY-MM-DD format")
    parser.add_argument("--all", action="store_true", help="Export all supported targets")
    parser.add_argument("--dry-run", action="store_true", help="Build payload summary without Notion write")
    parser.add_argument("--confirm-actual", action="store_true", help="Confirm actual Notion write for guarded targets")
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
    export_daily_ops_status = args.daily_ops_status
    export_manual_review_template = args.manual_review_template
    if export_daily_review_summary and not args.date:
        parser.error("--date is required for --daily-review-summary")
    if export_manual_review_template and not args.date:
        parser.error("--date is required for --manual-review-template")
    if export_daily_ops_status and not (args.dry_run or args.confirm_actual):
        parser.error("--dry-run or --confirm-actual is required for --daily-ops-status in this stage")
    if export_manual_review_template and not (args.dry_run or args.confirm_actual):
        parser.error("--dry-run or --confirm-actual is required for --manual-review-template")
    if export_daily_ops_status and args.dry_run and args.confirm_actual:
        parser.error("--dry-run and --confirm-actual cannot be used together for --daily-ops-status")
    if export_manual_review_template and args.dry_run and args.confirm_actual:
        parser.error("--dry-run and --confirm-actual cannot be used together for --manual-review-template")
    other_targets = [
        export_weekly,
        export_benchmark,
        export_account_snapshot,
        export_daily_plan,
        export_daily_review_summary,
    ]
    if export_daily_ops_status and any([*other_targets, export_manual_review_template]):
        parser.error("--daily-ops-status cannot be combined with other export targets in this stage")
    if export_manual_review_template and any([*other_targets, export_daily_ops_status]):
        parser.error("--manual-review-template cannot be combined with other export targets in this stage")
    if not any([*other_targets, export_daily_ops_status, export_manual_review_template]):
        parser.error(
            "Select at least one target: --weekly, --benchmark, --account-snapshot, --daily-plan, "
            "--daily-review-summary, --daily-ops-status, --manual-review-template, or --all"
        )

    settings = load_notion_settings(allow_missing=True)
    mapping = load_notion_property_mapping()
    if export_daily_ops_status:
        resolved_account_id = normalize_notion_account_id(args.account_id)
        try:
            if args.dry_run:
                summary = export_daily_ops_status_dry_run(
                    settings=settings,
                    mapping_root=mapping,
                    account_id=args.account_id,
                    date_str=args.date,
                )
            else:
                client = NotionClient(get_notion_token(settings))
                summary = export_daily_ops_status_actual(
                    client=client,
                    settings=settings,
                    mapping_root=mapping,
                    account_id=args.account_id,
                    date_str=args.date,
                )
        except (NotionAPIError, NotionDailyOpsStatusExportError, NotionSettingsError) as exc:
            if not args.dry_run:
                failure_summary = {
                    "target": DAILY_OPS_STATUS_TARGET,
                    "account_id": resolved_account_id,
                    "status_date": "",
                    "external_key": "",
                    "dry_run": False,
                    "actual_export": True,
                    "action": "failed",
                    "page_id": "",
                    "workflow_status": "",
                    "review_progress_status": "",
                    "sync_status": "FAILED",
                    "synced_at": "",
                    "data_source_configured": False,
                    "error": str(exc),
                }
                print("PAPER NOTION EXPORT")
                print(
                    f"  daily_ops_status: account_id={failure_summary['account_id']} "
                    f"action=failed error={failure_summary['error']}"
                )
                if args.json:
                    print(json.dumps(failure_summary, ensure_ascii=False, indent=2))
                return 1
            raise
        print("PAPER NOTION EXPORT")
        print(
            f"  daily_ops_status: account_id={summary['account_id']} "
            f"workflow_status={summary['workflow_status']} "
            f"external_key={summary['external_key']} "
            f"data_source_configured={str(bool(summary['data_source_configured'])).lower()}"
        )
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    if export_manual_review_template:
        resolved_account_id = normalize_notion_account_id(args.account_id)
        try:
            client = NotionClient(get_notion_token(settings))
            summary = export_manual_review_template_to_notion(
                client=client,
                settings=settings,
                mapping_root=mapping,
                review_date=args.date,
                account_id=resolved_account_id,
                dry_run=args.dry_run,
            )
        except (NotionAPIError, NotionExportError, NotionSettingsError) as exc:
            failure_summary = {
                "target": MANUAL_REVIEW_TEMPLATE_TARGET,
                "account_id": resolved_account_id,
                "review_date": args.date or "",
                "candidate_count": 0,
                "create_count": 0,
                "update_count": 0,
                "created_count": 0,
                "updated_count": 0,
                "skip_count": 0,
                "failed_count": 1,
                "source_template_path": "",
                "dry_run": args.dry_run,
                "would_write": False,
                "error": str(exc),
            }
            print("PAPER NOTION EXPORT")
            print(
                f"  manual_review_template: account_id={resolved_account_id} "
                f"action=failed error={exc}"
            )
            if args.json:
                print(json.dumps(failure_summary, ensure_ascii=False, indent=2))
            return 1
        print("PAPER NOTION EXPORT")
        print(
            f"  manual_review_template: account_id={summary['account_id']} "
            f"review_date={summary['review_date']} candidates={summary['candidate_count']} "
            f"create={summary['create_count']} update={summary['update_count']} "
            f"failed={summary['failed_count']} source={summary['source_template_path']}"
        )
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    client = None if args.dry_run else NotionClient(get_notion_token(settings))
    results = export_selected_paper_reports_to_notion(
        client=client,
        settings=settings,
        mapping_root=mapping,
        account_id=args.account_id,
        export_weekly=export_weekly,
        export_benchmark=export_benchmark,
        export_account_snapshot=export_account_snapshot,
        export_daily_plan=export_daily_plan,
        export_daily_review_summary=export_daily_review_summary,
        review_date=args.date,
        daily_plan_date=args.date if export_daily_plan else None,
        dry_run=args.dry_run,
    )
    summary = [
        {
            "account_id": item.account_id,
            "target": item.target,
            "legacy_external_key": item.legacy_external_key,
            "legacy_fallback_used": item.legacy_fallback_used,
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
            f"  {item['target']}: account_id={item['account_id']} action={item['action']} "
            f"external_key={item['external_key']} source={item['source_path']}"
        )
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
