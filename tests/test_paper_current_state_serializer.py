from core.paper_account_state import build_paper_state_from_trades, create_initial_paper_state
from core.paper_current_state_serializer import paper_account_state_to_current_state_dict


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


def test_serializer_empty_state():
    state = create_initial_paper_state()
    data = paper_account_state_to_current_state_dict(state, "20260509")

    assert data["current_symbols"] == []
    assert data["shares"] == {}
    assert data["avg_price"] == {}
    assert data["highest_prices"] == {}
    assert data["absolute_cash"] == 100000.0
    assert data["current_cash_ratio"] == 1.0
    assert data["applied_trade_ids"] == []
    assert "positions" not in data


def test_serializer_buy_state_maps_top_level_fields():
    state = build_paper_state_from_trades(
        [_make_trade("t1", "CPAY", "BUY", 29, 343.99)],
        initial_cash=100000.0,
        currency="USD",
    )
    data = paper_account_state_to_current_state_dict(state, "2026-05-09")

    assert data["current_symbols"] == ["CPAY"]
    assert data["shares"] == {"CPAY": 29}
    assert data["avg_price"] == {"CPAY": 343.99}
    assert data["highest_prices"] == {"CPAY": 343.99}
    assert "positions" not in data


def test_serializer_computes_current_cash_ratio_from_total_equity():
    state = build_paper_state_from_trades(
        [
            _make_trade("t1", "CPAY", "BUY", 29, 343.99),
            _make_trade("t2", "GEN", "BUY", 440, 22.68),
            _make_trade("t3", "VRSN", "BUY", 34, 288.21),
        ],
        initial_cash=100000.0,
        currency="USD",
    )
    data = paper_account_state_to_current_state_dict(state, "20260509")

    expected_position_value = (29 * 343.99) + (440 * 22.68) + (34 * 288.21)
    expected_total_equity = 70245.95 + expected_position_value
    expected_cash_ratio = 70245.95 / expected_total_equity

    assert round(data["absolute_cash"], 2) == 70245.95
    assert abs(data["current_cash_ratio"] - expected_cash_ratio) < 1e-12


def test_serializer_generates_highest_price_meta():
    state = build_paper_state_from_trades(
        [_make_trade("t1", "CPAY", "BUY", 29, 343.99)],
        initial_cash=100000.0,
        currency="USD",
    )
    data = paper_account_state_to_current_state_dict(state, "20260509")

    assert data["highest_price_meta"]["CPAY"]["updated_at"] == "2026-05-09"
    assert data["highest_price_meta"]["CPAY"]["source"] == "paper_execution_log"
    assert data["highest_price_meta"]["CPAY"]["basis"] == "trade_price"


def test_serializer_stores_sorted_applied_trade_ids_list():
    state = build_paper_state_from_trades(
        [
            _make_trade("t2", "GEN", "BUY", 1, 10.0),
            _make_trade("t1", "CPAY", "BUY", 1, 20.0),
        ],
        initial_cash=100000.0,
        currency="USD",
    )
    data = paper_account_state_to_current_state_dict(state, "2026-05-09")

    assert data["applied_trade_ids"] == ["t1", "t2"]
