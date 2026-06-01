from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_account_paths import PaperAccountPaths  # noqa: E402
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


def generate_paper_performance_summary(account_paths: PaperAccountPaths | None = None) -> dict:
    allowed_root = None
    if account_paths is not None and account_paths.account_id != "paper_default":
        account_snapshot_path = account_paths.account_snapshot_path
        position_snapshot_path = account_paths.position_snapshot_path
        reports_dir = account_paths.reports_dir
        output_path = reports_dir / "paper_performance_summary.md"
        allowed_root = account_paths.root
    else:
        account_snapshot_path = paper_account_snapshot_path()
        position_snapshot_path = paper_position_snapshot_path()
        reports_dir = paper_reports_dir()
        output_path = paper_performance_summary_path()
    equity_curve_path = reports_dir / "paper_equity_curve.csv"
    drawdown_path = reports_dir / "paper_drawdown.csv"

    summary = build_paper_performance_summary(
        load_paper_equity_curve(equity_curve_path, allowed_root=allowed_root),
        load_paper_drawdown(drawdown_path, allowed_root=allowed_root),
        load_paper_account_snapshots(account_snapshot_path, allowed_root=allowed_root),
        *load_latest_position_snapshot_rows(position_snapshot_path, allowed_root=allowed_root),
    )
    markdown = render_paper_performance_summary_markdown(summary)
    write_paper_performance_summary(markdown, output_path, allowed_root=allowed_root)
    return {
        "equity_curve_path": equity_curve_path,
        "drawdown_path": drawdown_path,
        "account_snapshot_path": account_snapshot_path,
        "position_snapshot_path": position_snapshot_path,
        "output_path": output_path,
        "summary": summary,
    }


def main() -> int:
    result = generate_paper_performance_summary()
    summary = result["summary"]

    print("Paper performance summary generated")
    print(f"  equity_curve_path: {result['equity_curve_path']}")
    print(f"  drawdown_path: {result['drawdown_path']}")
    print(f"  account_snapshot_path: {result['account_snapshot_path']}")
    print(f"  position_snapshot_path: {result['position_snapshot_path']}")
    print(f"  output_path: {result['output_path']}")
    print(f"  latest_snapshot_date: {summary['latest_snapshot_date']}")
    print(f"  valuation_status: {summary['account_latest'].get('market_valuation_status', '') or 'N/A'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
