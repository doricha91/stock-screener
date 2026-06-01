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

