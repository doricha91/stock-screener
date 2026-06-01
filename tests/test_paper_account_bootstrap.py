from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from core.paper_account_bootstrap import (
    PaperAccountBootstrapError,
    build_account_bootstrap_plan,
    initialize_paper_account,
)
from core.paper_status import run_paper_status


def test_bootstrap_dry_run_does_not_create_files(tmp_path: Path):
    summary = initialize_paper_account(
        account_id="paper_growth",
        initial_cash=100000,
        currency="USD",
        date_str="20260601",
        confirm_create=False,
        account_root=tmp_path / "outputs" / "paper_accounts" / "paper_growth",
    )
    assert summary["dry_run"] is True
    assert summary["created"] is False
    assert not Path(summary["account_root"]).exists()


def test_bootstrap_confirm_create_writes_required_structure(tmp_path: Path):
    root = tmp_path / "outputs" / "paper_accounts" / "paper_growth"
    summary = initialize_paper_account(
        account_id="paper_growth",
        initial_cash=100000,
        currency="USD",
        date_str="20260601",
        confirm_create=True,
        account_root=root,
    )
    assert summary["created"] is True
    assert root.exists()
    assert (root / "reports").exists()
    assert (root / "reviews").exists()
    assert (root / "archive").exists()
    assert (root / "config_snapshots").exists()
    assert (root / "replay_diff").exists()
    assert (root / "paper_account_snapshot.csv").exists()
    assert (root / "paper_position_snapshot.csv").exists()
    assert (root / "paper_execution_log.csv").exists()
    assert (root / "paper_current_state_20260601.json").exists()


def test_bootstrap_snapshot_contains_initial_cash_and_snapshot_date(tmp_path: Path):
    root = tmp_path / "outputs" / "paper_accounts" / "paper_growth"
    initialize_paper_account(
        account_id="paper_growth",
        initial_cash=123456,
        currency="USD",
        date_str="2026-06-01",
        confirm_create=True,
        account_root=root,
    )
    with (root / "paper_account_snapshot.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    row = rows[0]
    assert row["snapshot_date"] == "2026-06-01"
    assert row["initial_cash"] == "123456.00"
    assert row["cash"] == "123456.00"


def test_bootstrap_execution_log_is_header_only(tmp_path: Path):
    root = tmp_path / "outputs" / "paper_accounts" / "paper_growth"
    initialize_paper_account(
        account_id="paper_growth",
        initial_cash=100000,
        currency="USD",
        date_str="20260601",
        confirm_create=True,
        account_root=root,
    )
    lines = (root / "paper_execution_log.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 1
    assert "trade_id" in lines[0]


def test_bootstrap_position_snapshot_is_header_only(tmp_path: Path):
    root = tmp_path / "outputs" / "paper_accounts" / "paper_growth"
    initialize_paper_account(
        account_id="paper_growth",
        initial_cash=100000,
        currency="USD",
        date_str="20260601",
        confirm_create=True,
        account_root=root,
    )
    lines = (root / "paper_position_snapshot.csv").read_text(encoding="utf-8-sig").splitlines()
    assert len(lines) == 1
    assert "snapshot_date" in lines[0]


def test_bootstrap_current_state_json_is_created(tmp_path: Path):
    root = tmp_path / "outputs" / "paper_accounts" / "paper_growth"
    initialize_paper_account(
        account_id="paper_growth",
        initial_cash=100000,
        currency="USD",
        date_str="20260601",
        confirm_create=True,
        account_root=root,
    )
    payload = json.loads((root / "paper_current_state_20260601.json").read_text(encoding="utf-8"))
    assert payload["account_id"] == "paper_growth"
    assert payload["snapshot_date"] == "2026-06-01"
    assert payload["absolute_cash"] == 100000.0
    assert payload["current_symbols"] == []


def test_paper_default_bootstrap_is_rejected(tmp_path: Path):
    with pytest.raises(PaperAccountBootstrapError):
        initialize_paper_account(
            account_id="paper_default",
            initial_cash=100000,
            currency="USD",
            date_str="20260601",
            confirm_create=False,
            account_root=tmp_path / "outputs" / "paper_accounts" / "paper_default",
        )


def test_invalid_account_id_fails(tmp_path: Path):
    with pytest.raises(ValueError):
        initialize_paper_account(
            account_id="Paper Default",
            initial_cash=100000,
            currency="USD",
            date_str="20260601",
            confirm_create=False,
            account_root=tmp_path / "outputs" / "paper_accounts" / "paper_growth",
        )


def test_reinitialize_existing_account_fails(tmp_path: Path):
    root = tmp_path / "outputs" / "paper_accounts" / "paper_growth"
    initialize_paper_account(
        account_id="paper_growth",
        initial_cash=100000,
        currency="USD",
        date_str="20260601",
        confirm_create=True,
        account_root=root,
    )
    with pytest.raises(PaperAccountBootstrapError):
        initialize_paper_account(
            account_id="paper_growth",
            initial_cash=100000,
            currency="USD",
            date_str="20260601",
            confirm_create=True,
            account_root=root,
        )


def test_existing_root_without_core_files_is_blocked_by_default(tmp_path: Path):
    root = tmp_path / "outputs" / "paper_accounts" / "paper_growth"
    root.mkdir(parents=True)
    plan = build_account_bootstrap_plan(
        account_id="paper_growth",
        initial_cash=100000,
        currency="USD",
        date_str="20260601",
        dry_run=True,
        account_root=root,
    )
    assert plan.blocked_reason is not None


def test_bootstrap_status_is_resolved_and_not_unknown(tmp_path: Path):
    root = tmp_path / "outputs" / "paper_accounts" / "paper_growth"
    initialize_paper_account(
        account_id="paper_growth",
        initial_cash=100000,
        currency="USD",
        date_str="20260601",
        confirm_create=True,
        account_root=root,
    )
    status = run_paper_status("20260601", paper_root=root)
    assert status["workflow_status"] == "NO_PLAN"
