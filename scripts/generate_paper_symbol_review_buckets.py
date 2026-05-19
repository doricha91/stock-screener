from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_symbol_review_buckets import (  # noqa: E402
    build_paper_symbol_review_buckets,
    load_paper_symbol_side_by_side_performance_rows,
    render_paper_symbol_review_buckets_summary,
    summarize_paper_symbol_review_buckets,
    write_paper_symbol_review_buckets,
    write_paper_symbol_review_buckets_summary,
)
from core.paths import paper_reports_dir  # noqa: E402


def generate_paper_symbol_review_buckets() -> dict:
    reports_dir = paper_reports_dir()
    input_path = reports_dir / "paper_symbol_side_by_side_performance.csv"
    output_csv_path = reports_dir / "paper_symbol_review_buckets.csv"
    output_summary_path = reports_dir / "paper_symbol_review_buckets_summary.md"

    rows = load_paper_symbol_side_by_side_performance_rows(input_path)
    review_rows, summary_data, warnings = build_paper_symbol_review_buckets(rows)
    write_paper_symbol_review_buckets(review_rows, output_csv_path)
    summary = summarize_paper_symbol_review_buckets(
        summary_data,
        warnings,
        input_path=input_path,
        output_path=output_csv_path,
    )
    write_paper_symbol_review_buckets_summary(
        render_paper_symbol_review_buckets_summary(summary),
        output_summary_path,
    )
    return {
        "input_path": input_path,
        "output_csv_path": output_csv_path,
        "output_summary_path": output_summary_path,
        "summary": summary,
    }


def main() -> int:
    result = generate_paper_symbol_review_buckets()
    summary = result["summary"]
    print("Paper symbol review buckets generated")
    print(f"  input_path: {result['input_path']}")
    print(f"  output_csv_path: {result['output_csv_path']}")
    print(f"  output_summary_path: {result['output_summary_path']}")
    print(f"  bucket_count: {sum(summary['bucket_counts'].values())}")
    print(f"  high_priority_count: {summary['priority_counts'].get('high', 0)}")
    print(f"  warnings: {len(summary['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
