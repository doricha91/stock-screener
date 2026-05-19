from __future__ import annotations

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
from core.paths import paper_reviews_dir  # noqa: E402


def append_paper_manual_review_log_from_template() -> dict:
    reviews_dir = paper_reviews_dir()
    template_path = reviews_dir / "paper_manual_review_log_template.csv"
    target_log_path = reviews_dir / "paper_manual_review_log.csv"
    append_report_path = reviews_dir / "paper_manual_review_log_append_report.md"
    append_issues_path = reviews_dir / "paper_manual_review_log_append_issues.csv"

    template_rows = load_paper_manual_review_log_rows(template_path)
    existing_log_rows = load_existing_paper_manual_review_log_rows(target_log_path)
    final_rows, append_issues, summary_data = append_paper_manual_review_log(
        template_rows,
        existing_log_rows,
    )
    if summary_data["append_executed"]:
        write_paper_manual_review_log(final_rows, target_log_path)
    write_append_issues_csv(append_issues, append_issues_path)
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
    )
    return {
        "template_path": template_path,
        "target_log_path": target_log_path,
        "append_report_path": append_report_path,
        "append_issues_path": append_issues_path,
        "summary": summary,
    }


def main() -> int:
    result = append_paper_manual_review_log_from_template()
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
