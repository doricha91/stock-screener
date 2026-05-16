from core.daily_plan_generator import (
    build_strategy_entry_action_items,
    build_switch_action_items,
    filter_switch_candidates_for_daily_plan,
    is_buy_signal_candidate,
)
from core.target_portfolio_state import CurrentPortfolioState

import pandas as pd


def _state(symbols=None, cash=70000.0, shares=None, avg_price=None):
    symbols = symbols or []
    shares = shares or {}
    avg_price = avg_price or {}
    return CurrentPortfolioState(
        current_symbols=symbols,
        current_cash_ratio=0.7,
        current_hedge_ratio=0.0,
        absolute_cash=cash,
        shares=shares,
        avg_price=avg_price,
        highest_prices=avg_price.copy(),
        highest_price_meta={},
        hedge_symbols=[],
    )


def test_is_buy_signal_candidate_requires_score_threshold_and_positive_rs():
    assert is_buy_signal_candidate({"score": 3.0, "rs_val": 0.1}, 1.5) is True
    assert is_buy_signal_candidate({"score": 3.0, "rs_val": 0.0}, 1.5) is False
    assert is_buy_signal_candidate({"score": 3.0, "rs_val": -0.1}, 1.5) is False
    assert is_buy_signal_candidate({"score": 1.0, "rs_val": 0.5}, 1.5) is False


def test_filter_switch_candidates_excludes_fail_candidates_even_with_high_score():
    candidates = pd.DataFrame(
        [
            {"symbol": "CF", "score": 3.0, "rs_val": -0.22, "close": 130.39},
            {"symbol": "BRK-B", "score": 2.0, "rs_val": -0.14, "close": 484.96},
            {"symbol": "F", "score": 6.0, "rs_val": 0.03, "close": 13.57},
        ]
    )

    filtered = filter_switch_candidates_for_daily_plan(candidates, 1.5)

    assert filtered["symbol"].tolist() == ["F"]


def test_switch_candidates_do_not_use_max_positions_or_cash_gate():
    candidates = pd.DataFrame(
        [
            {"symbol": "F", "score": 6.0, "rs_val": 0.03, "close": 13.57},
        ]
    )

    filtered = filter_switch_candidates_for_daily_plan(candidates, 1.5)

    assert filtered["symbol"].tolist() == ["F"]


def test_build_strategy_entry_action_items_skips_duplicate_switch_in_symbol():
    current_state = _state(symbols=["BRK-B", "CF", "GEN"])
    formatted_candidates = [{"symbol": "F", "price": 13.57, "score": 6.0, "rs_val": 0.03, "entry_signal": True}]
    cp_status = {"total_equity": 99667.06}

    actions = build_strategy_entry_action_items(
        rebalance_symbol_diff_added=["F"],
        current_state=current_state,
        formatted_candidates=formatted_candidates,
        cp_status=cp_status,
        target_cash_ratio=0.05,
        max_positions=10,
        planned_buy_symbols={"F"},
    )

    assert actions == []


def test_20260513_like_switch_in_and_strategy_entry_do_not_duplicate_buy():
    current_state = _state(
        symbols=["BRK-B", "CF", "GEN"],
        shares={"BRK-B": 20, "CF": 75, "GEN": 440},
        avg_price={"BRK-B": 484.96, "CF": 130.39, "GEN": 22.68},
    )
    current_prices = {"CF": 125.50}
    switch_pairs = [
        {
            "sell_symbol": "CF",
            "buy_symbol": "F",
            "buy_row": {"symbol": "F", "close": 13.57, "score": 6.0, "rs_val": 0.03},
            "score_gap": 6.0,
        }
    ]

    switch_actions, _, switch_buy_symbols = build_switch_action_items(
        switch_pairs,
        current_state,
        current_prices,
    )
    strategy_actions = build_strategy_entry_action_items(
        rebalance_symbol_diff_added=["F"],
        current_state=current_state,
        formatted_candidates=[{"symbol": "F", "price": 13.57, "score": 6.0, "rs_val": 0.03, "entry_signal": True}],
        cp_status={"total_equity": 99667.06},
        target_cash_ratio=0.05,
        max_positions=10,
        planned_buy_symbols=switch_buy_symbols,
    )

    buy_symbols = [item["symbol"] for item in switch_actions + strategy_actions if item["type"] == "BUY"]
    assert buy_symbols == ["F"]


def test_20260512_like_fail_candidates_are_not_switch_candidates():
    candidates = pd.DataFrame(
        [
            {"symbol": "CF", "score": 3.0, "rs_val": -0.220460, "close": 130.39},
            {"symbol": "BRK-B", "score": 2.0, "rs_val": -0.146362, "close": 484.96},
            {"symbol": "VRTX", "score": 2.0, "rs_val": -0.156486, "close": 500.0},
        ]
    )

    filtered = filter_switch_candidates_for_daily_plan(candidates, 1.5)

    assert filtered.empty
