from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_realized_ranking_report import (  # noqa: E402
    build_paper_realized_rankings,
    load_paper_symbol_realized_performance_rows,
    render_paper_realized_ranking_report,
    summarize_paper_realized_ranking_report,
    write_paper_realized_ranking_csv,
    write_paper_realized_ranking_report,
)
from core.paths import paper_reports_dir  # noqa: E402


def generate_paper_realized_ranking_report() -> dict:
    reports_dir = paper_reports_dir()
    input_path = reports_dir / "paper_symbol_realized_performance.csv"
    output_markdown_path = reports_dir / "paper_realized_ranking_report.md"
    output_csv_path = reports_dir / "paper_realized_ranking.csv"

    performance_rows = load_paper_symbol_realized_performance_rows(input_path)
    rankings, ranking_csv_rows, warnings, overall = build_paper_realized_rankings(performance_rows)
    write_paper_realized_ranking_csv(ranking_csv_rows, output_csv_path)

    summary = summarize_paper_realized_ranking_report(
        rankings,
        warnings,
        overall,
        input_path=input_path,
        output_csv_path=output_csv_path,
        output_markdown_path=output_markdown_path,
    )
    write_paper_realized_ranking_report(
        render_paper_realized_ranking_report(summary),
        output_markdown_path,
    )
    return {
        "input_path": input_path,
        "output_csv_path": output_csv_path,
        "output_markdown_path": output_markdown_path,
        "summary": summary,
        "ranking_csv_rows": ranking_csv_rows,
    }


def main() -> int:
    result = generate_paper_realized_ranking_report()
    summary = result["summary"]
    print("Paper realized ranking report generated")
    print(f"  input_path: {result['input_path']}")
    print(f"  output_csv_path: {result['output_csv_path']}")
    print(f"  output_markdown_path: {result['output_markdown_path']}")
    print(f"  symbol_count: {summary['symbol_count']}")
    print(f"  total_realized_trade_count: {summary['total_realized_trade_count']}")
    print(f"  total_realized_pnl: {summary['total_realized_pnl']:.2f}")
    print(f"  warnings: {len(summary['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
