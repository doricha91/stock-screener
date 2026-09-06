from __future__ import annotations

from pathlib import Path

import pytest

import core.paper_account_paths as account_paths_module
from core.paper_account_bootstrap import initialize_paper_account
from core.paper_account_guard import (
    assert_account_writer_target,
    require_initialized_writer_account_paths,
)
from core.paper_account_paths import build_paper_account_paths
from core.paper_account_state import create_initial_paper_state
from core.paper_current_state_storage import save_paper_current_state
from core.paths import PAPER_TEST_DIR
from scripts import (
    import_notion_executions,
    import_notion_reviews,
    paper,
    sync_notion_execution_status,
)
from scripts.reset_paper_execution_log import reset_paper_execution_log
from scripts.runbook_execution_reconciliation_preview import write_account_preview


def _initialized_paths(root: Path, account_id: str):
    root.mkdir(parents=True)
    account_paths = build_paper_account_paths(account_id, account_root=root, create=False)
    account_paths.account_snapshot_path.write_text("snapshot_date\n", encoding="utf-8")
    account_paths.position_snapshot_path.write_text("snapshot_date\n", encoding="utf-8")
    account_paths.execution_log_path.write_text("trade_id\n", encoding="utf-8")
    account_paths.current_state_snapshot_path("2026-09-05").write_text("{}", encoding="utf-8")
    return account_paths


@pytest.mark.parametrize("account_id", ["paper_default", "paper_growth"])
def test_explicit_initialized_account_writes_under_its_root(
    tmp_path: Path,
    monkeypatch,
    account_id: str,
):
    accounts_root = tmp_path / "paper_accounts"
    monkeypatch.setattr(account_paths_module, "PAPER_ACCOUNTS_ROOT", accounts_root)
    account_paths = _initialized_paths(accounts_root / account_id, account_id)
    assert account_paths.root == accounts_root / account_id
    output_path = account_paths.current_state_snapshot_path("2026-09-06")

    result = save_paper_current_state(
        create_initial_paper_state(),
        "2026-09-06",
        output_path,
        account_paths.root / "archive",
        account_paths=account_paths,
    )

    assert result["path"] == output_path
    assert output_path.is_file()
    assert output_path.resolve().is_relative_to(account_paths.root.resolve())


def test_direct_writer_without_account_context_fails_closed(tmp_path: Path):
    with pytest.raises(ValueError, match="requires explicit account_paths"):
        save_paper_current_state(
            create_initial_paper_state(),
            "2026-09-06",
            tmp_path / "paper_current_state_20260906.json",
            tmp_path / "archive",
        )


def test_legacy_default_root_is_read_only_for_writers():
    account_paths = build_paper_account_paths(
        "paper_default",
        account_root=PAPER_TEST_DIR,
        allow_legacy_default=True,
        create=False,
    )
    with pytest.raises(ValueError, match="cannot write to legacy"):
        require_initialized_writer_account_paths(
            account_paths,
            command_name="test writer",
        )


def test_cross_account_target_is_rejected(tmp_path: Path):
    account_a = _initialized_paths(tmp_path / "paper_a", "paper_a")
    account_b = _initialized_paths(tmp_path / "paper_b", "paper_b")
    with pytest.raises(ValueError, match="not under"):
        assert_account_writer_target(
            account_b.execution_log_path,
            account_paths=account_a,
            command_name="test writer",
        )


def test_uninitialized_writer_fails_without_creating_root(tmp_path: Path):
    root = tmp_path / "paper_missing"
    account_paths = build_paper_account_paths(
        "paper_missing",
        account_root=root,
        create=False,
    )
    with pytest.raises(ValueError, match="requires an initialized account root"):
        reset_paper_execution_log(account_paths=account_paths, commit=True)
    assert not root.exists()


def test_missing_non_default_root_points_to_init_account_without_creation(tmp_path: Path):
    root = tmp_path / "paper_missing"
    account_paths = build_paper_account_paths("paper_missing", account_root=root, create=False)

    with pytest.raises(ValueError) as exc_info:
        require_initialized_writer_account_paths(account_paths, command_name="test writer")

    message = str(exc_info.value)
    assert "init-account --account-id paper_missing --confirm-create" in message
    assert not root.exists()


def test_missing_paper_default_root_points_to_migration_without_dead_end(tmp_path: Path):
    root = tmp_path / "paper_default"
    account_paths = build_paper_account_paths("paper_default", account_root=root, create=False)

    with pytest.raises(ValueError) as exc_info:
        require_initialized_writer_account_paths(account_paths, command_name="test writer")

    message = str(exc_info.value)
    assert "migration or separately approved initialization is required" in message
    assert "init-account --account-id paper_default" not in message
    assert not root.exists()


def test_empty_account_directory_is_not_initialized(tmp_path: Path):
    root = tmp_path / "paper_empty"
    root.mkdir()
    account_paths = build_paper_account_paths("paper_empty", account_root=root, create=False)

    with pytest.raises(ValueError, match="missing bootstrap core artifacts"):
        require_initialized_writer_account_paths(account_paths, command_name="test writer")

    assert list(root.iterdir()) == []


def test_partial_bootstrap_artifacts_are_not_initialized_or_repaired(tmp_path: Path):
    root = tmp_path / "paper_partial"
    root.mkdir()
    account_paths = build_paper_account_paths("paper_partial", account_root=root, create=False)
    account_paths.account_snapshot_path.write_text("snapshot_date\n", encoding="utf-8")
    before = sorted(path.name for path in root.iterdir())

    with pytest.raises(ValueError, match="paper_position_snapshot.csv"):
        require_initialized_writer_account_paths(account_paths, command_name="test writer")

    assert sorted(path.name for path in root.iterdir()) == before


def test_frozen_account_context_can_drive_writer_preview(tmp_path: Path):
    account_paths = _initialized_paths(tmp_path / "paper_frozen", "paper_frozen")
    before = account_paths.execution_log_path.read_text(encoding="utf-8-sig")
    result = reset_paper_execution_log(account_paths=account_paths, commit=False)
    assert result["write_performed"] is False
    assert result["log_path"] == account_paths.execution_log_path
    assert account_paths.execution_log_path.read_text(encoding="utf-8-sig") == before


def test_runbook_writer_uses_frozen_account_root(tmp_path: Path):
    root = tmp_path / "paper_frozen"
    _initialized_paths(root, "paper_frozen")
    result = write_account_preview(
        "paper_frozen",
        "2026-09-08",
        {
            "schema_version": "execution_reconciliation_preview.v2",
            "runner_result": "PASS",
            "account_id": "paper_frozen",
            "rows": [],
        },
        account_root=root,
    )
    assert result["json"].resolve().is_relative_to(root.resolve())
    assert result["md"].resolve().is_relative_to(root.resolve())


def test_sync_report_stays_in_selected_account_namespace(tmp_path: Path, monkeypatch):
    account_paths = _initialized_paths(tmp_path / "paper_sync", "paper_sync")
    monkeypatch.setattr(
        sync_notion_execution_status,
        "build_paper_account_paths",
        lambda account_id, create=False: account_paths,
    )
    payload = {"account_id": "paper_sync", "execution_date": "2026-09-08"}
    json_path, markdown_path = sync_notion_execution_status.write_status_sync_report(
        payload,
        "paper_sync",
        "2026-09-08",
    )
    assert json_path.parent == account_paths.reports_dir
    assert markdown_path.parent == account_paths.reports_dir
    assert json_path.is_file() and markdown_path.is_file()


def test_init_account_remains_the_root_creation_owner(tmp_path: Path):
    root = tmp_path / "paper_bootstrap"
    result = initialize_paper_account(
        account_id="paper_bootstrap",
        initial_cash=100000,
        currency="USD",
        date_str="2026-09-06",
        confirm_create=True,
        account_root=root,
    )
    assert result["created"] is True
    assert root.is_dir()
    assert (root / "paper_execution_log.csv").is_file()
    account_paths = build_paper_account_paths("paper_bootstrap", account_root=root, create=False)
    assert require_initialized_writer_account_paths(
        account_paths,
        command_name="test writer",
    ) is account_paths


@pytest.mark.parametrize(
    "builder,argv",
    [
        (paper.build_parser, ["eod", "--date", "2026-09-06", "--dry-run"]),
        (import_notion_executions.build_parser, ["--date", "2026-09-06", "--preview"]),
        (import_notion_reviews.build_parser, ["--date", "2026-09-06", "--preview"]),
    ],
)
def test_writer_cli_requires_account_id(builder, argv):
    with pytest.raises(SystemExit) as exc_info:
        builder().parse_args(argv)
    assert exc_info.value.code == 2
