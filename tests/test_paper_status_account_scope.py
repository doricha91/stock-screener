from __future__ import annotations

from pathlib import Path

from core.paper_account_paths import build_paper_account_paths
from core.paper_status import run_paper_status


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
