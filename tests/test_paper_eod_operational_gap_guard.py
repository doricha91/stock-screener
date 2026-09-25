from __future__ import annotations

from pathlib import Path

import pytest

from core import operational_gap_recovery
from scripts import run_paper_eod_update
from tests.test_paper_eod_accounting_close import (
    _account_paths,
    _fake_valuation,
    _seed_account,
)


def _seed_eod(tmp_path: Path):
    paths = _account_paths(
        tmp_path / "paper_accounts" / "paper_eod_ntg",
        account_id="paper_eod_ntg",
    )
    _seed_account(paths, plan_items=[], trades=[])
    return paths


def test_eod_guard_block_prevents_all_snapshot_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _seed_eod(tmp_path)
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)
    monkeypatch.setattr(
        run_paper_eod_update,
        "guard_operational_gap_boundary",
        lambda *args, **kwargs: {
            "decision": operational_gap_recovery.GUARD_BLOCKED,
            "reason": "operational_gap_authorization_invalid",
            "blockers": ["late_contradiction"],
        },
    )
    writer_calls: list[str] = []

    def unexpected_writer(*args, **kwargs):
        writer_calls.append("called")
        raise AssertionError("snapshot writer reached after EOD NTG block")

    for name in (
        "save_paper_current_state",
        "save_paper_account_snapshot",
        "save_paper_position_snapshot",
    ):
        monkeypatch.setattr(run_paper_eod_update, name, unexpected_writer)

    result = run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
        data_date="2026-06-14",
        workspace=tmp_path / "runbook_workspace",
    )

    assert result == 1
    assert writer_calls == []
    assert not paths.current_state_snapshot_path("2026-06-15").exists()


def test_eod_valid_guard_allows_existing_snapshot_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _seed_eod(tmp_path)
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)
    captured: dict[str, object] = {}

    def allow_guard(workspace, **kwargs):
        captured["workspace"] = Path(workspace)
        captured.update(kwargs)
        return {
            "decision": operational_gap_recovery.GUARD_ALLOW,
            "reason": "operational_gap_exact_target_valid",
            "blockers": [],
        }

    monkeypatch.setattr(
        run_paper_eod_update, "guard_operational_gap_boundary", allow_guard
    )
    workspace = tmp_path / "runbook_workspace"
    result = run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
        data_date="2026-06-14",
        workspace=workspace,
    )

    assert result == 0
    assert captured["workspace"] == workspace
    assert captured["account_id"] == paths.account_id
    assert captured["data_date"] == "2026-06-14"
    assert captured["trade_date"] == "2026-06-15"
    assert captured["runbook_day_id"] == "paper_eod_ntg_2026-06-14_2026-06-15"
    assert captured["account_root"] == paths.root
    assert captured["boundary"] == "EOD_SNAPSHOT_WRITE"
    assert paths.current_state_snapshot_path("2026-06-15").exists()


def test_eod_non_ntg_not_applicable_keeps_existing_behavior(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _seed_eod(tmp_path)
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)
    workspace = tmp_path / "empty_runbook_workspace"

    result = run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
        data_date="2026-06-14",
        workspace=workspace,
    )

    assert result == 0
    assert paths.current_state_snapshot_path("2026-06-15").exists()
    assert "2026-06-15" in paths.account_snapshot_path.read_text(encoding="utf-8-sig")


def test_eod_commit_without_canonical_context_fails_before_writers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paths = _seed_eod(tmp_path)
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)
    writer_calls: list[str] = []

    def unexpected_writer(*args, **kwargs):
        writer_calls.append("called")
        raise AssertionError("writer reached without canonical runbook context")

    for name in (
        "save_paper_current_state",
        "save_paper_account_snapshot",
        "save_paper_position_snapshot",
    ):
        monkeypatch.setattr(run_paper_eod_update, name, unexpected_writer)

    assert run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    ) == 1
    assert writer_calls == []
