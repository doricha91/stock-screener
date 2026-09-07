from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import pytest

from core import paper_account_paths as account_paths_module
from core.paper_account_paths import build_paper_account_paths, resolve_paper_read_account_paths
from core.paper_account_state import create_initial_paper_state
from core.paper_current_state_storage import save_paper_current_state
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_replay_diff import compare_daily_plan_payloads, write_daily_plan_diff_report
from core.paper_state_provider import load_paper_execution_rows_for_state
from scripts.check_paper_report_regeneration_safety import snapshot_tree_hashes
from tests.paper_account_test_support import create_initialized_account_paths


@pytest.fixture
def isolated_accounts(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    accounts_root = tmp_path / "paper_accounts"
    legacy_root = tmp_path / "legacy_paper_test"
    monkeypatch.setattr(account_paths_module, "PAPER_ACCOUNTS_ROOT", accounts_root)
    monkeypatch.setattr(account_paths_module, "LEGACY_PAPER_DEFAULT_ROOT", legacy_root)
    monkeypatch.setattr(
        account_paths_module,
        "resolve_paper_account_profile",
        lambda account_id=None: SimpleNamespace(account_id=account_id or "paper_alpha"),
    )

    alpha = create_initialized_account_paths(accounts_root / "paper_alpha", account_id="paper_alpha")
    beta = create_initialized_account_paths(accounts_root / "paper_beta", account_id="paper_beta")
    legacy_root.mkdir()
    _write_execution_rows(legacy_root / "paper_execution_log.csv", "legacy-trade")
    _write_execution_rows(alpha.execution_log_path, "alpha-trade")
    _write_execution_rows(beta.execution_log_path, "beta-trade")
    return alpha, beta, legacy_root


def _write_execution_rows(path: Path, trade_id: str) -> None:
    row = {column: "" for column in PAPER_EXECUTION_LOG_COLUMNS}
    row.update(trade_id=trade_id, date="2026-06-01", symbol="AAA", side="BUY")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writeheader()
        writer.writerow(row)


def _plan(account_id: str) -> dict:
    return {
        "account_id": account_id,
        "plan_date": "2026-06-02",
        "items": [],
        "metadata": {"generated_at": "2026-06-02T09:00:00Z"},
        "fingerprints": {"config_hash": "config-a", "universe_hash": "universe-a"},
    }


def _report(account_id: str) -> dict:
    plan = _plan(account_id)
    return compare_daily_plan_payloads(
        account_id=account_id,
        plan_date="2026-06-02",
        baseline_plan=plan,
        regenerated_plan=plan,
    )


@pytest.mark.parametrize("selected,other", [(0, 1), (1, 0)])
def test_canonical_writer_changes_only_selected_account(
    isolated_accounts, selected: int, other: int
) -> None:
    accounts = isolated_accounts
    target = accounts[selected]
    unrelated = accounts[other]
    legacy_root = accounts[2]
    before_unrelated = snapshot_tree_hashes(unrelated.root)
    before_legacy = snapshot_tree_hashes(legacy_root)
    output_path = target.current_state_snapshot_path("2026-06-02")

    result = save_paper_current_state(
        create_initial_paper_state(),
        "2026-06-02",
        output_path,
        target.root / "archive",
        account_paths=target,
    )

    assert result["path"] == output_path
    assert output_path.is_file()
    assert output_path.resolve().is_relative_to(target.root.resolve())
    assert snapshot_tree_hashes(unrelated.root) == before_unrelated
    assert snapshot_tree_hashes(legacy_root) == before_legacy


def test_read_contexts_are_canonical_and_cross_account_source_fails_closed(isolated_accounts) -> None:
    alpha, beta, legacy_root = isolated_accounts

    assert load_paper_execution_rows_for_state(account_paths=alpha)[0]["trade_id"] == "alpha-trade"
    assert load_paper_execution_rows_for_state(account_paths=beta)[0]["trade_id"] == "beta-trade"
    assert load_paper_execution_rows_for_state()[0]["trade_id"] == "alpha-trade"
    assert resolve_paper_read_account_paths("paper_default").root != legacy_root
    with pytest.raises(ValueError, match="outside the resolved account root"):
        load_paper_execution_rows_for_state(beta.execution_log_path, account_paths=alpha)


def test_legacy_read_is_explicit_read_only_and_never_a_write_target(isolated_accounts) -> None:
    alpha, _beta, legacy_root = isolated_accounts
    before_legacy = snapshot_tree_hashes(legacy_root)
    legacy = resolve_paper_read_account_paths("paper_default", legacy_read=True)

    assert legacy.root == legacy_root
    assert load_paper_execution_rows_for_state(account_paths=legacy)[0]["trade_id"] == "legacy-trade"
    with pytest.raises(ValueError, match="paper_default"):
        resolve_paper_read_account_paths("paper_beta", legacy_read=True)
    with pytest.raises(ValueError, match="legacy"):
        save_paper_current_state(
            create_initial_paper_state(),
            "2026-06-02",
            legacy.current_state_snapshot_path("2026-06-02"),
            legacy.root / "archive",
            account_paths=legacy,
        )
    with pytest.raises(ValueError, match="not under"):
        write_daily_plan_diff_report(_report(alpha.account_id), output_dir=legacy_root)
    assert snapshot_tree_hashes(legacy_root) == before_legacy


def test_replay_output_stays_under_selected_account_and_rejects_other_root(isolated_accounts) -> None:
    alpha, beta, legacy_root = isolated_accounts
    before_beta = snapshot_tree_hashes(beta.root)
    before_legacy = snapshot_tree_hashes(legacy_root)

    paths = write_daily_plan_diff_report(_report(alpha.account_id))

    assert Path(paths["json_path"]).parent == alpha.replay_diff_dir
    assert Path(paths["markdown_path"]).parent == alpha.replay_diff_dir
    assert Path(paths["json_path"]).is_file()
    assert Path(paths["markdown_path"]).is_file()
    assert snapshot_tree_hashes(beta.root) == before_beta
    assert snapshot_tree_hashes(legacy_root) == before_legacy

    before_alpha = snapshot_tree_hashes(alpha.root)
    with pytest.raises(ValueError, match="not under"):
        write_daily_plan_diff_report(_report(alpha.account_id), output_dir=beta.replay_diff_dir)
    assert snapshot_tree_hashes(alpha.root) == before_alpha
    assert snapshot_tree_hashes(beta.root) == before_beta
    assert snapshot_tree_hashes(legacy_root) == before_legacy


@pytest.mark.parametrize("partial", [False, True])
def test_missing_or_partial_canonical_root_fails_without_repair(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, partial: bool
) -> None:
    accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr(account_paths_module, "PAPER_ACCOUNTS_ROOT", accounts_root)
    account_id = "paper_partial" if partial else "paper_missing"
    root = accounts_root / account_id
    paths = build_paper_account_paths(account_id, account_root=root, create=False)
    if partial:
        root.mkdir(parents=True)
        paths.account_snapshot_path.write_text("snapshot_date\n", encoding="utf-8")
    before = snapshot_tree_hashes(root)

    with pytest.raises(ValueError, match="initialized account root|missing bootstrap core artifacts"):
        save_paper_current_state(
            create_initial_paper_state(),
            "2026-06-02",
            paths.current_state_snapshot_path("2026-06-02"),
            root / "archive",
            account_paths=paths,
        )
    with pytest.raises(ValueError, match="initialized account root|missing bootstrap core artifacts"):
        write_daily_plan_diff_report(_report(account_id))

    assert snapshot_tree_hashes(root) == before
