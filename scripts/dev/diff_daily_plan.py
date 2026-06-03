from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_replay_diff import (  # noqa: E402
    compare_daily_plan_files,
    normalize_replay_diff_date,
    write_daily_plan_diff_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare baseline and regenerated Daily Plan JSON files without regenerating a plan."
    )
    parser.add_argument("--account-id", required=True, help="Paper account id, e.g. paper_sandbox.")
    parser.add_argument("--date", required=True, help="Plan date in YYYY-MM-DD or YYYYMMDD format.")
    parser.add_argument("--baseline-plan", required=True, help="Path to baseline Daily Plan JSON.")
    parser.add_argument("--regenerated-plan", required=True, help="Path to regenerated Daily Plan JSON.")
    parser.add_argument(
        "--output-dir",
        help="Directory for JSON/Markdown diff output. Defaults to the account replay_diff directory.",
    )
    parser.add_argument("--json", action="store_true", help="Print a JSON summary.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    plan_date = normalize_replay_diff_date(args.date)
    report = compare_daily_plan_files(
        account_id=args.account_id,
        plan_date=plan_date,
        baseline_plan_path=args.baseline_plan,
        regenerated_plan_path=args.regenerated_plan,
    )
    paths = write_daily_plan_diff_report(report, output_dir=args.output_dir)
    summary = {
        "schema_version": report["schema_version"],
        "account_id": report["account_id"],
        "plan_date": report["plan_date"],
        "overall_status": report["overall_status"],
        "diff_categories": report["diff_categories"],
        "summary": report["summary"],
        "json_path": paths["json_path"],
        "markdown_path": paths["markdown_path"],
        "write_executed": False,
        "notion_api_called": False,
        "notion_write_export_sync_executed": False,
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Daily Plan diff report written: {paths['json_path']}")
        print(f"Markdown report written: {paths['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
