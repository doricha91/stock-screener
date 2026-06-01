from __future__ import annotations

import json

import pytest

from core.paper_account_bootstrap import PaperAccountBootstrapError
from scripts import paper


def test_init_account_cli_dry_run_json(monkeypatch, capsys):
    captured: dict[str, object] = {}

    def fake_initialize_paper_account(**kwargs):
        captured.update(kwargs)
        return {
            "account_id": "paper_growth",
            "account_root": "D:/tmp/paper_accounts/paper_growth",
            "snapshot_date": "2026-06-01",
            "initial_cash": 100000.0,
            "currency": "USD",
            "dry_run": True,
            "allow_existing": False,
            "blocked_reason": None,
            "existing_root": False,
            "existing_core_files": [],
            "would_create_dirs": ["D:/tmp/paper_accounts/paper_growth"],
            "would_create_files": ["D:/tmp/paper_accounts/paper_growth/paper_account_snapshot.csv"],
            "created": False,
        }

    monkeypatch.setattr(paper, "initialize_paper_account", fake_initialize_paper_account)
    exit_code = paper.main(
        [
            "init-account",
            "--account-id",
            "paper_growth",
            "--initial-cash",
            "100000",
            "--currency",
            "USD",
            "--date",
            "20260601",
            "--dry-run",
            "--json",
        ]
    )
    assert exit_code == 0
    assert captured["confirm_create"] is False
    payload = json.loads(capsys.readouterr().out)
    assert payload["account_id"] == "paper_growth"
    assert payload["dry_run"] is True


def test_init_account_cli_confirm_create(monkeypatch):
    captured: dict[str, object] = {}

    def fake_initialize_paper_account(**kwargs):
        captured.update(kwargs)
        return {
            "account_id": "paper_growth",
            "account_root": "D:/tmp/paper_accounts/paper_growth",
            "snapshot_date": "2026-06-01",
            "initial_cash": 100000.0,
            "currency": "USD",
            "dry_run": False,
            "allow_existing": False,
            "blocked_reason": None,
            "existing_root": False,
            "existing_core_files": [],
            "would_create_dirs": [],
            "would_create_files": [],
            "created": True,
        }

    monkeypatch.setattr(paper, "initialize_paper_account", fake_initialize_paper_account)
    exit_code = paper.main(
        [
            "init-account",
            "--account-id",
            "paper_growth",
            "--initial-cash",
            "100000",
            "--currency",
            "USD",
            "--date",
            "20260601",
            "--confirm-create",
        ]
    )
    assert exit_code == 0
    assert captured["confirm_create"] is True


def test_init_account_cli_rejects_both_dry_run_and_confirm_create():
    with pytest.raises(PaperAccountBootstrapError):
        paper.main(
            [
                "init-account",
                "--account-id",
                "paper_growth",
                "--initial-cash",
                "100000",
                "--currency",
                "USD",
                "--date",
                "20260601",
                "--dry-run",
                "--confirm-create",
            ]
        )
