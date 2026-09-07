from __future__ import annotations

from pathlib import Path

import pytest

from core import paper_account_paths as account_paths_module
from core.paper_account_guard import require_initialized_output_account_paths
from core.paper_account_paths import (
    LEGACY_PAPER_DEFAULT_ROOT,
    build_paper_account_paths,
    resolve_paper_read_account_paths,
)
from core.paper_state_provider import load_paper_execution_rows_for_state
from scripts import paper


def test_omitted_read_uses_configured_default_canonical_root(monkeypatch, tmp_path: Path):
    canonical_root = tmp_path / "paper_accounts"
    monkeypatch.setattr(account_paths_module, "PAPER_ACCOUNTS_ROOT", canonical_root)

    resolved = resolve_paper_read_account_paths()

    assert resolved.account_id == "paper_default"
    assert resolved.root == canonical_root / "paper_default"
    assert resolved.legacy_default_used is False


def test_explicit_read_uses_requested_canonical_root(monkeypatch, tmp_path: Path):
    canonical_root = tmp_path / "paper_accounts"
    monkeypatch.setattr(account_paths_module, "PAPER_ACCOUNTS_ROOT", canonical_root)

    resolved = resolve_paper_read_account_paths("paper_growth")

    assert resolved.root == canonical_root / "paper_growth"
    assert resolved.legacy_default_used is False


def test_legacy_read_is_explicit_and_paper_default_only(monkeypatch, tmp_path: Path):
    legacy_root = tmp_path / "paper_test"
    monkeypatch.setattr(account_paths_module, "LEGACY_PAPER_DEFAULT_ROOT", legacy_root)

    resolved = resolve_paper_read_account_paths("paper_default", legacy_read=True)

    assert resolved.root == legacy_root
    assert resolved.legacy_default_used is True
    with pytest.raises(ValueError, match="paper_default"):
        resolve_paper_read_account_paths("paper_growth", legacy_read=True)


def test_output_requires_initialized_explicit_account_paths(tmp_path: Path):
    paths = build_paper_account_paths("paper_growth", account_root=tmp_path / "paper_growth")

    with pytest.raises(ValueError, match="initialized account root"):
        require_initialized_output_account_paths(paths, command_name="test-output")
    assert not paths.root.exists()


def test_state_reader_rejects_cross_account_log_path(tmp_path: Path):
    expected = build_paper_account_paths("paper_growth", account_root=tmp_path / "paper_growth")
    other_log = tmp_path / "paper_value" / "paper_execution_log.csv"

    with pytest.raises(ValueError, match="outside the resolved account root"):
        load_paper_execution_rows_for_state(other_log, account_paths=expected)


def test_output_cli_rejects_omitted_account():
    with pytest.raises(SystemExit) as exc_info:
        paper.main(["weekly-status"])
    assert exc_info.value.code == 2


def test_legacy_read_cannot_be_combined_with_output_command():
    with pytest.raises(SystemExit) as exc_info:
        paper.main(["weekly-status", "--account-id", "paper_default", "--legacy-read"])
    assert exc_info.value.code == 2
