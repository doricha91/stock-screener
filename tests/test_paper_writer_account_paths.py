from __future__ import annotations

from pathlib import Path

import pytest

from core.paper_account_guard import assert_non_default_writer_target
from core.paper_account_paths import build_paper_account_paths


def test_paper_default_legacy_root_is_preserved(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_default",
        account_root=tmp_path / "paper_test",
        allow_legacy_default=False,
        create=True,
    )
    assert account_paths.account_id == "paper_default"
    assert account_paths.root == tmp_path / "paper_test"


def test_non_default_paths_resolve_under_account_root(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_growth",
        account_root=tmp_path / "paper_accounts" / "paper_growth",
        allow_legacy_default=False,
        create=True,
    )
    assert account_paths.execution_log_path.is_relative_to(account_paths.root.resolve())
    assert account_paths.account_snapshot_path.is_relative_to(account_paths.root.resolve())
    assert account_paths.position_snapshot_path.is_relative_to(account_paths.root.resolve())
    assert account_paths.reports_dir.is_relative_to(account_paths.root.resolve())
    assert account_paths.reviews_dir.is_relative_to(account_paths.root.resolve())


def test_non_default_writer_target_rejects_legacy_paper_test_path(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_growth",
        account_root=tmp_path / "paper_accounts" / "paper_growth",
        allow_legacy_default=False,
        create=True,
    )
    legacy_target = tmp_path / "paper_test" / "paper_execution_log.csv"
    with pytest.raises(ValueError, match="account root"):
        assert_non_default_writer_target(
            legacy_target,
            account_id=account_paths.account_id,
            account_root=account_paths.root,
        )
