from __future__ import annotations

from pathlib import Path

import pytest

from core.paper_account_paths import PaperAccountPaths
from scripts import paper


def _account_paths(account_id: str, root: Path, *, legacy_default_used: bool = False) -> PaperAccountPaths:
    return PaperAccountPaths(
        account_id=account_id,
        root=root,
        legacy_default_used=legacy_default_used,
        execution_log_path=root / "paper_execution_log.csv",
        account_snapshot_path=root / "paper_account_snapshot.csv",
        position_snapshot_path=root / "paper_position_snapshot.csv",
        reports_dir=root / "reports",
        reviews_dir=root / "reviews",
        config_snapshots_dir=root / "config_snapshots",
        config_snapshot_archive_dir=root / "archive" / "config_snapshots",
        replay_diff_dir=root / "replay_diff",
        replay_diff_config_snapshot_archive_dir=root / "replay_diff" / "archive" / "config_snapshots",
    )


def test_status_uses_account_paths_and_defaults_to_paper_default(monkeypatch):
    captured: dict[str, object] = {}
    paths = _account_paths("paper_default", Path("outputs/paper_test"), legacy_default_used=True)

    def fake_build_paper_account_paths(account_id=None, *, create: bool = False):
        captured["account_id"] = account_id
        captured["create"] = create
        return paths

    def fake_run_paper_status(date_str=None, *, account_paths=None, paper_root=None):
        captured["status_account_id"] = account_paths.account_id
        captured["paper_root"] = paper_root
        return {
            "account_id": account_paths.account_id,
            "account_root": str(account_paths.root),
            "legacy_default_used": account_paths.legacy_default_used,
            "date": "2026-05-20",
            "workflow_status": "COMMITTED",
            "latest_account_snapshot_date": "2026-05-20",
            "latest_current_state_date": "2026-05-20",
            "daily_action_plan_exists": True,
            "current_state_exists": True,
            "account_snapshot_exists": True,
            "position_snapshot_exists": True,
            "same_date_snapshot_exists": True,
            "execution_log_rows_for_date": 0,
            "reports_exists": True,
            "review_template_exists": True,
            "review_validation_exists": True,
            "review_validation_result": "PASS",
            "next_recommended_command": "paper.py review",
            "errors": [],
        }

    monkeypatch.setattr(paper, "build_paper_account_paths", fake_build_paper_account_paths)
    monkeypatch.setattr(paper, "run_paper_status", fake_run_paper_status)

    exit_code = paper.main(["status", "--json"])
    assert exit_code == 0
    assert captured["account_id"] is None
    assert captured["create"] is False
    assert captured["status_account_id"] == "paper_default"
    assert captured["paper_root"] is None


def test_status_invalid_account_id_raises():
    with pytest.raises(ValueError):
        paper.main(["status", "--account-id", "Paper Default"])


def test_weekly_status_passes_account_paths(monkeypatch):
    captured: dict[str, object] = {}
    root = Path("outputs/paper_accounts/paper_growth")
    paths = _account_paths("paper_growth", root)

    monkeypatch.setattr(paper, "build_paper_account_paths", lambda account_id=None, *, create=False: paths)
    monkeypatch.setattr(Path, "exists", lambda self: True if self == root else Path.__dict__["exists"](self))

    def fake_generate_paper_weekly_status(*, days, start, end, account_paths=None, paper_root=None):
        captured["days"] = days
        captured["account_id"] = account_paths.account_id
        captured["paper_root"] = paper_root
        return {
            "markdown_path": root / "reports" / "paper_weekly_status_summary.md",
            "json_path": root / "reports" / "paper_weekly_status_summary.json",
            "summary": {
                "account_id": account_paths.account_id,
                "account_root": str(account_paths.root),
                "legacy_default_used": False,
                "schema_version": "paper_weekly_status.v1",
                "period": {"actual_start": "2026-05-15", "actual_end": "2026-05-20", "snapshot_count": 2, "coverage_status": "FULL"},
                "overall_status": "PASS",
            },
        }

    monkeypatch.setattr(paper, "generate_paper_weekly_status", fake_generate_paper_weekly_status)
    exit_code = paper.main(["weekly-status", "--account-id", "paper_growth", "--days", "2"])
    assert exit_code == 0
    assert captured == {"days": 2, "account_id": "paper_growth", "paper_root": None}


def test_benchmark_passes_account_paths(monkeypatch):
    captured: dict[str, object] = {}
    root = Path("outputs/paper_accounts/paper_growth")
    paths = _account_paths("paper_growth", root)

    monkeypatch.setattr(paper, "build_paper_account_paths", lambda account_id=None, *, create=False: paths)
    monkeypatch.setattr(Path, "exists", lambda self: True if self == root else Path.__dict__["exists"](self))

    def fake_generate_paper_benchmark_comparison(*, account_paths=None, paper_root=None, market_db=None):
        captured["account_id"] = account_paths.account_id
        captured["paper_root"] = paper_root
        return {
            "markdown_path": root / "reports" / "paper_benchmark_comparison.md",
            "json_path": root / "reports" / "paper_benchmark_comparison.json",
            "summary": {
                "account_id": account_paths.account_id,
                "account_root": str(account_paths.root),
                "legacy_default_used": False,
                "schema_version": "paper_benchmark_comparison.v1",
                "run_mode": "exploratory",
                "official_run": False,
                "latest_snapshot_date": "2026-05-20",
                "availability_status": "AVAILABLE",
            },
        }

    monkeypatch.setattr(paper, "generate_paper_benchmark_comparison", fake_generate_paper_benchmark_comparison)
    exit_code = paper.main(["benchmark", "--account-id", "paper_growth"])
    assert exit_code == 0
    assert captured == {"account_id": "paper_growth", "paper_root": None}


def test_missing_non_default_root_returns_no_data_without_creation(monkeypatch, capsys):
    root = Path("outputs/paper_accounts/paper_growth")
    paths = _account_paths("paper_growth", root)
    monkeypatch.setattr(paper, "build_paper_account_paths", lambda account_id=None, *, create=False: paths)
    monkeypatch.setattr(Path, "exists", lambda self: False if self == root else Path.__dict__["exists"](self))

    exit_code = paper.main(["benchmark", "--account-id", "paper_growth", "--json"])
    output = capsys.readouterr().out
    assert exit_code == 1
    assert '"availability_status": "NO_DATA"' in output
