import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_account_state import build_paper_state_from_trades
from core.paths import FRONT_TEST_DIR, PAPER_TEST_DIR
from core.portfolio_state_manager import load_current_state
from core.paper_current_state_storage import save_paper_current_state


def _unique_state_path() -> Path:
    return PAPER_TEST_DIR / f"paper_current_state_test_{uuid4().hex}.json"


def _unique_archive_dir() -> Path:
    return PAPER_TEST_DIR / f"archive_state_test_{uuid4().hex}"


def _make_trade(
    trade_id: str,
    symbol: str,
    side: str,
    shares: int,
    price: float,
) -> dict:
    return {
        "trade_id": trade_id,
        "date": "2026-05-09",
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": price,
        "gross_amount": shares * price,
    }


def _cleanup(path: Path, archive_dir: Path) -> None:
    if path.exists():
        path.unlink()
    if archive_dir.exists():
        for child in archive_dir.iterdir():
            child.unlink()
        archive_dir.rmdir()


def test_save_paper_current_state_creates_json_with_required_fields():
    output_path = _unique_state_path()
    archive_dir = _unique_archive_dir()
    try:
        state = build_paper_state_from_trades(
            [_make_trade("t1", "CPAY", "BUY", 29, 343.99)],
            initial_cash=100000.0,
            currency="USD",
        )
        result = save_paper_current_state(
            state,
            "20260509",
            output_path,
            archive_dir,
            now=datetime(2026, 5, 10, 11, 0, 0),
        )
        assert output_path.exists()
        assert result["backup_path"] is None
        data = json.loads(output_path.read_text(encoding="utf-8"))
        for field in (
            "current_symbols",
            "current_cash_ratio",
            "current_hedge_ratio",
            "absolute_cash",
            "shares",
            "avg_price",
            "highest_prices",
            "highest_price_meta",
            "hedge_symbols",
            "applied_trade_ids",
        ):
            assert field in data
        assert "positions" not in data
    finally:
        _cleanup(output_path, archive_dir)


def test_paper_current_state_marks_configured_hedge_as_excluded_symbol():
    output_path = _unique_state_path()
    archive_dir = _unique_archive_dir()
    try:
        state = build_paper_state_from_trades(
            [
                _make_trade("t1", "AAPL", "BUY", 10, 100.0),
                _make_trade("t2", "SQQQ", "BUY", 10, 20.0),
            ],
            initial_cash=100000.0,
            currency="USD",
        )
        payload = save_paper_current_state(state, "20260509", output_path, archive_dir)["payload"]
        assert payload["hedge_symbols"] == ["SQQQ"]
        assert payload["current_hedge_ratio"] > 0
    finally:
        _cleanup(output_path, archive_dir)


def test_save_paper_current_state_backs_up_existing_file_before_overwrite():
    output_path = _unique_state_path()
    archive_dir = _unique_archive_dir()
    try:
        output_path.write_text('{"old": true}', encoding="utf-8")
        state = build_paper_state_from_trades(
            [_make_trade("t1", "GEN", "BUY", 10, 20.0)],
            initial_cash=100000.0,
            currency="USD",
        )
        result = save_paper_current_state(
            state,
            "2026-05-09",
            output_path,
            archive_dir,
            now=datetime(2026, 5, 10, 11, 0, 0),
        )
        assert result["backup_path"] is not None
        assert result["backup_path"].exists()
        assert json.loads(result["backup_path"].read_text(encoding="utf-8")) == {"old": True}
        data = json.loads(output_path.read_text(encoding="utf-8"))
        assert data["current_symbols"] == ["GEN"]
    finally:
        _cleanup(output_path, archive_dir)


def test_save_paper_current_state_rejects_non_paper_path():
    output_path = FRONT_TEST_DIR / f"paper_current_state_test_{uuid4().hex}.json"
    archive_dir = _unique_archive_dir()
    try:
        state = build_paper_state_from_trades(
            [_make_trade("t1", "GEN", "BUY", 10, 20.0)],
            initial_cash=100000.0,
            currency="USD",
        )
        with pytest.raises(ValueError):
            save_paper_current_state(state, "20260509", output_path, archive_dir)
    finally:
        if archive_dir.exists():
            for child in archive_dir.iterdir():
                child.unlink()
            archive_dir.rmdir()


def test_saved_json_round_trips_through_existing_loader(monkeypatch):
    output_path = _unique_state_path()
    archive_dir = _unique_archive_dir()
    try:
        state = build_paper_state_from_trades(
            [
                _make_trade("t2", "GEN", "BUY", 440, 22.68),
                _make_trade("t1", "CPAY", "BUY", 29, 343.99),
            ],
            initial_cash=100000.0,
            currency="USD",
        )
        result = save_paper_current_state(
            state,
            "20260509",
            output_path,
            archive_dir,
            now=datetime(2026, 5, 10, 11, 0, 0),
        )
        payload = result["payload"]
        assert payload["applied_trade_ids"] == ["t1", "t2"]
        monkeypatch.setattr(
            "core.portfolio_state_manager.current_state_snapshot_path",
            lambda _date_str: output_path,
        )
        loaded_state = load_current_state("2026-05-09")
        assert loaded_state.current_symbols == ["CPAY", "GEN"]
        assert loaded_state.shares["CPAY"] == 29
        assert loaded_state.avg_price["GEN"] == 22.68
        assert loaded_state.highest_prices["CPAY"] == 343.99
    finally:
        _cleanup(output_path, archive_dir)
