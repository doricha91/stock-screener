from __future__ import annotations

from pathlib import Path

from core.paper_account_paths import build_paper_account_paths
from core.paper_status import (
    WORKFLOW_COMMITTED,
    WORKFLOW_REVIEW_DONE,
    WORKFLOW_REVIEW_PARTIAL,
    WORKFLOW_REVIEW_READY,
    run_paper_status,
)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_root(tmp_path: Path) -> Path:
    root = tmp_path / "outputs" / "paper_accounts" / "paper_smoke"
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reviews").mkdir(parents=True, exist_ok=True)
    return root


def _seed_committed_review_root(root: Path) -> None:
    _write(root / "daily_action_plan_20260520.md", "# plan\n")
    _write(root / "paper_current_state_20260520.json", "{}\n")
    _write(
        root / "paper_account_snapshot.csv",
        "snapshot_date,cash,total_equity_market_value,unrealized_pnl,position_count,symbols\n"
        "2026-05-20,99815.98,100000.00,0.00,1,AMT\n",
    )
    _write(
        root / "paper_position_snapshot.csv",
        "snapshot_date,symbol\n2026-05-20,AMT\n",
    )
    _write(root / "reports" / "paper_daily_review_summary.md", "# summary\n")
    _write(root / "reports" / "paper_performance_summary.md", "# perf\n")


def test_validation_fail_does_not_transition_to_review_partial_or_done(tmp_path):
    root = _build_root(tmp_path)
    _seed_committed_review_root(root)
    _write(
        root / "reviews" / "paper_manual_review_log_template.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-05-31,AMT,Q1,filled,reviewed\n"
        "2026-05-31,AMT,Q2,,pending\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-05-31,AMT,Q1,filled,reviewed\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log_validation_report.md",
        "# Paper Manual Review Log Validation Report\n\n- Validation result: FAIL\n",
    )
    status = run_paper_status("20260520", paper_root=root)
    assert status["workflow_status"] == WORKFLOW_COMMITTED
    assert status["review_progress_status"] == "PARTIAL"


def test_review_log_without_template_does_not_misclassify_as_done(tmp_path):
    root = _build_root(tmp_path)
    _seed_committed_review_root(root)
    _write(
        root / "reviews" / "paper_manual_review_log.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-05-31,AMT,Q1,filled,reviewed\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log_validation_report.md",
        "# Paper Manual Review Log Validation Report\n\n- Validation result: PASS\n",
    )
    status = run_paper_status("20260520", paper_root=root)
    assert status["workflow_status"] == WORKFLOW_COMMITTED
    assert status["review_progress_status"] == "NOT_APPLICABLE"


def test_non_default_account_paths_partial_review_matches_4c_shape(tmp_path, monkeypatch):
    legacy_root = tmp_path / "outputs" / "paper_test"
    accounts_root = tmp_path / "outputs" / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", accounts_root)

    root = accounts_root / "paper_smoke"
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reviews").mkdir(parents=True, exist_ok=True)
    _seed_committed_review_root(root)
    _write(
        root / "reviews" / "paper_manual_review_log_template.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-05-31,AMT,neutral_1,paper_sandbox rehearsal review,reviewed\n"
        "2026-05-31,AMT,neutral_2,,pending\n"
        "2026-05-31,AMT,neutral_3,,pending\n"
        "2026-05-31,AMT,neutral_4,,pending\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-05-31,AMT,neutral_1,paper_sandbox rehearsal review,reviewed\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log_validation_report.md",
        "# Paper Manual Review Log Validation Report\n\n- Validation result: PASS\n",
    )
    account_paths = build_paper_account_paths("paper_smoke", create=False)
    status = run_paper_status("20260520", account_paths=account_paths)
    assert status["workflow_status"] == WORKFLOW_REVIEW_PARTIAL
    assert status["review_answered_row_count"] == 1
    assert status["review_pending_row_count"] == 3
    assert status["review_completion_ratio"] == 0.25


def test_non_default_account_paths_done_review(tmp_path, monkeypatch):
    legacy_root = tmp_path / "outputs" / "paper_test"
    accounts_root = tmp_path / "outputs" / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", accounts_root)

    root = accounts_root / "paper_smoke"
    (root / "reports").mkdir(parents=True, exist_ok=True)
    (root / "reviews").mkdir(parents=True, exist_ok=True)
    _seed_committed_review_root(root)
    _write(
        root / "reviews" / "paper_manual_review_log_template.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-05-31,AMT,neutral_1,a1,reviewed\n"
        "2026-05-31,AMT,neutral_2,a2,reviewed\n"
        "2026-05-31,AMT,neutral_3,a3,reviewed\n"
        "2026-05-31,AMT,neutral_4,a4,reviewed\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-05-31,AMT,neutral_1,a1,reviewed\n"
        "2026-05-31,AMT,neutral_2,a2,reviewed\n"
        "2026-05-31,AMT,neutral_3,a3,reviewed\n"
        "2026-05-31,AMT,neutral_4,a4,reviewed\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log_validation_report.md",
        "# Paper Manual Review Log Validation Report\n\n- Validation result: PASS\n",
    )
    account_paths = build_paper_account_paths("paper_smoke", create=False)
    status = run_paper_status("20260520", account_paths=account_paths)
    assert status["workflow_status"] == WORKFLOW_REVIEW_DONE
    assert status["review_progress_status"] == "DONE"
    assert status["next_recommended_command"] == "no immediate action"


def test_review_ready_still_returned_when_validation_pass_but_no_review_log(tmp_path):
    root = _build_root(tmp_path)
    _seed_committed_review_root(root)
    _write(
        root / "reviews" / "paper_manual_review_log_template.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-05-31,AMT,neutral_1,,pending\n"
        "2026-05-31,AMT,neutral_2,,pending\n",
    )
    _write(
        root / "reviews" / "paper_manual_review_log_validation_report.md",
        "# Paper Manual Review Log Validation Report\n\n- Validation result: PASS\n",
    )
    status = run_paper_status("20260520", paper_root=root)
    assert status["workflow_status"] == WORKFLOW_REVIEW_READY
