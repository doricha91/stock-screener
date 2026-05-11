import io
from types import SimpleNamespace

import pandas as pd

from core.position_sizing import calculate_entry_shares
from core.target_portfolio_state import CurrentPortfolioState
import core.daily_plan_generator as dpg


def _base_current_state() -> CurrentPortfolioState:
    return CurrentPortfolioState(
        current_symbols=[],
        current_cash_ratio=1.0,
        current_hedge_ratio=0.0,
        absolute_cash=30000.0,
        shares={},
        avg_price={},
        highest_prices={},
        hedge_symbols=[],
    )


def _patch_fronttest_buy_path(monkeypatch, captured):
    monkeypatch.setattr(dpg, "_configure_console_encoding", lambda: None)
    monkeypatch.setattr(dpg, "load_current_state", lambda: _base_current_state())
    monkeypatch.setattr(
        dpg.market_analyzer,
        "get_market_state",
        lambda target_date=None: {
            "date": "2026-05-04",
            "regime": "BULL",
            "vix_value": 20.0,
            "triggers": {},
        },
    )
    monkeypatch.setattr(dpg, "make_config", lambda *args, **kwargs: {"max_positions": 10, "score_threshold": 1.5})
    monkeypatch.setattr(
        dpg,
        "get_regime_config",
        lambda regime, base_config: {**base_config, "max_positions": 10, "score_threshold": 1.5},
    )
    monkeypatch.setattr(dpg, "load_market_index_series", lambda *args, **kwargs: pd.Series(dtype="float64"))
    monkeypatch.setattr(dpg, "load_latest_universe_snapshot", lambda: {"removed": []})
    monkeypatch.setattr(
        dpg,
        "build_screener_results",
        lambda market_state=None: pd.DataFrame(
            [{"symbol": "AAPL", "close": 200.0, "score": 3.5, "rs_val": 0.1, "date": "2026-05-04"}]
        ),
    )
    monkeypatch.setattr(
        dpg,
        "build_target_portfolio_state",
        lambda regime, formatted_candidates, merged_config: SimpleNamespace(
            target_cash_ratio=0.0,
            target_symbols=["AAPL"],
            target_long_slots=1,
        ),
    )
    monkeypatch.setattr(
        dpg,
        "evaluate_rebalance_need",
        lambda current_state, target_state, merged_config: SimpleNamespace(
            symbol_diff_added=["AAPL"],
            symbol_diff_removed=[],
            rebalance_needed=True,
            rebalance_reason=["TEST"],
        ),
    )
    monkeypatch.setattr(
        dpg,
        "get_cash_policy_status",
        lambda cash, total_equity, target_cash_ratio: {
            "total_equity": 100000.0,
            "target_cash_ratio": target_cash_ratio,
            "available_buying_power": 30000.0,
            "current_cash_ratio": 0.3,
            "required_cash_buffer": 0.0,
            "is_violating_buffer": False,
        },
    )
    monkeypatch.setattr(dpg, "calculate_available_buying_power", lambda *args, **kwargs: 30000.0)

    def fake_format_markdown_report(
        date_str,
        m_state,
        cp_status,
        action_items,
        stop_alerts,
        journal_rows,
        **kwargs,
    ):
        captured["action_items"] = action_items
        captured["journal_rows"] = journal_rows
        return "dummy report"

    monkeypatch.setattr(dpg, "format_markdown_report", fake_format_markdown_report)
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: io.StringIO())


def test_fronttest_normal_buy_rec_shares_matches_position_sizing_helper(monkeypatch):
    captured = {}
    _patch_fronttest_buy_path(monkeypatch, captured)

    report_path = dpg.generate_daily_plan("2026-05-07")

    assert report_path
    assert captured["action_items"]
    buy_action = next(item for item in captured["action_items"] if item["type"] == dpg.ACTION_BUY)

    expected = calculate_entry_shares(
        total_equity=100000.0,
        available_buying_power=30000.0,
        price=200.0,
        max_positions=10,
    )

    assert buy_action["shares"] == expected
    assert buy_action["shares"] == 50
    assert buy_action["shares"] != int(30000.0 / 200.0)

    journal_row = next(row for row in captured["journal_rows"] if row["type"] == dpg.ACTION_BUY)
    assert journal_row["rec_shares"] == expected
    assert journal_row["rec_shares"] == 50


def test_fronttest_normal_buy_path_uses_calculate_entry_shares(monkeypatch):
    captured = {}
    _patch_fronttest_buy_path(monkeypatch, captured)

    monkeypatch.setattr(dpg, "calculate_entry_shares", lambda **kwargs: 123)

    dpg.generate_daily_plan("2026-05-07")

    buy_action = next(item for item in captured["action_items"] if item["type"] == dpg.ACTION_BUY)
    journal_row = next(row for row in captured["journal_rows"] if row["type"] == dpg.ACTION_BUY)

    assert buy_action["shares"] == 123
    assert journal_row["rec_shares"] == 123
