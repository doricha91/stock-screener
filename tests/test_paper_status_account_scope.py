from __future__ import annotations

from pathlib import Path

from core.paper_account_paths import build_paper_account_paths
from core.paper_status import run_paper_status


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_run_paper_status_includes_account_metadata_for_account_paths(tmp_path, monkeypatch):
    legacy_root = tmp_path / "paper_test"
    new_accounts_root = tmp_path / "paper_accounts"
    legacy_root.mkdir()
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", new_accounts_root)

    account_paths = build_paper_account_paths("paper_default", create=False)
    status = run_paper_status("20260520", account_paths=account_paths)
    assert status["account_id"] == "paper_default"
    assert status["account_root"] == str(legacy_root)
    assert status["legacy_default_used"] is True


def test_run_paper_status_next_command_includes_non_default_account_id(tmp_path, monkeypatch):
    new_accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", new_accounts_root)

    account_paths = build_paper_account_paths("paper_pilot_test", create=True)
    status = run_paper_status("20260605", account_paths=account_paths)

    assert status["workflow_status"] == "NO_PLAN"
    assert status["next_recommended_command"] == (
        "paper.py plan --date 20260605 --account-id paper_pilot_test"
    )


def test_non_default_review_progress_uses_account_specific_review_log(tmp_path, monkeypatch):
    legacy_root = tmp_path / "paper_test"
    accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", accounts_root)
    account_paths = build_paper_account_paths("paper_pilot_test", create=True)

    for root in (legacy_root, account_paths.root):
        _write(root / "daily_action_plan_20260605.md", "# plan\n")
        _write(root / "paper_current_state_20260605.json", "{}\n")
        _write(
            root / "paper_account_snapshot.csv",
            "snapshot_date,cash,total_equity_market_value,unrealized_pnl,position_count,symbols\n"
            "2026-06-05,100,200,0,1,MAA\n",
        )
        _write(root / "paper_position_snapshot.csv", "snapshot_date,symbol\n2026-06-05,MAA\n")
        _write(root / "reports" / "paper_daily_review_summary.md", "# summary\n")
        _write(root / "reports" / "paper_performance_summary.md", "# perf\n")
        _write(
            root / "reviews" / "paper_manual_review_log_template.csv",
            "review_date,symbol,question_id,manual_answer,review_status\n"
            "2026-06-05,MAA,Q1,,pending\n"
            "2026-06-05,MAA,Q2,,pending\n",
        )
        _write(
            root / "reviews" / "paper_manual_review_log_validation_report.md",
            "# Paper Manual Review Log Validation Report\n\n- Validation result: PASS\n",
        )

    _write(
        legacy_root / "reviews" / "paper_manual_review_log.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-06-05,MAA,Q1,default-answer-1,reviewed\n"
        "2026-06-05,MAA,Q2,default-answer-2,reviewed\n",
    )
    _write(
        account_paths.reviews_dir / "paper_manual_review_log.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-06-05,MAA,Q1,account-answer-1,reviewed\n",
    )

    status = run_paper_status("20260605", account_paths=account_paths)

    assert status["account_id"] == "paper_pilot_test"
    assert status["manual_review_log_row_count"] == 1
    assert status["review_answered_row_count"] == 1
    assert status["review_pending_row_count"] == 1
    assert status["review_progress_status"] == "PARTIAL"
