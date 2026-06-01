from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_account_paths import PaperAccountPaths  # noqa: E402
from core.paper_symbol_unrealized_performance import (  # noqa: E402
    build_paper_symbol_unrealized_performance,
    load_paper_account_snapshot_rows,
    load_paper_position_snapshot_rows,
    render_paper_symbol_unrealized_performance_summary,
    summarize_paper_symbol_unrealized_performance,
    write_paper_symbol_unrealized_performance,
    write_paper_symbol_unrealized_performance_summary,
)
from core.paths import (  # noqa: E402
    paper_account_snapshot_path,
    paper_position_snapshot_path,
    paper_reports_dir,
)


def generate_paper_symbol_unrealized_performance(account_paths: PaperAccountPaths | None = None) -> dict:
    if account_paths is not None and account_paths.account_id != "paper_default":
        position_snapshot_path = account_paths.position_snapshot_path
        account_snapshot_path = account_paths.account_snapshot_path
        reports_dir = account_paths.reports_dir
        allowed_root = account_paths.root
    else:
        position_snapshot_path = paper_position_snapshot_path()
        account_snapshot_path = paper_account_snapshot_path()
        reports_dir = paper_reports_dir()
        allowed_root = None
    output_csv_path = reports_dir / "paper_symbol_unrealized_performance.csv"
    output_summary_path = reports_dir / "paper_symbol_unrealized_performance_summary.md"

    position_rows = load_paper_position_snapshot_rows(position_snapshot_path, allowed_root=allowed_root)
    account_rows = load_paper_account_snapshot_rows(account_snapshot_path, allowed_root=allowed_root)
    rows, summary_data, warnings = build_paper_symbol_unrealized_performance(position_rows, account_rows)
    write_paper_symbol_unrealized_performance(rows, output_csv_path, allowed_root=allowed_root)
    summary = summarize_paper_symbol_unrealized_performance(
        summary_data,
        warnings,
        input_path=position_snapshot_path,
        output_path=output_csv_path,
    )
    write_paper_symbol_unrealized_performance_summary(
        render_paper_symbol_unrealized_performance_summary(summary),
        output_summary_path,
        allowed_root=allowed_root,
    )
    return {
        "position_snapshot_path": position_snapshot_path,
        "account_snapshot_path": account_snapshot_path,
        "output_csv_path": output_csv_path,
        "output_summary_path": output_summary_path,
        "summary": summary,
    }


def main() -> int:
    result = generate_paper_symbol_unrealized_performance()
    summary = result["summary"]
    print("Paper symbol unrealized performance generated")
    print(f"  position_snapshot_path: {result['position_snapshot_path']}")
    print(f"  account_snapshot_path: {result['account_snapshot_path']}")
    print(f"  output_csv_path: {result['output_csv_path']}")
    print(f"  output_summary_path: {result['output_summary_path']}")
    print(f"  latest_snapshot_date: {summary['latest_snapshot_date']}")
    print(f"  open_symbol_count: {summary['open_symbol_count']}")
    print(f"  total_unrealized_pnl: {summary['total_unrealized_pnl']:.2f}")
    print(f"  warnings: {len(summary['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
