from __future__ import annotations

from pathlib import Path

from core.paper_commit_guard import PaperCommitGuardPaths, check_same_date_commit_guard


def _write_csv(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_guard_allows_when_no_same_date_snapshot_exists(tmp_path):
    account_path = tmp_path / "paper_account_snapshot.csv"
    position_path = tmp_path / "paper_position_snapshot.csv"
    current_state_path = tmp_path / "paper_current_state_20260513.json"
    _write_csv(account_path, "snapshot_date,cash\n2026-05-12,1\n")
    _write_csv(position_path, "snapshot_date,symbol\n2026-05-12,AAPL\n")
    paths = PaperCommitGuardPaths(account_path, position_path, current_state_path)
    result = check_same_date_commit_guard("20260513", paths=paths)
    assert result["allowed"] is True
    assert result["existing_sources"] == []


def test_guard_blocks_when_current_state_exists(tmp_path):
    account_path = tmp_path / "paper_account_snapshot.csv"
    position_path = tmp_path / "paper_position_snapshot.csv"
    current_state_path = tmp_path / "paper_current_state_20260513.json"
    _write_csv(account_path, "snapshot_date,cash\n2026-05-12,1\n")
    _write_csv(position_path, "snapshot_date,symbol\n2026-05-12,AAPL\n")
    current_state_path.write_text("{}", encoding="utf-8")
    paths = PaperCommitGuardPaths(account_path, position_path, current_state_path)
    result = check_same_date_commit_guard("20260513", paths=paths)
    assert result["allowed"] is False
    assert current_state_path.name in result["existing_sources"]


def test_guard_blocks_when_account_snapshot_has_same_date(tmp_path):
    account_path = tmp_path / "paper_account_snapshot.csv"
    position_path = tmp_path / "paper_position_snapshot.csv"
    current_state_path = tmp_path / "paper_current_state_20260513.json"
    _write_csv(account_path, "snapshot_date,cash\n2026-05-13,1\n")
    _write_csv(position_path, "snapshot_date,symbol\n2026-05-12,AAPL\n")
    paths = PaperCommitGuardPaths(account_path, position_path, current_state_path)
    result = check_same_date_commit_guard("20260513", paths=paths)
    assert result["allowed"] is False
    assert "paper_account_snapshot.csv" in result["existing_sources"]


def test_guard_blocks_when_position_snapshot_has_same_date(tmp_path):
    account_path = tmp_path / "paper_account_snapshot.csv"
    position_path = tmp_path / "paper_position_snapshot.csv"
    current_state_path = tmp_path / "paper_current_state_20260513.json"
    _write_csv(account_path, "snapshot_date,cash\n2026-05-12,1\n")
    _write_csv(position_path, "snapshot_date,symbol\n2026-05-13,AAPL\n")
    paths = PaperCommitGuardPaths(account_path, position_path, current_state_path)
    result = check_same_date_commit_guard("20260513", paths=paths)
    assert result["allowed"] is False
    assert "paper_position_snapshot.csv" in result["existing_sources"]


def test_guard_treats_missing_csv_as_absent(tmp_path):
    paths = PaperCommitGuardPaths(
        tmp_path / "missing_account.csv",
        tmp_path / "missing_position.csv",
        tmp_path / "paper_current_state_20260513.json",
    )
    result = check_same_date_commit_guard("20260513", paths=paths)
    assert result["allowed"] is True
    assert result["existing_sources"] == []


def test_guard_returns_error_on_csv_parse_failure(tmp_path):
    account_path = tmp_path / "paper_account_snapshot.csv"
    position_path = tmp_path / "paper_position_snapshot.csv"
    current_state_path = tmp_path / "paper_current_state_20260513.json"
    _write_csv(account_path, "cash\n1\n")
    _write_csv(position_path, "snapshot_date,symbol\n2026-05-12,AAPL\n")
    paths = PaperCommitGuardPaths(account_path, position_path, current_state_path)
    result = check_same_date_commit_guard("20260513", paths=paths)
    assert result["allowed"] is False
    assert "snapshot_date column missing" in result["error"]
