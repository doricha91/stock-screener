import pandas as pd
import pytest

from core.backtest_engine import evaluate_switching_opportunity, extract_candidate_symbol


def test_extract_candidate_symbol_prefers_symbol_column_over_dataframe_index():
    row = pd.Series({"symbol": "CF", "score": 3.0, "rs_val": 0.1}, name=0)
    assert extract_candidate_symbol(row) == "CF"


def test_evaluate_switching_opportunity_uses_ticker_not_numeric_index():
    candidates = pd.DataFrame(
        [
            {"symbol": "CF", "score": 3.0, "rs_val": 0.1, "close": 130.39},
            {"symbol": "BRK-B", "score": 2.0, "rs_val": 0.05, "close": 484.96},
        ],
        index=[0, 2],
    )
    current_pos_scores = [
        {"symbol": "CPAY", "score": 0.0, "return": -0.1, "shares": 10, "price": 100.0}
    ]
    config = {
        "SWITCHING_PREMIUM": 1.0,
        "ALLOW_PROFIT_SWITCH": False,
        "SWITCHING_MAX_COUNT": 2,
    }

    pairs = evaluate_switching_opportunity(candidates, current_pos_scores, config)

    assert len(pairs) == 1
    assert pairs[0]["buy_symbol"] == "CF"
    assert pairs[0]["buy_symbol"] != "0"
    assert pairs[0]["buy_symbol"] != "2"


def test_extract_candidate_symbol_rejects_missing_symbol_column():
    row = pd.Series({"score": 3.0, "rs_val": 0.1, "close": 130.39}, name=0)
    with pytest.raises(ValueError, match="missing valid symbol"):
        extract_candidate_symbol(row)


def test_extract_candidate_symbol_rejects_numeric_only_symbol():
    row = pd.Series({"symbol": "2", "score": 3.0, "rs_val": 0.1}, name=0)
    with pytest.raises(ValueError, match="numeric-only"):
        extract_candidate_symbol(row)
