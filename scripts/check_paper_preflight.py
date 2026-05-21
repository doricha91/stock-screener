from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_preflight_check import (  # noqa: E402
    REPORT_PATH_NAMES,
    render_paper_preflight_report,
    run_paper_preflight_check,
    write_markdown,
    write_paper_preflight_issues_csv,
)
from core.paths import PAPER_TEST_DIR  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run paper-specific preflight checks")
    parser.add_argument("--date", help="Target date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument(
        "--stage",
        required=True,
        choices=["plan", "eod", "reports", "review-template", "review-append", "all"],
        help="Paper workflow stage to validate",
    )
    parser.add_argument("--strict", action="store_true", help="Escalate warnings to errors")
    parser.add_argument("--write-report", action="store_true", help="Write markdown and issues CSV under outputs/paper_test/reports")
    args = parser.parse_args()

    summary = run_paper_preflight_check(
        stage=args.stage,
        date_str=args.date,
        strict=args.strict,
    )

    print("PAPER PREFLIGHT CHECK")
    print(f"  stage: {summary['stage']}")
    print(f"  date: {summary['date'] or '-'}")
    print(f"  strict: {summary['strict']}")
    print(f"  result: {summary['result']}")
    print(f"  error_count: {summary['error_count']}")
    print(f"  warning_count: {summary['warning_count']}")
    if summary["issues"]:
        print("  issues:")
        for issue in summary["issues"]:
            print(
                f"    - [{issue['severity']}] {issue['stage']}::{issue['check_name']} "
                f"{issue['message']}"
            )
    else:
        print("  issues: none")

    if args.write_report:
        reports_dir = PAPER_TEST_DIR / "reports"
        markdown_path = reports_dir / REPORT_PATH_NAMES["markdown"]
        issues_path = reports_dir / REPORT_PATH_NAMES["issues"]
        write_markdown(markdown_path, render_paper_preflight_report(summary))
        write_paper_preflight_issues_csv(summary["issues"], issues_path)
        print(f"  report_path: {markdown_path}")
        print(f"  issues_path: {issues_path}")

    return 1 if summary["result"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
