import csv
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paths import FRONT_TEST_DIR, PAPER_TEST_DIR
from scripts.reset_paper_execution_log import reset_paper_execution_log


def _unique_log_path() -> Path:
    return PAPER_TEST_DIR / f"paper_execution_log_reset_test_{uuid4().hex}.csv"


def _unique_archive_dir() -> Path:
    return PAPER_TEST_DIR / f"archive_reset_test_{uuid4().hex}"


def _write_log(log_path: Path, rows: list[dict]) -> None:
    with log_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _read_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8-sig").splitlines()


def _sample_row() -> dict:
    return {
        "trade_id": "t1",
        "date": "2026-05-07",
        "regime": "BULL",
        "symbol": "AAPL",
        "side": "BUY",
        "shares": 10,
        "price": 100.0,
        "gross_amount": 1000.0,
        "source": "journal_actual_fill",
        "status": "READY_FOR_PAPER_TRADE",
        "reason": "PAPER_FILLED",
        "notes": "",
        "rec_shares": 10,
        "rec_price": 100.0,
        "created_at": "2026-05-09T10:50:00",
    }


def test_reset_dry_run_does_not_modify_file():
    log_path = _unique_log_path()
    archive_dir = _unique_archive_dir()
    try:
        _write_log(log_path, [_sample_row()])
        before = _read_lines(log_path)
        result = reset_paper_execution_log(
            log_path=log_path,
            archive_dir=archive_dir,
            commit=False,
            now=datetime(2026, 5, 9, 10, 50, 0),
        )
        after = _read_lines(log_path)
        assert before == after
        assert result["write_performed"] is False
        assert not result["backup_target"].exists()
    finally:
        if log_path.exists():
            log_path.unlink()
        if archive_dir.exists():
            for child in archive_dir.iterdir():
                child.unlink()
            archive_dir.rmdir()


def test_reset_commit_backs_up_existing_log_and_recreates_header_only():
    log_path = _unique_log_path()
    archive_dir = _unique_archive_dir()
    try:
        _write_log(log_path, [_sample_row()])
        result = reset_paper_execution_log(
            log_path=log_path,
            archive_dir=archive_dir,
            commit=True,
            now=datetime(2026, 5, 9, 10, 50, 0),
        )
        assert result["backup_created"] is True
        assert result["backup_target"].exists()
        backup_lines = _read_lines(result["backup_target"])
        assert len(backup_lines) == 2
        new_lines = _read_lines(log_path)
        assert len(new_lines) == 1
        assert new_lines[0] == ",".join(PAPER_EXECUTION_LOG_COLUMNS)
    finally:
        if log_path.exists():
            log_path.unlink()
        if archive_dir.exists():
            for child in archive_dir.iterdir():
                child.unlink()
            archive_dir.rmdir()


def test_reset_commit_creates_header_only_log_when_missing():
    log_path = _unique_log_path()
    archive_dir = _unique_archive_dir()
    try:
        result = reset_paper_execution_log(
            log_path=log_path,
            archive_dir=archive_dir,
            commit=True,
            now=datetime(2026, 5, 9, 10, 50, 0),
        )
        assert result["backup_created"] is False
        assert log_path.exists()
        lines = _read_lines(log_path)
        assert len(lines) == 1
        assert lines[0] == ",".join(PAPER_EXECUTION_LOG_COLUMNS)
    finally:
        if log_path.exists():
            log_path.unlink()
        if archive_dir.exists():
            for child in archive_dir.iterdir():
                child.unlink()
            archive_dir.rmdir()


def test_reset_rejects_non_paper_path():
    log_path = FRONT_TEST_DIR / f"paper_execution_log_reset_test_{uuid4().hex}.csv"
    archive_dir = _unique_archive_dir()
    try:
        with pytest.raises(ValueError):
            reset_paper_execution_log(log_path=log_path, archive_dir=archive_dir, commit=True)
    finally:
        if archive_dir.exists():
            for child in archive_dir.iterdir():
                child.unlink()
            archive_dir.rmdir()
