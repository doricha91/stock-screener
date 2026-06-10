from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.paper_daily_ops_orchestrator import build_daily_ops_status


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload, indent=2))


def _stage(payload: dict, name: str) -> dict:
    return next(stage for stage in payload["stages"] if stage["stage_name"] == name)


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "paper_accounts" / "paper_ops"
    (root / "reports").mkdir(parents=True)
    (root / "reviews").mkdir()
    (root / "config_snapshots").mkdir()
    return root


def _base_kwargs(root: Path) -> dict:
    return {
        "account_id": "paper_ops",
        "data_date": "2026-06-08",
        "trade_date": "2026-06-09",
        "account_root": root,
    }


def _write_plan_20260609(root: Path) -> None:
    _write(root / "daily_action_plan_20260609.md", "# plan 2026-06-09\n")
    _write_json(
        root / "daily_action_plan_20260609.json",
        {
            "account_id": "paper_ops",
            "data_date": "2026-06-08",
            "trade_date": "2026-06-09",
            "plan_date": "2026-06-09",
        },
    )
    _write_json(root / "config_snapshots" / "paper_config_snapshot_20260609.json", {"ok": True})


def _write_stale_review_artifacts_20260608(root: Path) -> None:
    # reports/paper_daily_review_summary.md
    _write(
        root / "reports" / "paper_daily_review_summary.md",
        "# Daily Review Summary\n\nLatest snapshot date: 2026-06-08\n",
    )
    # reports/paper_performance_summary.md
    _write(
        root / "reports" / "paper_performance_summary.md",
        "# Performance Summary\n\nLatest Snapshot Date: 2026-06-08\n",
    )
    # reviews/paper_manual_review_log_template.csv
    _write(
        root / "reviews" / "paper_manual_review_log_template.csv",
        "review_date,symbol,question_id,manual_answer,review_status\n"
        "2026-06-08,AAPL,Q1,,pending\n",
    )
    # reviews/paper_manual_review_log_validation_report.md
    _write(
        root / "reviews" / "paper_manual_review_log_validation_report.md",
        "# Validation Report\n\n- Validation result: PASS\n",
    )


import shutil

def test_stale_review_artifacts_should_not_mark_daily_review_done():
    tmp_path = Path("_tmp_test_orchestrator_guard")
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True)
    try:
        root = _root(tmp_path)
        _write_plan_20260609(root)
        _write_stale_review_artifacts_20260608(root)

        payload = build_daily_ops_status(**_base_kwargs(root))

        daily_review = _stage(payload, "DAILY_REVIEW")
        
        # Current behavior: this passes because it only checks existence and PASS in validation report.
        # Expected behavior: this should be READY or BLOCKED because artifacts are for 2026-06-08.
        assert daily_review["status"] != "DONE", f"DAILY_REVIEW should not be DONE with stale artifacts. Status: {daily_review['status']}"
        
        # MANUAL_REVIEW_TEMPLATE should also not be current_step
        assert payload["operator_summary"]["current_step"] != "MANUAL_REVIEW_TEMPLATE"
        # Should be DAILY_PLAN_NOTION_EXPORT
        assert payload["operator_summary"]["current_step"] == "DAILY_PLAN_NOTION_EXPORT"
    finally:
        shutil.rmtree(tmp_path)


def test_mixed_dates_in_review_template_should_not_be_done():
    tmp_path = Path("_tmp_test_orchestrator_guard_mixed")
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True)
    try:
        root = _root(tmp_path)
        _write_plan_20260609(root)
        _write(
            root / "reports" / "paper_daily_review_summary.md",
            "Latest snapshot date: 2026-06-09\n",
        )
        _write(
            root / "reports" / "paper_performance_summary.md",
            "Latest Snapshot Date: 2026-06-09\n",
        )
        # Mixed dates
        _write(
            root / "reviews" / "paper_manual_review_log_template.csv",
            "review_date,symbol,question_id,manual_answer,review_status\n"
            "2026-06-08,AAPL,Q1,,pending\n"
            "2026-06-09,AAPL,Q2,,pending\n",
        )
        _write(
            root / "reviews" / "paper_manual_review_log_validation_report.md",
            "Validation result: PASS\n",
        )

        payload = build_daily_ops_status(**_base_kwargs(root))
        daily_review = _stage(payload, "DAILY_REVIEW")
        assert daily_review["status"] != "DONE"
    finally:
        shutil.rmtree(tmp_path)


def test_current_review_artifacts_allow_daily_review_done():
    tmp_path = Path("_tmp_test_orchestrator_guard_current")
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True)
    try:
        root = _root(tmp_path)
        _write_plan_20260609(root)
        _write(
            root / "reports" / "paper_daily_review_summary.md",
            "Latest snapshot date: 2026-06-09\n",
        )
        _write(
            root / "reports" / "paper_performance_summary.md",
            "Latest Snapshot Date: 2026-06-09\n",
        )
        _write(
            root / "reviews" / "paper_manual_review_log_template.csv",
            "review_date,symbol,question_id,manual_answer,review_status\n"
            "2026-06-09,AAPL,Q1,,pending\n",
        )
        _write(
            root / "reviews" / "paper_manual_review_log_validation_report.md",
            "Validation result: PASS\n",
        )

        payload = build_daily_ops_status(**_base_kwargs(root))
        daily_review = _stage(payload, "DAILY_REVIEW")
        assert daily_review["status"] == "DONE"
    finally:
        shutil.rmtree(tmp_path)


def test_no_execution_candidates_skips_manual_execution_loop():
    tmp_path = Path("_tmp_test_orchestrator_guard_no_exec")
    if tmp_path.exists():
        shutil.rmtree(tmp_path)
    tmp_path.mkdir(parents=True)
    try:
        root = _root(tmp_path)
        # Write plan with items but no candidates
        _write(root / "daily_action_plan_20260609.md", "# plan 2026-06-09\n")
        _write_json(
            root / "daily_action_plan_20260609.json",
            {
                "account_id": "paper_ops",
                "data_date": "2026-06-08",
                "trade_date": "2026-06-09",
                "plan_date": "2026-06-09",
                "items": [
                    {"symbol": "AAPL", "action": "HOLD", "status": "PENDING"},
                    {"symbol": "GOOG", "action": "EXECUTE", "status": "COMPLETED", "side": "BUY"},
                    {"symbol": "MSFT", "action": "EXECUTE", "status": "PENDING", "side": "OTHER"},
                ]
            },
        )
        _write_json(root / "config_snapshots" / "paper_config_snapshot_20260609.json", {"ok": True})

        # DAILY_PLAN_NOTION_EXPORT is DONE (mocked by evidence or ignore it for this test)
        # We don't write evidence here to see if plan-based count works

        payload = build_daily_ops_status(**_base_kwargs(root))
        
        template = _stage(payload, "MANUAL_EXECUTION_TEMPLATE")
        preview = _stage(payload, "MANUAL_EXECUTION_PREVIEW")
        commit = _stage(payload, "MANUAL_EXECUTION_COMMIT")
        sync = _stage(payload, "MANUAL_EXECUTION_STATUS_SYNC")

        assert template["status"] == "DONE"
        assert template["no_execution_candidates"] is True
        assert template["execution_candidate_count"] == 0
        
        assert preview["status"] == "DONE"
        assert preview["no_execution_candidates"] is True
        
        assert commit["status"] == "DONE"
        assert commit["no_execution_candidates"] is True
        
        assert sync["status"] == "DONE"
        assert sync["no_execution_candidates"] is True

        # Should advance to DAILY_REVIEW
        assert payload["operator_summary"]["current_step"] == "DAILY_REVIEW"
        assert "paper.py review" in payload["operator_summary"]["next_command"]
        assert payload["operator_summary"]["recommended_operator_action"] == "RUN_NEXT_COMMAND"
    finally:
        shutil.rmtree(tmp_path)
