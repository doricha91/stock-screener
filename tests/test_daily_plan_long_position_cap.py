import math

import pytest

from core.daily_plan_generator import (
    ACTION_BUY,
    ACTION_SELL,
    WARNING_LONG_POSITION_RECOVERY_SCORE_UNAVAILABLE,
    WARNING_LONG_POSITION_RECOVERY_UNEXPECTED_ACTION,
    apply_daily_plan_long_position_cap,
    select_strategy_entry_symbols_with_long_cap,
    validate_final_daily_plan_long_position_actions,
)
from core.target_portfolio_state import CurrentPortfolioState
from core.config_factory import make_config
from core.param_grid import params_grid


def _state(symbols, hedge_symbols=None):
    shares = {symbol: 10 for symbol in symbols}
    return CurrentPortfolioState(
        current_symbols=list(symbols),
        current_cash_ratio=0.2,
        current_hedge_ratio=0.0,
        absolute_cash=20000.0,
        shares=shares,
        avg_price={symbol: 100.0 for symbol in symbols},
        highest_prices={symbol: 100.0 for symbol in symbols},
        hedge_symbols=hedge_symbols or [],
    )


def _scores(symbols, score_by_symbol=None, rs_by_symbol=None):
    score_by_symbol = score_by_symbol or {}
    rs_by_symbol = rs_by_symbol or {}
    rows = []
    for symbol in symbols:
        score = score_by_symbol.get(symbol, 10.0)
        try:
            valid = score is not None and math.isfinite(float(score))
        except (TypeError, ValueError):
            valid = False
        rows.append({"symbol": symbol, "score": score, "rs_val": rs_by_symbol.get(symbol, 0.0), "valid": valid})
    return rows


def test_strategy_buy_candidates_are_trimmed_in_existing_rank_order():
    candidates = [
        {"symbol": "C", "score": 3.0, "rs_val": 0.1},
        {"symbol": "A", "score": 4.0, "rs_val": 0.1},
        {"symbol": "B", "score": 4.0, "rs_val": 0.2},
        {"symbol": "D", "score": 2.0, "rs_val": 1.0},
    ]
    assert select_strategy_entry_symbols_with_long_cap(["A", "B", "C", "D"], candidates, 2) == ["B", "A"]


def test_existing_full_sell_frees_slot_but_partial_sell_does_not():
    state = _state([f"L{i}" for i in range(10)])
    full_actions, full_slots, _, _ = apply_daily_plan_long_position_cap(
        state, [{"type": ACTION_SELL, "symbol": "L0", "shares": 10}], _scores(state.current_symbols), 10, {}
    )
    partial_actions, partial_slots, _, _ = apply_daily_plan_long_position_cap(
        state, [{"type": ACTION_SELL, "symbol": "L0", "shares": 1}], _scores(state.current_symbols), 10, {}
    )
    assert full_actions and full_slots == 1
    assert partial_actions and partial_slots == 0


def test_over_cap_blocks_buy_even_when_existing_full_sells_reduce_projection_below_cap():
    symbols = [f"L{i}" for i in range(11)]
    state = _state(symbols)
    actions, slots, warnings, over_cap = apply_daily_plan_long_position_cap(
        state,
        [
            {"type": ACTION_SELL, "symbol": "L0", "shares": 10, "reason": "EXISTING_EXIT"},
            {"type": ACTION_SELL, "symbol": "L1", "shares": 10, "reason": "EXISTING_EXIT"},
            {"type": ACTION_BUY, "symbol": "TOP_UP", "shares": 1},
        ],
        _scores(symbols),
        10,
        {},
    )
    assert over_cap is True
    assert slots == 0
    assert warnings[0]["reason"] == WARNING_LONG_POSITION_RECOVERY_UNEXPECTED_ACTION
    assert [item["symbol"] for item in actions] == ["L0", "L1"]
    assert all(item["type"] == ACTION_SELL for item in actions)


def test_non_default_central_cap_value_is_used_by_shared_policy():
    state = _state([f"L{i}" for i in range(15)])
    _, slots, _, over_cap = apply_daily_plan_long_position_cap(
        state, [], _scores(state.current_symbols), 15, {}
    )
    assert over_cap is False
    assert slots == 0


def test_runtime_config_override_reaches_daily_plan_policy_without_optimizer_grid_entry():
    config = make_config({}, "2026-05-04", "2026-05-04", runtime_overrides={"max_long_positions": 15})
    assert config["max_long_positions"] == 15
    assert "max_long_positions" not in params_grid


def test_hedge_does_not_consume_long_slot_or_become_recovery_candidate():
    state = _state([*(f"L{i}" for i in range(10)), "HEDGE"], hedge_symbols=["HEDGE"])
    actions, slots, warnings, over_cap = apply_daily_plan_long_position_cap(
        state, [], _scores(state.current_symbols), 10, {}
    )
    assert actions == []
    assert slots == 0
    assert warnings == []
    assert over_cap is False


def test_over_cap_creates_only_required_lowest_score_full_sell_recovery():
    symbols = [f"L{i}" for i in range(11)]
    state = _state(symbols)
    actions, slots, warnings, over_cap = apply_daily_plan_long_position_cap(
        state, [], _scores(symbols, {"L7": 1.0}), 10, {symbol: 99.0 for symbol in symbols}
    )
    assert over_cap is True
    assert slots == 0
    assert warnings == []
    assert actions == [{"type": ACTION_SELL, "symbol": "L7", "shares": 10, "price": 99.0, "reason": "LONG_POSITION_CAP_RECOVERY"}]


def test_over_cap_ties_use_rs_then_reverse_symbol_and_block_all_buys():
    symbols = [f"L{i}" for i in range(12)]
    state = _state(symbols)
    scores = _scores(symbols, {symbol: 5.0 for symbol in symbols}, {symbol: 1.0 for symbol in symbols})
    scores[0]["rs_val"] = 0.0
    scores[1]["rs_val"] = 0.0
    actions, _, _, over_cap = apply_daily_plan_long_position_cap(
        state,
        [],
        scores,
        10,
        {},
    )
    assert over_cap is True
    assert all(item["type"] != ACTION_BUY for item in actions)
    assert [item["symbol"] for item in actions] == ["L1", "L0"]
    assert all(item["shares"] == 10 for item in actions)


def test_missing_or_nonfinite_holding_score_blocks_buys_without_forced_sell():
    symbols = [f"L{i}" for i in range(11)]
    state = _state(symbols)
    for invalid_score in (None, float("nan"), float("inf"), "bad"):
        scores = _scores(symbols)
        scores[0]["score"] = invalid_score
        scores[0]["valid"] = False
        actions, slots, warnings, over_cap = apply_daily_plan_long_position_cap(
            state,
            [],
            scores,
            10,
            {},
        )
        assert actions == []
        assert slots == 0
        assert over_cap is True
        assert warnings[0]["reason"] == WARNING_LONG_POSITION_RECOVERY_SCORE_UNAVAILABLE
        assert "L0" in warnings[0]["note"]


@pytest.mark.parametrize(
    "unexpected_actions",
    [
        [{"type": ACTION_BUY, "symbol": "NEW", "shares": 1, "reason": "STRATEGY_ENTRY"}],
        [
            {"type": ACTION_SELL, "symbol": "L1", "shares": 10, "reason": "SWITCH_OUT (to NEW)"},
            {"type": ACTION_BUY, "symbol": "NEW", "shares": 1, "reason": "SWITCH_IN (from L1)"},
        ],
    ],
)
def test_unexpected_over_cap_actions_fail_closed_without_recovery_sell(unexpected_actions):
    symbols = [f"L{i}" for i in range(12)]
    independent_sell = {"type": ACTION_SELL, "symbol": "L0", "shares": 10, "reason": "TRAILING_STOP"}
    actions, slots, warnings, over_cap = apply_daily_plan_long_position_cap(
        _state(symbols),
        [independent_sell, *unexpected_actions],
        _scores(symbols),
        10,
        {symbol: 100.0 for symbol in symbols},
    )
    assert actions == [independent_sell]
    assert slots == 0 and over_cap is True
    assert warnings[0]["reason"] == WARNING_LONG_POSITION_RECOVERY_UNEXPECTED_ACTION
    assert "type=" in warnings[0]["note"] and "reason=" in warnings[0]["note"]
    assert all(item["reason"] != "LONG_POSITION_CAP_RECOVERY" for item in actions)


def test_recovery_sell_uses_normalized_symbol_for_shares_and_price_lookup():
    symbols = [*(f"L{i}" for i in range(10)), "  weak  "]
    state = _state(symbols)
    scores = _scores(symbols, {"  weak  ": 0.0})
    actions, _, warnings, over_cap = apply_daily_plan_long_position_cap(
        state,
        [],
        scores,
        10,
        {**{f"L{i}": 100.0 for i in range(10)}, " weak ": 77.0},
    )
    assert over_cap is True and warnings == []
    assert actions == [{
        "type": ACTION_SELL,
        "symbol": "WEAK",
        "shares": 10,
        "price": 77.0,
        "reason": "LONG_POSITION_CAP_RECOVERY",
    }]


def test_final_normal_policy_passes_within_cap_and_fails_before_write_when_over_cap():
    state = _state([f"L{i}" for i in range(10)])
    validate_final_daily_plan_long_position_actions(
        state,
        [{"type": ACTION_SELL, "symbol": "L0", "shares": 10}, {"type": ACTION_BUY, "symbol": "NEW", "shares": 1}],
        "NORMAL",
        10,
        [],
    )
    with pytest.raises(RuntimeError, match="Final NORMAL"):
        validate_final_daily_plan_long_position_actions(
            state,
            [{"type": ACTION_BUY, "symbol": "NEW", "shares": 1}],
            "NORMAL",
            10,
            [],
        )


def test_final_over_cap_policy_warning_and_recovery_boundaries():
    state = _state([f"L{i}" for i in range(11)])
    unresolved_warning = [{"reason": WARNING_LONG_POSITION_RECOVERY_SCORE_UNAVAILABLE}]
    validate_final_daily_plan_long_position_actions(state, [], "OVER_CAP_RECOVERY", 10, unresolved_warning)

    with pytest.raises(RuntimeError, match="unsafe"):
        validate_final_daily_plan_long_position_actions(
            state,
            [{"type": ACTION_BUY, "symbol": "NEW", "shares": 1, "reason": "STRATEGY_ENTRY"}],
            "OVER_CAP_RECOVERY",
            10,
            unresolved_warning,
        )
    with pytest.raises(RuntimeError, match="unsafe"):
        validate_final_daily_plan_long_position_actions(
            state,
            [{"type": ACTION_SELL, "symbol": "L0", "shares": 10, "reason": "SWITCH_OUT (to NEW)"}],
            "OVER_CAP_RECOVERY",
            10,
            unresolved_warning,
        )
    with pytest.raises(RuntimeError, match="did not restore"):
        validate_final_daily_plan_long_position_actions(state, [], "OVER_CAP_RECOVERY", 10, [])
