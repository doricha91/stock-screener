import csv
from pathlib import Path
from uuid import uuid4

import pytest

from core.paths import FRONT_TEST_DIR, PAPER_TEST_DIR
from core.paper_execution_log import append_paper_execution_log, paper_trade_preview_to_row
from core.paper_trade_preview import PaperTradePreview


def make_preview(side: str = "BUY") -> PaperTradePreview:
    shares = 10 if side == "BUY" else -3
    price = 185.30 if side == "BUY" else 240.10
    return PaperTradePreview(
        date="2026-05-07",
        regime="BULL",
        symbol="AAPL" if side == "BUY" else "TSLA",
        side=side,
        shares=shares,
        price=price,
        gross_amount=shares * price,
        source="journal_actual_fill",
        status="READY_FOR_PAPER_TRADE",
        reason="PAPER_FILLED",
        notes="",
        rec_shares=abs(shares),
        rec_price=price,
    )


def test_paper_trade_preview_to_row_buy():
    row = paper_trade_preview_to_row(make_preview("BUY"))
    assert row["side"] == "BUY"
    assert int(row["shares"]) > 0
    assert float(row["gross_amount"]) > 0
    assert row["trade_id"]


def test_paper_trade_preview_to_row_sell():
    row = paper_trade_preview_to_row(make_preview("SELL"))
    assert row["side"] == "SELL"
    assert int(row["shares"]) < 0
    assert float(row["gross_amount"]) < 0


def _unique_log_path() -> Path:
    return PAPER_TEST_DIR / f"paper_execution_log_test_{uuid4().hex}.csv"


def test_append_dry_run_does_not_create_file():
    log_path = _unique_log_path()
    try:
        rows, warnings = append_paper_execution_log([make_preview("BUY")], log_path, commit=False)
        assert len(rows) == 1
        assert warnings == []
        assert not log_path.exists()
    finally:
        if log_path.exists():
            log_path.unlink()


def test_append_commit_creates_csv():
    log_path = _unique_log_path()
    try:
        rows, warnings = append_paper_execution_log([make_preview("BUY")], log_path, commit=True)
        assert len(rows) == 1
        assert warnings == []
        assert log_path.exists()
        with log_path.open("r", encoding="utf-8-sig", newline="") as handle:
            saved_rows = list(csv.DictReader(handle))
        assert len(saved_rows) == 1
    finally:
        if log_path.exists():
            log_path.unlink()


def test_duplicate_preview_is_not_appended_twice():
    log_path = _unique_log_path()
    try:
        preview = make_preview("BUY")
        first_rows, first_warnings = append_paper_execution_log([preview], log_path, commit=True)
        second_rows, second_warnings = append_paper_execution_log([preview], log_path, commit=True)
        assert len(first_rows) == 1
        assert first_warnings == []
        assert second_rows == []
        assert any("Skipping duplicate paper trade" in warning for warning in second_warnings)
        with log_path.open("r", encoding="utf-8-sig", newline="") as handle:
            saved_rows = list(csv.DictReader(handle))
        assert len(saved_rows) == 1
    finally:
        if log_path.exists():
            log_path.unlink()


def test_append_rejects_non_paper_path():
    log_path = FRONT_TEST_DIR / f"paper_execution_log_test_{uuid4().hex}.csv"
    with pytest.raises(ValueError):
        append_paper_execution_log([make_preview("BUY")], log_path, commit=True)
