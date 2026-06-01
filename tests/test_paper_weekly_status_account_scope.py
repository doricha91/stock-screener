from __future__ import annotations

from pathlib import Path

from core.paper_account_paths import build_paper_account_paths
from core.paper_weekly_status import generate_paper_weekly_status


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_weekly_status_accepts_account_paths_and_writes_under_account_root(tmp_path, monkeypatch):
    accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", accounts_root)
    root = accounts_root / "paper_growth"
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reviews").mkdir(parents=True, exist_ok=True)
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,cash,total_equity_market_value,cash_ratio_market_value,unrealized_pnl,position_count,total_equity_cost_basis\n"
        "2026-05-15,140,1040,0.14,25,3,1040\n"
        "2026-05-16,150,1050,0.15,30,3,1050\n",
    )
    _write(root / "paper_position_snapshot.csv", "snapshot_date,symbol\n2026-05-15,AAPL\n2026-05-16,AAPL\n")
    _write(root / "paper_execution_log.csv", "date,symbol,side\n2026-05-15,AAPL,BUY\n")
    _write(root / "daily_action_plan_20260515.md", "# plan\n")
    _write(root / "daily_action_plan_20260516.md", "# plan\n")
    _write(root / "paper_current_state_20260515.json", "{}\n")
    _write(root / "paper_current_state_20260516.json", "{}\n")
    _write(root / "reports" / "paper_daily_review_summary.md", "# summary\n")
    _write(root / "reports" / "paper_performance_summary.md", "# perf\n")
    _write(root / "reviews" / "paper_manual_review_log_template.csv", "review_date,symbol,review_status\n2026-05-16,AAPL,pending\n")
    _write(root / "reviews" / "paper_manual_review_log_validation_report.md", "# report\n\n- Validation result: PASS\n")
    _write(root / "reviews" / "paper_manual_review_log.csv", "review_date,symbol,review_status\n2026-05-16,AAPL,reviewed\n")

    account_paths = build_paper_account_paths("paper_growth", create=False)
    result = generate_paper_weekly_status(days=2, account_paths=account_paths)
    assert result["markdown_path"].parent == root / "reports"
    assert result["summary"]["account_id"] == "paper_growth"
    assert result["summary"]["account_root"] == str(root)

