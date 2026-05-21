from __future__ import annotations

import json
from pathlib import Path

from core.paper_status import (
    WORKFLOW_COMMITTED,
    WORKFLOW_NO_PLAN,
    WORKFLOW_PLAN_READY,
    WORKFLOW_REVIEW_READY,
    format_paper_status,
    paper_status_to_json,
    run_paper_status,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_root(tmp_path: Path) -> Path:
    root = tmp_path / "paper_test"
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reviews").mkdir(parents=True, exist_ok=True)
    return root


def test_no_plan_when_daily_action_plan_missing(tmp_path):
    root = _build_root(tmp_path)
    status = run_paper_status("20260520", paper_root=root)
    assert status["workflow_status"] == WORKFLOW_NO_PLAN


def test_plan_ready_when_plan_exists_without_commit_snapshots(tmp_path):
    root = _build_root(tmp_path)
    _write(root / "daily_action_plan_20260520.md", "# plan\n")
    status = run_paper_status("20260520", paper_root=root)
    assert status["workflow_status"] == WORKFLOW_PLAN_READY


def test_committed_when_current_state_account_and_position_exist(tmp_path):
    root = _build_root(tmp_path)
    _write(root / "daily_action_plan_20260520.md", "# plan\n")
    _write(root / "paper_current_state_20260520.json", "{}\n")
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,cash,total_equity_market_value,unrealized_pnl,position_count,symbols\n"
        "2026-05-20,100,200,3,2,AAPL|MSFT\n",
    )
    _write(
        root / "paper_position_snapshot.csv",
        "snapshot_date,symbol\n2026-05-20,AAPL\n2026-05-20,MSFT\n",
    )
    status = run_paper_status("20260520", paper_root=root)
    assert status["workflow_status"] == WORKFLOW_COMMITTED


def test_review_ready_when_reports_template_and_validation_pass_exist(tmp_path):
    root = _build_root(tmp_path)
    _write(root / "daily_action_plan_20260520.md", "# plan\n")
    _write(root / "paper_current_state_20260520.json", "{}\n")
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,cash,total_equity_market_value,unrealized_pnl,position_count,symbols\n"
        "2026-05-20,100,200,3,2,AAPL|MSFT\n",
    )
    _write(
        root / "paper_position_snapshot.csv",
        "snapshot_date,symbol\n2026-05-20,AAPL\n",
    )
    _write(root / "reports" / "paper_daily_review_summary.md", "# summary\n")
    _write(root / "reports" / "paper_performance_summary.md", "# perf\n")
    _write(root / "reviews" / "paper_manual_review_log_template.csv", "review_date,symbol\n2026-05-21,AAPL\n")
    _write(
        root / "reviews" / "paper_manual_review_log_validation_report.md",
        "# Paper Manual Review Log Validation Report\n\n- Validation result: PASS\n",
    )
    status = run_paper_status("20260520", paper_root=root)
    assert status["workflow_status"] == WORKFLOW_REVIEW_READY


def test_execution_log_zero_rows_for_date_is_not_error(tmp_path):
    root = _build_root(tmp_path)
    _write(root / "daily_action_plan_20260520.md", "# plan\n")
    _write(
        root / "paper_execution_log.csv",
        "date,symbol\n2026-05-19,AAPL\n",
    )
    status = run_paper_status("20260520", paper_root=root)
    assert status["execution_log_rows_for_date"] == 0
    assert status["errors"] == []


def test_reads_latest_account_snapshot_date(tmp_path):
    root = _build_root(tmp_path)
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,cash,total_equity_market_value,unrealized_pnl,position_count,symbols\n"
        "2026-05-19,100,200,3,2,AAPL|MSFT\n"
        "2026-05-20,110,210,4,3,AAPL|MSFT|NVDA\n",
    )
    status = run_paper_status(paper_root=root)
    assert status["latest_account_snapshot_date"] == "2026-05-20"
    assert status["date"] == "2026-05-20"


def test_same_date_snapshot_exists_flag(tmp_path):
    root = _build_root(tmp_path)
    _write(root / "paper_current_state_20260520.json", "{}\n")
    status = run_paper_status("20260520", paper_root=root)
    assert status["same_date_snapshot_exists"] is True


def test_json_output_is_valid_json(tmp_path):
    root = _build_root(tmp_path)
    _write(root / "daily_action_plan_20260520.md", "# plan\n")
    status = run_paper_status("20260520", paper_root=root)
    payload = json.loads(paper_status_to_json(status))
    assert payload["date"] == "2026-05-20"


def test_format_status_contains_next_command(tmp_path):
    root = _build_root(tmp_path)
    _write(root / "daily_action_plan_20260520.md", "# plan\n")
    status = run_paper_status("20260520", paper_root=root)
    text = format_paper_status(status)
    assert "next_recommended_command" in text
