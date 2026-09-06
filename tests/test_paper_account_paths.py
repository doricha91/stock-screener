from __future__ import annotations

from pathlib import Path

import pytest

from core.paper_account_profile import PaperAccountProfile
from core.paper_account_paths import build_paper_account_paths, resolve_paper_account_root


def test_none_account_id_uses_configured_default_canonical_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", accounts_root)
    monkeypatch.setattr(
        "core.paper_account_paths.resolve_paper_account_profile",
        lambda account_id: PaperAccountProfile(
            account_id="paper_growth",
            display_name="Paper Growth",
            currency="USD",
            initial_cash=100000,
            account_type="paper",
            is_default=True,
        ),
    )

    root = resolve_paper_account_root(None, create=False)

    assert root == accounts_root / "paper_growth"
    assert not root.exists()


def test_explicit_paper_default_uses_canonical_root_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    legacy_root = tmp_path / "paper_test"
    accounts_root = tmp_path / "paper_accounts"
    legacy_root.mkdir()
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", accounts_root)

    root = resolve_paper_account_root("paper_default", create=False)

    assert root == accounts_root / "paper_default"
    assert not root.exists()


def test_paper_default_uses_legacy_root_when_new_root_missing_and_legacy_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    legacy_root = tmp_path / "paper_test"
    new_accounts_root = tmp_path / "paper_accounts"
    legacy_root.mkdir()
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", new_accounts_root)

    root = resolve_paper_account_root("paper_default", allow_legacy_default=True, create=False)
    assert root == legacy_root
    assert not (new_accounts_root / "paper_default").exists()


def test_explicit_legacy_compatibility_is_reported_by_account_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    legacy_root = tmp_path / "paper_test"
    accounts_root = tmp_path / "paper_accounts"
    legacy_root.mkdir()
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", accounts_root)

    paths = build_paper_account_paths(
        "paper_default",
        allow_legacy_default=True,
        create=False,
    )

    assert paths.root == legacy_root
    assert paths.legacy_default_used is True


def test_paper_default_prefers_new_root_when_it_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    legacy_root = tmp_path / "paper_test"
    new_accounts_root = tmp_path / "paper_accounts"
    legacy_root.mkdir()
    new_root = new_accounts_root / "paper_default"
    new_root.mkdir(parents=True)
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", new_accounts_root)

    root = resolve_paper_account_root("paper_default", allow_legacy_default=True, create=False)
    assert root == new_root


def test_paper_default_returns_new_root_when_legacy_fallback_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    legacy_root = tmp_path / "paper_test"
    new_accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", new_accounts_root)

    root = resolve_paper_account_root("paper_default", allow_legacy_default=False, create=False)
    assert root == new_accounts_root / "paper_default"
    assert not root.exists()


def test_non_default_account_uses_paper_accounts_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    new_accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", new_accounts_root)

    root = resolve_paper_account_root("paper_growth", create=False)
    assert root == new_accounts_root / "paper_growth"


def test_invalid_account_id_fails():
    with pytest.raises(ValueError):
        resolve_paper_account_root("Paper Default", create=False)


def test_create_false_does_not_create_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    new_accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", new_accounts_root)

    root = resolve_paper_account_root("paper_growth", create=False)
    assert root == new_accounts_root / "paper_growth"
    assert not root.exists()


def test_create_true_temporary_compatibility_creates_canonical_subdirectories_pending_acct_01b(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    new_accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", new_accounts_root)

    paths = build_paper_account_paths("paper_growth", create=True)
    assert paths.root.exists()
    assert paths.reports_dir.exists()
    assert paths.reviews_dir.exists()
    assert paths.config_snapshots_dir.exists()
    assert paths.config_snapshot_archive_dir.exists()
    assert paths.replay_diff_dir.exists()
    assert paths.replay_diff_config_snapshot_archive_dir.exists()


def test_create_true_rejects_explicit_legacy_compatibility(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    legacy_root = tmp_path / "paper_test"
    accounts_root = tmp_path / "paper_accounts"
    legacy_root.mkdir()
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", accounts_root)

    with pytest.raises(ValueError, match="read-only"):
        build_paper_account_paths(
            "paper_default",
            allow_legacy_default=True,
            create=True,
        )


def test_explicit_legacy_account_root_requires_compatibility_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    legacy_root = tmp_path / "paper_test"
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)

    with pytest.raises(ValueError, match="explicit allow_legacy_default=True"):
        build_paper_account_paths(
            "paper_default",
            account_root=legacy_root,
            create=False,
        )


def test_explicit_legacy_account_root_is_read_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    legacy_root = tmp_path / "paper_test"
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)

    paths = build_paper_account_paths(
        "paper_default",
        account_root=legacy_root,
        allow_legacy_default=True,
        create=False,
    )
    assert paths.root == legacy_root
    assert paths.legacy_default_used is True

    with pytest.raises(ValueError, match="read-only"):
        build_paper_account_paths(
            "paper_default",
            account_root=legacy_root,
            allow_legacy_default=True,
            create=True,
        )


def test_non_default_account_cannot_use_legacy_account_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    legacy_root = tmp_path / "paper_test"
    monkeypatch.setattr("core.paper_account_paths.LEGACY_PAPER_DEFAULT_ROOT", legacy_root)

    with pytest.raises(ValueError, match="only available for paper_default"):
        build_paper_account_paths(
            "paper_growth",
            account_root=legacy_root,
            allow_legacy_default=True,
            create=False,
        )


@pytest.mark.parametrize("date_str,expected", [("20260530", "20260530"), ("2026-05-30", "20260530")])
def test_date_based_paths_support_multiple_date_formats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    date_str: str,
    expected: str,
):
    new_accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", new_accounts_root)

    paths = build_paper_account_paths("paper_growth", create=False)
    assert paths.current_state_snapshot_path(date_str).name == f"paper_current_state_{expected}.json"
    assert paths.daily_action_plan_path(date_str).name == f"daily_action_plan_{expected}.md"
    assert paths.config_snapshot_path(date_str).name == f"paper_config_snapshot_{expected}.json"
    assert paths.regenerated_daily_action_plan_path(date_str).name == f"regenerated_daily_action_plan_{expected}.md"
    assert paths.daily_plan_diff_report_path(date_str).name == f"daily_plan_diff_{expected}.md"
    assert paths.replay_diff_config_snapshot_path(date_str).name == f"regenerated_paper_config_snapshot_{expected}.json"


def test_account_directories_are_under_account_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    new_accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr("core.paper_account_paths.PAPER_ACCOUNTS_ROOT", new_accounts_root)

    paths = build_paper_account_paths("paper_growth", create=False)
    assert paths.reports_dir.parent == paths.root
    assert paths.reviews_dir.parent == paths.root
    assert paths.config_snapshots_dir.parent == paths.root
    assert paths.replay_diff_dir.parent == paths.root
