from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_manual_review_log_append import (  # noqa: E402
    append_paper_manual_review_log,
    load_existing_paper_manual_review_log_rows,
    render_paper_manual_review_log_append_report,
    summarize_paper_manual_review_log_append,
    write_append_issues_csv,
    write_markdown,
    write_paper_manual_review_log,
)
from core.paper_manual_review_log_validator import load_paper_manual_review_log_rows  # noqa: E402
from core.paper_account_paths import PaperAccountPaths, build_paper_account_paths  # noqa: E402
from core.paper_account_guard import require_initialized_writer_account_paths  # noqa: E402


def append_paper_manual_review_log_from_template(
    account_paths: PaperAccountPaths | None = None,
) -> dict:
    require_initialized_writer_account_paths(
        account_paths,
        command_name="append_paper_manual_review_log_from_template",
    )
    reviews_dir = account_paths.reviews_dir
    allowed_root = account_paths.root
    template_path = reviews_dir / "paper_manual_review_log_template.csv"
    target_log_path = reviews_dir / "paper_manual_review_log.csv"
    append_report_path = reviews_dir / "paper_manual_review_log_append_report.md"
    append_issues_path = reviews_dir / "paper_manual_review_log_append_issues.csv"

    template_rows = load_paper_manual_review_log_rows(template_path, allowed_root=allowed_root)
    existing_log_rows = load_existing_paper_manual_review_log_rows(target_log_path, allowed_root=allowed_root)
    final_rows, append_issues, summary_data = append_paper_manual_review_log(
        template_rows,
        existing_log_rows,
    )
    if summary_data["append_executed"]:
        write_paper_manual_review_log(final_rows, target_log_path, account_paths=account_paths)
    write_append_issues_csv(append_issues, append_issues_path, account_paths=account_paths)
    summary = summarize_paper_manual_review_log_append(
        template_path=template_path,
        target_log_path=target_log_path,
        append_report_path=append_report_path,
        append_issues_path=append_issues_path,
        summary_data=summary_data,
    )
    write_markdown(
        append_report_path,
        render_paper_manual_review_log_append_report(summary),
        account_paths=account_paths,
    )
    return {
        "template_path": template_path,
        "target_log_path": target_log_path,
        "append_report_path": append_report_path,
        "append_issues_path": append_issues_path,
        "summary": summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Append a manual review log for one paper account")
    parser.add_argument("--account-id", required=True, help="Initialized paper account id")
    args = parser.parse_args()
    try:
        account_paths = build_paper_account_paths(args.account_id, create=False)
        result = append_paper_manual_review_log_from_template(account_paths=account_paths)
    except ValueError as exc:
        print(f"Paper manual review append aborted: {exc}")
        return 1
    summary = result["summary"]
    print("Paper manual review log append completed")
    print(f"  template_path: {result['template_path']}")
    print(f"  target_log_path: {result['target_log_path']}")
    print(f"  append_report_path: {result['append_report_path']}")
    print(f"  append_issues_path: {result['append_issues_path']}")
    print(f"  validation_result: {summary['validation_result']}")
    print(f"  rows_appended: {summary['rows_appended']}")
    print(f"  rows_skipped_pending: {summary['rows_skipped_pending']}")
    print(f"  rows_skipped_duplicate: {summary['rows_skipped_duplicate']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
