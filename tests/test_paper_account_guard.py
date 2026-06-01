from __future__ import annotations

from pathlib import Path

import pytest

from core import paper_account_guard


def test_guard_defaults_to_paper_default(monkeypatch):
    monkeypatch.setattr(
        paper_account_guard,
        "build_paper_account_paths",
        lambda account_id=None, create=False: type(
            "Paths",
            (),
            {
                "account_id": "paper_default",
                "root": Path("outputs/paper_test"),
                "legacy_default_used": True,
            },
        )(),
    )

    context = paper_account_guard.guard_paper_writer_account(command_name="paper.py commit")

    assert context["account_id"] == "paper_default"
    assert context["write_allowed"] is True
    assert context["legacy_default_used"] is True


def test_guard_allows_paper_default(monkeypatch):
    monkeypatch.setattr(
        paper_account_guard,
        "build_paper_account_paths",
        lambda account_id=None, create=False: type(
            "Paths",
            (),
            {
                "account_id": "paper_default",
                "root": Path("outputs/paper_test"),
                "legacy_default_used": True,
            },
        )(),
    )

    context = paper_account_guard.guard_paper_writer_account(
        account_id="paper_default",
        command_name="paper.py plan",
    )

    assert context["write_allowed"] is True
    assert "allowing paper.py plan" in context["message"]


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
        lambda account_id=None, create=False: type(
            "Paths",
            (),
            {
                "account_id": "paper_growth",
                "root": Path("outputs/paper_accounts/paper_growth"),
                "legacy_default_used": False,
            },
        )(),
    )

    context = paper_account_guard.guard_paper_writer_account(
        account_id="paper_growth",
        command_name="paper.py review-append",
    )

    assert context["write_allowed"] is False
    assert "non-default account_id=paper_growth" in context["message"]


def test_guard_context_includes_account_fields(monkeypatch):
    monkeypatch.setattr(
        paper_account_guard,
        "build_paper_account_paths",
        lambda account_id=None, create=False: type(
            "Paths",
            (),
            {
                "account_id": "paper_default",
                "root": Path("outputs/paper_test"),
                "legacy_default_used": True,
            },
        )(),
    )

    context = paper_account_guard.resolve_writer_account_context("paper_default")

    assert context["account_id"] == "paper_default"
    assert Path(context["account_root"]) == Path("outputs/paper_test")
    assert context["legacy_default_used"] is True


def test_format_writer_account_guard_message_returns_message(monkeypatch):
    monkeypatch.setattr(
        paper_account_guard,
        "build_paper_account_paths",
        lambda account_id=None, create=False: type(
            "Paths",
            (),
            {
                "account_id": "paper_default",
                "root": Path("outputs/paper_test"),
                "legacy_default_used": True,
            },
        )(),
    )
    context = paper_account_guard.guard_paper_writer_account(
        account_id="paper_default",
        command_name="paper.py eod",
    )

    assert paper_account_guard.format_writer_account_guard_message(context) == context["message"]
