from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_manual_review_log_validator import (  # noqa: E402
    load_paper_manual_review_log_rows,
    render_paper_manual_review_log_validation_report,
    summarize_paper_manual_review_log_validation,
    validate_paper_manual_review_log_rows,
    write_markdown,
    write_validation_issues_csv,
)
from core.paths import paper_reviews_dir  # noqa: E402


def validate_paper_manual_review_log() -> dict:
    reviews_dir = paper_reviews_dir()
    input_path = reviews_dir / "paper_manual_review_log_template.csv"
    report_output_path = reviews_dir / "paper_manual_review_log_validation_report.md"
    issues_output_path = reviews_dir / "paper_manual_review_log_validation_issues.csv"

    rows = load_paper_manual_review_log_rows(input_path)
    issues, summary_data = validate_paper_manual_review_log_rows(rows)
    summary = summarize_paper_manual_review_log_validation(
        input_path=input_path,
        issues=issues,
        summary_data=summary_data,
        report_output_path=report_output_path,
        issues_output_path=issues_output_path,
    )
    write_validation_issues_csv(issues, issues_output_path)
    write_markdown(report_output_path, render_paper_manual_review_log_validation_report(summary))
    return {
        "input_path": input_path,
        "report_output_path": report_output_path,
        "issues_output_path": issues_output_path,
        "summary": summary,
    }


def main() -> int:
    result = validate_paper_manual_review_log()
    summary = result["summary"]
    print("Paper manual review log validation completed")
    print(f"  input_path: {result['input_path']}")
    print(f"  report_output_path: {result['report_output_path']}")
    print(f"  issues_output_path: {result['issues_output_path']}")
    print(f"  validation_result: {summary['validation_result']}")
    print(f"  error_count: {summary['error_count']}")
    print(f"  warning_count: {summary['warning_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
