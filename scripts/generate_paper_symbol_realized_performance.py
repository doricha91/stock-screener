from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_symbol_realized_performance import (  # noqa: E402
    build_paper_symbol_realized_performance,
    load_paper_realized_trade_journal_rows,
    render_paper_symbol_realized_performance_summary,
    summarize_paper_symbol_realized_performance,
    write_paper_symbol_realized_performance,
    write_paper_symbol_realized_performance_summary,
)
from core.paths import paper_reports_dir  # noqa: E402


def generate_paper_symbol_realized_performance() -> dict:
    reports_dir = paper_reports_dir()
    input_path = reports_dir / "paper_realized_trade_journal.csv"
    output_csv_path = reports_dir / "paper_symbol_realized_performance.csv"
    output_summary_path = reports_dir / "paper_symbol_realized_performance_summary.md"

    journal_rows = load_paper_realized_trade_journal_rows(input_path)
    performance_rows, warnings = build_paper_symbol_realized_performance(journal_rows)
    write_paper_symbol_realized_performance(performance_rows, output_csv_path)

    summary = summarize_paper_symbol_realized_performance(
        performance_rows,
        input_path=input_path,
        output_path=output_csv_path,
        warnings=warnings,
    )
    write_paper_symbol_realized_performance_summary(
        render_paper_symbol_realized_performance_summary(summary),
        output_summary_path,
    )
    return {
        "input_path": input_path,
        "output_csv_path": output_csv_path,
        "output_summary_path": output_summary_path,
        "summary": summary,
    }


def main() -> int:
    result = generate_paper_symbol_realized_performance()
    summary = result["summary"]
    print("Paper symbol realized performance generated")
    print(f"  input_path: {result['input_path']}")
    print(f"  output_csv_path: {result['output_csv_path']}")
    print(f"  output_summary_path: {result['output_summary_path']}")
    print(f"  symbol_count: {summary['symbol_count']}")
    print(f"  total_realized_trade_count: {summary['total_realized_trade_count']}")
    print(f"  total_realized_pnl: {summary['total_realized_pnl']:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
