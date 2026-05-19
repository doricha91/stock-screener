from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_symbol_side_by_side_performance import (  # noqa: E402
    build_paper_symbol_side_by_side_performance,
    load_paper_symbol_realized_performance_rows,
    load_paper_symbol_unrealized_performance_rows,
    render_paper_symbol_side_by_side_performance_summary,
    summarize_paper_symbol_side_by_side_performance,
    write_paper_symbol_side_by_side_performance,
    write_paper_symbol_side_by_side_performance_summary,
)
from core.paths import paper_reports_dir  # noqa: E402


def generate_paper_symbol_side_by_side_performance() -> dict:
    reports_dir = paper_reports_dir()
    realized_input_path = reports_dir / "paper_symbol_realized_performance.csv"
    unrealized_input_path = reports_dir / "paper_symbol_unrealized_performance.csv"
    output_csv_path = reports_dir / "paper_symbol_side_by_side_performance.csv"
    output_summary_path = reports_dir / "paper_symbol_side_by_side_performance_summary.md"

    realized_rows = load_paper_symbol_realized_performance_rows(realized_input_path)
    unrealized_rows = load_paper_symbol_unrealized_performance_rows(unrealized_input_path)
    rows, summary_data, warnings = build_paper_symbol_side_by_side_performance(realized_rows, unrealized_rows)
    write_paper_symbol_side_by_side_performance(rows, output_csv_path)
    summary = summarize_paper_symbol_side_by_side_performance(
        summary_data,
        warnings,
        realized_input_path=realized_input_path,
        unrealized_input_path=unrealized_input_path,
        output_path=output_csv_path,
    )
    write_paper_symbol_side_by_side_performance_summary(
        render_paper_symbol_side_by_side_performance_summary(summary),
        output_summary_path,
    )
    return {
        "realized_input_path": realized_input_path,
        "unrealized_input_path": unrealized_input_path,
        "output_csv_path": output_csv_path,
        "output_summary_path": output_summary_path,
        "summary": summary,
    }


def main() -> int:
    result = generate_paper_symbol_side_by_side_performance()
    summary = result["summary"]
    print("Paper symbol side-by-side performance generated")
    print(f"  realized_input_path: {result['realized_input_path']}")
    print(f"  unrealized_input_path: {result['unrealized_input_path']}")
    print(f"  output_csv_path: {result['output_csv_path']}")
    print(f"  output_summary_path: {result['output_summary_path']}")
    print(f"  symbol_count: {summary['symbol_count']}")
    print(f"  total_pnl_reference: {summary['total_pnl_reference']:.2f}")
    print(f"  warnings: {len(summary['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
