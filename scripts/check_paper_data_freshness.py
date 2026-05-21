from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_data_freshness import (  # noqa: E402
    run_paper_data_freshness_check,
    write_paper_data_freshness_report,
)


def _print_summary(summary: dict) -> None:
    print("PAPER DATA FRESHNESS")
    print(f"  target_date: {summary['target_date']}")
    print(f"  market_db_path: {summary['market_db_path']}")
    print(f"  result: {summary['result']}")
    print(f"  error_count: {summary['error_count']}")
    print(f"  warning_count: {summary['warning_count']}")
    for item in summary["checks"]:
        if item["severity"] in {"error", "warning"}:
            print(
                f"  - [{item['severity']}] {item['check_name']} "
                f"{item['message']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only market data freshness check for paper planning")
    parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--strict", action="store_true", help="Escalate stale-data warnings to errors where applicable")
    parser.add_argument("--write-report", action="store_true", help="Write markdown/CSV report under outputs/paper_test/reports")
    args = parser.parse_args()

    summary = run_paper_data_freshness_check(date_str=args.date, strict=args.strict)
    _print_summary(summary)
    if args.write_report:
        markdown_path, issues_path = write_paper_data_freshness_report(summary)
        print(f"  report_path: {markdown_path}")
        print(f"  issues_path: {issues_path}")
    return 1 if summary["result"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
