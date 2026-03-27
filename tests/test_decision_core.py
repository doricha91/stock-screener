import pandas as pd
import pytest
from core.decision_core import compute_candidate_score, is_enterable_candidate

def test_compute_candidate_score():
    # 가중치 설정
    weights = {
        "turtle": 2.0,
        "rsi": 1.0,
        "sma": 1.5
    }
    
    # Mock 데이터 (Series)
    # 1. 모든 신호가 있는 경우
    row_all = pd.Series({
        "signal_turtle": 1,
        "signal_rsi": 1,
        "signal_sma": 1,
        "close": 100
    })
    score, reasons = compute_candidate_score(row_all, weights)
    assert score == 4.5
    assert set(reasons) == {"turtle", "rsi", "sma"}
    
    # 2. 일부 신호만 있는 경우
    row_partial = pd.Series({
        "signal_turtle": 1,
        "signal_rsi": 0,
        "signal_sma": 1,
        "close": 100
    })
    score, reasons = compute_candidate_score(row_partial, weights)
    assert score == 3.5
    assert set(reasons) == {"turtle", "sma"}
    
    # 3. 신호가 없는 경우
    row_none = pd.Series({
        "signal_turtle": 0,
        "signal_rsi": 0,
        "signal_sma": 0,
        "close": 100
    })
    score, reasons = compute_candidate_score(row_none, weights)
    assert score == 0.0
    assert reasons == []

def test_is_enterable_candidate():
    threshold = 2.0
    
    # 1. BULL 국면, 점수 미달
    assert is_enterable_candidate(1.5, threshold, "BULL") is False
    
    # 2. BULL 국면, 점수 충족
    assert is_enterable_candidate(2.0, threshold, "BULL") is True
    assert is_enterable_candidate(3.0, threshold, "BULL") is True
    
    # 3. PANIC 국면 (점수 관계없이 False)
    assert is_enterable_candidate(5.0, threshold, "PANIC") is False
    
    # 4. BEAR 국면, 점수 충족
    assert is_enterable_candidate(2.5, threshold, "BEAR") is True

if __name__ == "__main__":
    pytest.main([__file__])
