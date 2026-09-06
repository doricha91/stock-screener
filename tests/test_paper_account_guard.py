from __future__ import annotations

from pathlib import Path

import pytest

from core import paper_account_guard


def _paths(account_id: str, root: str, *, legacy_default_used: bool):
    return type(
        "Paths",
        (),
        {
            "account_id": account_id,
            "root": Path(root),
            "legacy_default_used": legacy_default_used,
        },
    )()


def test_guard_rejects_omitted_direct_write_account():
    with pytest.raises(ValueError, match="account_id is required for a direct write"):
        paper_account_guard.guard_paper_writer_account(command_name="paper.py commit")


def test_guard_allows_paper_default(monkeypatch):
    monkeypatch.setattr(
        paper_account_guard,
        "build_paper_account_paths",
        lambda account_id=None, allow_legacy_default=False, create=False: _paths(
            "paper_default",
            "outputs/paper_accounts/paper_default",
            legacy_default_used=False,
        ),
    )

    context = paper_account_guard.guard_paper_writer_account(
        account_id="paper_default",
        command_name="paper.py plan",
    )

    assert context["write_allowed"] is True
    assert context["legacy_default_used"] is False
    assert "allowing paper.py plan" in context["message"]


def test_guard_blocks_legacy_default_writer(monkeypatch):
    monkeypatch.setattr(
        paper_account_guard,
        "build_paper_account_paths",
        lambda account_id=None, allow_legacy_default=False, create=False: _paths(
            "paper_default",
            "outputs/paper_test",
            legacy_default_used=True,
        ),
    )

    context = paper_account_guard.guard_paper_writer_account(
        account_id="paper_default",
        command_name="paper.py plan",
    )

    assert context["write_allowed"] is False
    assert "read-only" in context["message"]


def test_guard_rejects_invalid_account_id():
    with pytest.raises(ValueError):
        paper_account_guard.guard_paper_writer_account(
            account_id="Paper Default",
            command_name="paper.py commit",
        )


def test_guard_blocks_non_default_by_default(monkeypatch):
    monkeypatch.setattr(
        paper_account_guard,
        "build_paper_account_paths",
        lambda account_id=None, allow_legacy_default=False, create=False: _paths(
            "paper_growth",
            "outputs/paper_accounts/paper_growth",
            legacy_default_used=False,
        ),
    )

    context = paper_account_guard.guard_paper_writer_account(
        account_id="paper_growth",
        command_name="paper.py review-append",
    )

    assert context["write_allowed"] is False
    assert "non-default account_id=paper_growth" in context["message"]


def test_guard_allows_explicit_non_default_when_command_opts_in(monkeypatch):
    monkeypatch.setattr(
        paper_account_guard,
        "build_paper_account_paths",
        lambda account_id=None, allow_legacy_default=False, create=False: _paths(
            "paper_growth",
            "outputs/paper_accounts/paper_growth",
            legacy_default_used=False,
        ),
    )

    context = paper_account_guard.guard_paper_writer_account(
        account_id="paper_growth",
        command_name="paper.py review-append",
        allow_non_default=True,
    )

    assert context["write_allowed"] is True


def test_guard_context_includes_account_fields(monkeypatch):
    monkeypatch.setattr(
        paper_account_guard,
        "build_paper_account_paths",
        lambda account_id=None, allow_legacy_default=False, create=False: _paths(
            "paper_default",
            "outputs/paper_accounts/paper_default",
            legacy_default_used=False,
        ),
    )

    context = paper_account_guard.resolve_writer_account_context("paper_default")

    assert context["account_id"] == "paper_default"
    assert Path(context["account_root"]) == Path("outputs/paper_accounts/paper_default")
    assert context["legacy_default_used"] is False


def test_format_writer_account_guard_message_returns_message(monkeypatch):
    monkeypatch.setattr(
        paper_account_guard,
        "build_paper_account_paths",
        lambda account_id=None, allow_legacy_default=False, create=False: _paths(
            "paper_default",
            "outputs/paper_accounts/paper_default",
            legacy_default_used=False,
        ),
    )
    context = paper_account_guard.guard_paper_writer_account(
        account_id="paper_default",
        command_name="paper.py eod",
    )

    assert paper_account_guard.format_writer_account_guard_message(context) == context["message"]


def test_path_containment_accepts_child_and_rejects_sibling(tmp_path: Path):
    root = tmp_path / "paper_accounts" / "paper_growth"
    child = root / "reports" / "report.json"

    assert paper_account_guard.assert_path_under_account_root(child, root) == child.resolve()
    with pytest.raises(ValueError, match="under account root"):
        paper_account_guard.assert_path_under_account_root(tmp_path / "paper_test" / "report.json", root)


def test_non_default_writer_rejects_legacy_paper_test_target(tmp_path: Path, monkeypatch):
    legacy_root = tmp_path / "paper_test"
    monkeypatch.setattr(paper_account_guard, "PAPER_TEST_DIR", legacy_root)

    with pytest.raises(ValueError, match="legacy paper_test root"):
        paper_account_guard.assert_non_default_writer_target(
            legacy_root / "paper_execution_log.csv",
            account_id="paper_growth",
            account_root=legacy_root,
        )
