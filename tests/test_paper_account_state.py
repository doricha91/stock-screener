import pytest

from core.paper_account_state import (
    apply_paper_trade,
    build_paper_state_from_trades,
    create_initial_paper_state,
)


def make_trade(
    trade_id: str,
    symbol: str,
    side: str,
    shares: int,
    price: float,
) -> dict:
    return {
        "trade_id": trade_id,
        "date": "2026-05-07",
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": price,
        "gross_amount": shares * price,
    }


def test_create_initial_paper_state_defaults():
    state = create_initial_paper_state()
    assert state.cash == 100000.0
    assert state.currency == "USD"
    assert state.positions == {}
    assert state.applied_trade_ids == set()
    assert state.realized_pnl == 0.0
    assert state.realized_pnl_by_symbol == {}


def test_apply_buy_trade_updates_cash_and_position():
    state = create_initial_paper_state()
    state = apply_paper_trade(state, make_trade("t1", "AAPL", "BUY", 10, 100.0))
    assert state.cash == 99000.0
    assert state.positions["AAPL"].shares == 10
    assert state.positions["AAPL"].avg_price == 100.0


def test_apply_additional_buy_updates_weighted_average_price():
    state = create_initial_paper_state()
    state = apply_paper_trade(state, make_trade("t1", "AAPL", "BUY", 10, 100.0))
    state = apply_paper_trade(state, make_trade("t2", "AAPL", "BUY", 10, 200.0))
    assert state.positions["AAPL"].shares == 20
    assert state.positions["AAPL"].avg_price == 150.0
    assert state.positions["AAPL"].highest_price == 200.0


def test_apply_sell_reduces_shares_and_increases_cash():
    state = create_initial_paper_state()
    state = apply_paper_trade(state, make_trade("t1", "AAPL", "BUY", 20, 150.0))
    state = apply_paper_trade(state, make_trade("t2", "AAPL", "SELL", -5, 300.0))
    assert state.positions["AAPL"].shares == 15
    assert state.cash == 98500.0


def test_sell_realized_pnl_uses_average_cost_and_keeps_avg_price():
    state = create_initial_paper_state()
    state = apply_paper_trade(state, make_trade("t1", "AAPL", "BUY", 10, 100.0))
    state = apply_paper_trade(state, make_trade("t2", "AAPL", "SELL", -4, 120.0))
    assert state.realized_pnl == 80.0
    assert state.realized_pnl_by_symbol["AAPL"] == 80.0
    assert state.positions["AAPL"].shares == 6
    assert state.positions["AAPL"].avg_price == 100.0


def test_apply_full_sell_removes_position():
    state = create_initial_paper_state()
    state = apply_paper_trade(state, make_trade("t1", "AAPL", "BUY", 10, 100.0))
    state = apply_paper_trade(state, make_trade("t2", "AAPL", "SELL", -10, 120.0))
    assert "AAPL" not in state.positions
    assert state.realized_pnl == 200.0
    assert state.realized_pnl_by_symbol["AAPL"] == 200.0


def test_loss_sell_records_negative_realized_pnl():
    state = create_initial_paper_state()
    state = apply_paper_trade(state, make_trade("t1", "AAPL", "BUY", 10, 100.0))
    state = apply_paper_trade(state, make_trade("t2", "AAPL", "SELL", -5, 80.0))
    assert state.realized_pnl == -100.0
    assert state.realized_pnl_by_symbol["AAPL"] == -100.0


def test_insufficient_cash_buy_raises():
    state = create_initial_paper_state(initial_cash=500.0)
    with pytest.raises(ValueError):
        apply_paper_trade(state, make_trade("t1", "AAPL", "BUY", 10, 100.0))


def test_sell_more_than_held_raises():
    state = create_initial_paper_state()
    state = apply_paper_trade(state, make_trade("t1", "AAPL", "BUY", 5, 100.0))
    with pytest.raises(ValueError):
        apply_paper_trade(state, make_trade("t2", "AAPL", "SELL", -10, 120.0))


def test_duplicate_trade_id_is_skipped():
    trade = make_trade("dup1", "AAPL", "BUY", 10, 100.0)
    state = build_paper_state_from_trades([trade, trade])
    assert state.cash == 99000.0
    assert state.positions["AAPL"].shares == 10
    assert state.applied_trade_ids == {"dup1"}


def test_duplicate_sell_trade_id_does_not_double_count_realized_pnl():
    buy = make_trade("t1", "AAPL", "BUY", 10, 100.0)
    sell = make_trade("t2", "AAPL", "SELL", -4, 120.0)
    state = build_paper_state_from_trades([buy, sell, sell])
    assert state.realized_pnl == 80.0
    assert state.realized_pnl_by_symbol["AAPL"] == 80.0
    assert state.positions["AAPL"].shares == 6


def test_realized_pnl_by_symbol_accumulates_per_symbol():
    state = build_paper_state_from_trades(
        [
            make_trade("t1", "AAPL", "BUY", 10, 100.0),
            make_trade("t2", "AAPL", "SELL", -4, 120.0),
            make_trade("t3", "AAPL", "SELL", -2, 90.0),
        ]
    )
    assert state.realized_pnl == 60.0
    assert state.realized_pnl_by_symbol["AAPL"] == 60.0
