from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_manual_review_log_template import (  # noqa: E402
    REQUIRED_BUCKET_COLUMNS,
    REQUIRED_WORKSHEET_COLUMNS,
    build_paper_manual_review_log_template,
    load_csv_rows,
    render_paper_manual_review_log_template_markdown,
    summarize_paper_manual_review_log_template,
    write_markdown,
    write_paper_manual_review_log_template_csv,
)
from core.paths import paper_reports_dir, paper_reviews_dir  # noqa: E402


def generate_paper_manual_review_log_template() -> dict:
    reports_dir = paper_reports_dir()
    reviews_dir = paper_reviews_dir()
    worksheet_csv_path = reports_dir / "paper_symbol_review_worksheet.csv"
    review_bucket_csv_path = reports_dir / "paper_symbol_review_buckets.csv"
    csv_output_path = reviews_dir / "paper_manual_review_log_template.csv"
    markdown_output_path = reviews_dir / "paper_manual_review_log_template.md"

    worksheet_rows = load_csv_rows(
        worksheet_csv_path,
        REQUIRED_WORKSHEET_COLUMNS,
        "paper_symbol_review_worksheet.csv",
    )
    review_bucket_rows = load_csv_rows(
        review_bucket_csv_path,
        REQUIRED_BUCKET_COLUMNS,
        "paper_symbol_review_buckets.csv",
    )
    output_rows, summary_data, warnings = build_paper_manual_review_log_template(
        worksheet_rows,
        review_bucket_rows,
        source_worksheet_path=worksheet_csv_path,
    )
    write_paper_manual_review_log_template_csv(output_rows, csv_output_path)
    summary = summarize_paper_manual_review_log_template(
        summary_data,
        warnings,
        worksheet_csv_path=worksheet_csv_path,
        review_bucket_csv_path=review_bucket_csv_path,
        csv_output_path=csv_output_path,
        markdown_output_path=markdown_output_path,
    )
    write_markdown(
        markdown_output_path,
        render_paper_manual_review_log_template_markdown(summary),
    )
    return {
        "worksheet_csv_path": worksheet_csv_path,
        "review_bucket_csv_path": review_bucket_csv_path,
        "csv_output_path": csv_output_path,
        "markdown_output_path": markdown_output_path,
        "summary": summary,
        "output_rows": output_rows,
    }


def main() -> int:
    result = generate_paper_manual_review_log_template()
    summary = result["summary"]
    print("Paper manual review log template generated")
    print(f"  worksheet_csv_path: {result['worksheet_csv_path']}")
    print(f"  review_bucket_csv_path: {result['review_bucket_csv_path']}")
    print(f"  csv_output_path: {result['csv_output_path']}")
    print(f"  markdown_output_path: {result['markdown_output_path']}")
    print(f"  review_template_row_count: {summary['review_template_row_count']}")
    print(f"  symbol_count: {summary['symbol_count']}")
    print(f"  warnings: {len(summary['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
