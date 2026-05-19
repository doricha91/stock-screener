from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_realized_trade_journal import (  # noqa: E402
    build_average_cost_realized_trade_journal,
    load_paper_execution_rows,
    render_realized_trade_journal_summary,
    summarize_realized_trade_journal,
    write_realized_trade_journal,
    write_realized_trade_journal_summary,
)
from core.paths import paper_execution_log_path, paper_reports_dir  # noqa: E402


def generate_paper_realized_trade_journal() -> dict:
    input_path = paper_execution_log_path()
    reports_dir = paper_reports_dir()
    output_csv_path = reports_dir / "paper_realized_trade_journal.csv"
    output_summary_path = reports_dir / "paper_realized_trade_journal_summary.md"

    trade_rows = load_paper_execution_rows(input_path)
    build_result = build_average_cost_realized_trade_journal(trade_rows)
    write_realized_trade_journal(build_result.rows, output_csv_path)

    summary = summarize_realized_trade_journal(
        build_result.rows,
        input_path=input_path,
        output_path=output_csv_path,
        duplicate_skipped_count=build_result.duplicate_skipped_count,
        warnings=build_result.warnings,
    )
    write_realized_trade_journal_summary(
        render_realized_trade_journal_summary(summary),
        output_summary_path,
    )
    return {
        "input_path": input_path,
        "output_csv_path": output_csv_path,
        "output_summary_path": output_summary_path,
        "summary": summary,
    }


def main() -> int:
    result = generate_paper_realized_trade_journal()
    summary = result["summary"]
    print("Paper realized trade journal generated")
    print(f"  input_path: {result['input_path']}")
    print(f"  output_csv_path: {result['output_csv_path']}")
    print(f"  output_summary_path: {result['output_summary_path']}")
    print(f"  row_count: {summary['total_realized_trade_count']}")
    print(f"  total_realized_pnl: {summary['total_realized_pnl']:.2f}")
    print(
        "  win_loss_flat: "
        f"{summary['win_count']}/{summary['loss_count']}/{summary['flat_count']}"
    )
    print(f"  duplicate_skipped_count: {summary['duplicate_skipped_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
