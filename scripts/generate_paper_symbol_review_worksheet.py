from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_symbol_review_worksheet import (  # noqa: E402
    build_paper_symbol_review_worksheet,
    load_paper_symbol_review_bucket_rows,
    render_paper_symbol_review_worksheet_summary,
    summarize_paper_symbol_review_worksheet,
    write_paper_symbol_review_worksheet_csv,
    write_paper_symbol_review_worksheet_markdown,
)
from core.paths import paper_reports_dir  # noqa: E402


def generate_paper_symbol_review_worksheet() -> dict:
    reports_dir = paper_reports_dir()
    input_path = reports_dir / "paper_symbol_review_buckets.csv"
    markdown_output_path = reports_dir / "paper_symbol_review_worksheet.md"
    csv_output_path = reports_dir / "paper_symbol_review_worksheet.csv"

    input_rows = load_paper_symbol_review_bucket_rows(input_path)
    symbol_rows, question_rows, summary_data, warnings = build_paper_symbol_review_worksheet(input_rows)
    write_paper_symbol_review_worksheet_csv(question_rows, csv_output_path)
    summary = summarize_paper_symbol_review_worksheet(
        summary_data,
        warnings,
        input_path=input_path,
        markdown_output_path=markdown_output_path,
        csv_output_path=csv_output_path,
    )
    markdown = render_paper_symbol_review_worksheet_summary(summary, symbol_rows)
    write_paper_symbol_review_worksheet_markdown(markdown, markdown_output_path)
    return {
        "input_path": input_path,
        "markdown_output_path": markdown_output_path,
        "csv_output_path": csv_output_path,
        "summary": summary,
        "symbol_rows": symbol_rows,
        "question_rows": question_rows,
    }


def main() -> int:
    result = generate_paper_symbol_review_worksheet()
    summary = result["summary"]
    print("Paper symbol review worksheet generated")
    print(f"  input_path: {result['input_path']}")
    print(f"  markdown_output_path: {result['markdown_output_path']}")
    print(f"  csv_output_path: {result['csv_output_path']}")
    print(f"  symbol_count: {summary['symbol_count']}")
    print(f"  question_row_count: {len(result['question_rows'])}")
    print(f"  warnings: {len(summary['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
