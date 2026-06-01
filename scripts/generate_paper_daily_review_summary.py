from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_account_paths import PaperAccountPaths  # noqa: E402
from core.paper_daily_review_summary import (  # noqa: E402
    REQUIRED_REVIEW_BUCKET_COLUMNS,
    REQUIRED_SIDE_BY_SIDE_COLUMNS,
    build_paper_daily_review_summary_data,
    load_csv_rows,
    render_paper_daily_review_summary,
    render_paper_report_index,
    summarize_paper_daily_review_summary,
    write_markdown,
)
from core.paths import paper_reports_dir  # noqa: E402


def generate_paper_daily_review_summary(account_paths: PaperAccountPaths | None = None) -> dict:
    if account_paths is not None and account_paths.account_id != "paper_default":
        reports_dir = account_paths.reports_dir
        allowed_root = account_paths.root
    else:
        reports_dir = paper_reports_dir()
        allowed_root = None
    performance_summary_path = reports_dir / "paper_performance_summary.md"
    side_by_side_path = reports_dir / "paper_symbol_side_by_side_performance.csv"
    review_buckets_path = reports_dir / "paper_symbol_review_buckets.csv"
    worksheet_path = reports_dir / "paper_symbol_review_worksheet.md"
    daily_summary_path = reports_dir / "paper_daily_review_summary.md"
    report_index_path = reports_dir / "paper_report_index.md"

    side_by_side_rows = load_csv_rows(
        side_by_side_path,
        REQUIRED_SIDE_BY_SIDE_COLUMNS,
        "paper_symbol_side_by_side_performance.csv",
        allowed_root=allowed_root,
    )
    review_bucket_rows = load_csv_rows(
        review_buckets_path,
        REQUIRED_REVIEW_BUCKET_COLUMNS,
        "paper_symbol_review_buckets.csv",
        allowed_root=allowed_root,
    )
    summary_data, warnings, report_rows = build_paper_daily_review_summary_data(
        performance_summary_path,
        side_by_side_rows,
        review_bucket_rows,
        worksheet_path,
        report_base_root=reports_dir,
        allowed_root=allowed_root,
    )
    summary = summarize_paper_daily_review_summary(summary_data, warnings)
    write_markdown(
        daily_summary_path,
        render_paper_daily_review_summary(summary),
        allowed_root=allowed_root,
    )
    write_markdown(
        report_index_path,
        render_paper_report_index(report_rows),
        allowed_root=allowed_root,
    )
    return {
        "daily_summary_path": daily_summary_path,
        "report_index_path": report_index_path,
        "summary": summary,
    }


def main() -> int:
    result = generate_paper_daily_review_summary()
    summary = result["summary"]
    print("Paper daily review summary generated")
    print(f"  daily_summary_path: {result['daily_summary_path']}")
    print(f"  report_index_path: {result['report_index_path']}")
    print(f"  symbol_count: {summary['side_by_side_summary']['symbol_count']}")
    print(f"  high_priority_count: {summary['review_bucket_summary']['priority_counts'].get('high', 0)}")
    print(f"  warnings: {len(summary['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
