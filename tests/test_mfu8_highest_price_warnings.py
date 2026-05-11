from core.daily_plan_generator import (
    WARNING_HIGHEST_PRICE_INCONSISTENT,
    WARNING_HIGHEST_PRICE_INVALID,
    WARNING_HIGHEST_PRICE_META_MISSING,
    WARNING_HIGHEST_PRICE_MISSING,
    WARNING_HIGHEST_PRICE_STALE,
    diagnose_highest_price_state,
    format_markdown_report,
)
import core.portfolio_state_manager as portfolio_state_manager
from core.target_portfolio_state import CurrentPortfolioState
import pandas as pd
from pathlib import Path


def make_state(highest_prices=None, highest_price_meta=None) -> CurrentPortfolioState:
    return CurrentPortfolioState(
        current_symbols=["AAPL"],
        current_cash_ratio=0.0,
        current_hedge_ratio=0.0,
        absolute_cash=1000.0,
        shares={},
        avg_price={},
        highest_prices=highest_prices or {},
        highest_price_meta=highest_price_meta or {},
        hedge_symbols=[],
    )


def extract_reasons(warnings):
    return [item["reason"] for item in warnings]


def test_missing_highest_price_warning():
    state = make_state()
    highest_price, highest_source, warnings, notes = diagnose_highest_price_state(
        "AAPL", "2026-05-07", state, close=100.0, high=105.0
    )

    assert highest_price == 100.0
    assert highest_source == "current_only"
    assert WARNING_HIGHEST_PRICE_MISSING in extract_reasons(warnings)
    assert "highest_price missing" in "; ".join(notes)


import pytest


@pytest.mark.parametrize("bad_value", [None, 0, -1, "bad"])
def test_invalid_highest_price_warning(bad_value):
    state = make_state(highest_prices={"AAPL": bad_value})
    highest_price, highest_source, warnings, _ = diagnose_highest_price_state(
        "AAPL", "2026-05-07", state, close=100.0, high=105.0
    )

    assert highest_price == 100.0
    assert highest_source == "current_only"
    assert WARNING_HIGHEST_PRICE_INVALID in extract_reasons(warnings)


def test_meta_missing_warning():
    state = make_state(highest_prices={"AAPL": 110.0})
    _, highest_source, warnings, _ = diagnose_highest_price_state(
        "AAPL", "2026-05-07", state, close=100.0, high=105.0
    )

    assert highest_source == "snapshot"
    assert WARNING_HIGHEST_PRICE_META_MISSING in extract_reasons(warnings)


def test_stale_metadata_warning():
    state = make_state(
        highest_prices={"AAPL": 110.0},
        highest_price_meta={
            "AAPL": {
                "updated_at": "2026-05-05",
                "source": "update_portfolio_state_after_close",
                "basis": "today_high",
            }
        },
    )
    _, _, warnings, _ = diagnose_highest_price_state(
        "AAPL", "2026-05-07", state, close=100.0, high=105.0
    )

    assert WARNING_HIGHEST_PRICE_STALE in extract_reasons(warnings)


def test_inconsistent_highest_warning():
    state = make_state(
        highest_prices={"AAPL": 90.0},
        highest_price_meta={
            "AAPL": {
                "updated_at": "2026-05-07",
                "source": "update_portfolio_state_after_close",
                "basis": "today_high",
            }
        },
    )
    highest_price, highest_source, warnings, _ = diagnose_highest_price_state(
        "AAPL", "2026-05-07", state, close=100.0, high=105.0
    )

    assert highest_price == 100.0
    assert highest_source == "max(snapshot,current)"
    assert WARNING_HIGHEST_PRICE_INCONSISTENT in extract_reasons(warnings)


def test_highest_price_warning_stays_out_of_journal():
    warning_reason = WARNING_HIGHEST_PRICE_STALE
    report = format_markdown_report(
        "2026-05-07",
        {"regime": "BULL", "vix_value": 20.0, "triggers": {}},
        {
            "target_cash_ratio": 0.2,
            "total_equity": 100000.0,
            "available_buying_power": 20000.0,
        },
        action_items=[],
        stop_alerts=[],
        journal_rows=[],
        holding_sell_diagnostics=[
            {
                "symbol": "AAPL",
                "close": 100.0,
                "exit_low": 95.0,
                "sell_signal": False,
                "atr": 3.5,
                "atr_source": "indicator",
                "highest_price": 110.0,
                "highest_source": "snapshot",
                "highest_meta_updated_at": "2026-05-05",
                "highest_meta_basis": "today_high",
                "highest_meta_source": "update_portfolio_state_after_close",
                "highest_warning_reasons": [warning_reason],
                "stop_price": 90.0,
                "trailing_triggered": False,
                "review_status": "-",
                "warning_status": warning_reason,
                "warning_items": [],
                "notes": "highest_meta updated_at=2026-05-05 basis=today_high; highest_price stale (2d)",
            }
        ],
        rebalance_review_items=[],
        warning_items=[
            {
                "symbol": "AAPL",
                "severity": "MEDIUM",
                "reason": warning_reason,
                "note": "stale vs data_date=2026-05-07",
            }
        ],
        candidate_diagnostics=[],
        stale_exclusions=[],
        removed_candidate_exclusions=[],
        stale_holdings_alert=[],
    )

    assert warning_reason in report
    journal_section = report[report.find("## 5.") :] if "## 5." in report else ""
    assert warning_reason not in journal_section


def test_load_current_state_without_highest_price_meta(monkeypatch):
    snapshot = Path("tests") / "_tmp_current_state_20260507.json"
    try:
        snapshot.write_text(
            """
{
    "current_symbols": ["AAPL"],
    "current_cash_ratio": 0.0,
    "current_hedge_ratio": 0.0,
    "absolute_cash": 1000.0,
    "shares": {"AAPL": 1},
    "avg_price": {"AAPL": 100.0},
    "highest_prices": {"AAPL": 110.0},
    "hedge_symbols": []
}
            """.strip(),
            encoding="utf-8",
        )
        monkeypatch.setattr(portfolio_state_manager, "_get_all_snapshots", lambda: [snapshot])

        state = portfolio_state_manager.load_current_state()

        assert state.highest_price_meta == {}
    finally:
        if snapshot.exists():
            snapshot.unlink()


def test_update_portfolio_state_after_close_updates_highest_price_meta(monkeypatch):
    initial_state = CurrentPortfolioState(
        current_symbols=[],
        current_cash_ratio=1.0,
        current_hedge_ratio=0.0,
        absolute_cash=1000.0,
        shares={},
        avg_price={},
        highest_prices={},
        highest_price_meta={},
        hedge_symbols=[],
    )
    captured = {}

    monkeypatch.setattr(portfolio_state_manager, "load_current_state", lambda date_str=None: initial_state)
    monkeypatch.setattr(
        portfolio_state_manager.data_manager,
        "get_price_data",
        lambda symbol, start_date=None: pd.DataFrame(
            [{"high": 120.0, "close": 118.0}], index=[pd.Timestamp("2026-05-07")]
        ),
    )

    def fake_save(state, date_str):
        captured["state"] = state
        captured["date_str"] = date_str
        return None
    monkeypatch.setattr(portfolio_state_manager, "save_current_state", fake_save)

    portfolio_state_manager.update_portfolio_state_after_close(
        "2026-05-07",
        [{"symbol": "AAPL", "shares": 1, "price": 100.0}],
        actual_cash=900.0,
    )

    state = captured["state"]
    assert state.highest_prices["AAPL"] == 120.0
    assert state.highest_price_meta["AAPL"] == {
        "updated_at": "2026-05-07",
        "source": "update_portfolio_state_after_close",
        "basis": "today_high",
    }


def test_update_portfolio_state_after_close_removes_highest_price_meta_on_full_sell(monkeypatch):
    initial_state = CurrentPortfolioState(
        current_symbols=["AAPL"],
        current_cash_ratio=0.0,
        current_hedge_ratio=0.0,
        absolute_cash=0.0,
        shares={"AAPL": 1},
        avg_price={"AAPL": 100.0},
        highest_prices={"AAPL": 120.0},
        highest_price_meta={
            "AAPL": {
                "updated_at": "2026-05-06",
                "source": "update_portfolio_state_after_close",
                "basis": "today_high",
            }
        },
        hedge_symbols=[],
    )
    captured = {}

    monkeypatch.setattr(portfolio_state_manager, "load_current_state", lambda date_str=None: initial_state)
    monkeypatch.setattr(
        portfolio_state_manager.data_manager,
        "get_price_data",
        lambda symbol, start_date=None: pd.DataFrame(),
    )

    def fake_save(state, date_str):
        captured["state"] = state
        return None

    monkeypatch.setattr(portfolio_state_manager, "save_current_state", fake_save)

    portfolio_state_manager.update_portfolio_state_after_close(
        "2026-05-07",
        [{"symbol": "AAPL", "shares": -1, "price": 110.0}],
        actual_cash=110.0,
    )

    state = captured["state"]
    assert "AAPL" not in state.current_symbols
    assert "AAPL" not in state.highest_prices
    assert "AAPL" not in state.highest_price_meta
