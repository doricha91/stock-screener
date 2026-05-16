from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_performance_summary import (  # noqa: E402
    build_paper_performance_summary,
    load_latest_position_snapshot_rows,
    load_paper_account_snapshots,
    load_paper_drawdown,
    load_paper_equity_curve,
    render_paper_performance_summary_markdown,
    write_paper_performance_summary,
)
from core.paths import (  # noqa: E402
    paper_account_snapshot_path,
    paper_performance_summary_path,
    paper_position_snapshot_path,
    paper_reports_dir,
)


def main() -> int:
    account_snapshot_path = paper_account_snapshot_path()
    reports_dir = paper_reports_dir()
    equity_curve_path = reports_dir / "paper_equity_curve.csv"
    drawdown_path = reports_dir / "paper_drawdown.csv"
    position_snapshot_path = paper_position_snapshot_path()
    output_path = paper_performance_summary_path()

    summary = build_paper_performance_summary(
        load_paper_equity_curve(equity_curve_path),
        load_paper_drawdown(drawdown_path),
        load_paper_account_snapshots(account_snapshot_path),
        *load_latest_position_snapshot_rows(position_snapshot_path),
    )
    markdown = render_paper_performance_summary_markdown(summary)
    write_paper_performance_summary(markdown, output_path)

    print("Paper performance summary generated")
    print(f"  equity_curve_path: {equity_curve_path}")
    print(f"  drawdown_path: {drawdown_path}")
    print(f"  account_snapshot_path: {account_snapshot_path}")
    print(f"  position_snapshot_path: {position_snapshot_path}")
    print(f"  output_path: {output_path}")
    print(f"  latest_snapshot_date: {summary['latest_snapshot_date']}")
    print(f"  valuation_status: {summary['account_latest'].get('market_valuation_status', '') or 'N/A'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
