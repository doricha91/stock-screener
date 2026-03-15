import pytest
from core.target_portfolio_state import (
    build_target_portfolio_state,
    TargetPortfolioState,
    CurrentPortfolioState,
    RebalanceDecision,
    evaluate_rebalance_need,
    compare_symbol_sets,
    compare_ratio,
    validate_candidate_row
)

@pytest.fixture
def base_config():
    return {
        'max_positions': 4,
        'score_threshold': 1.0,
        'USE_HEDGE_MODE': True,
        'HEDGE_RATIO_BEAR': 0.2,
        'HEDGE_RATIO_PANIC': 0.5,
        'cash_ratio_tolerance': 0.05,
        'hedge_ratio_tolerance': 0.05,
        'REGIME_RULES': {
            'BULL': {'target_cash_ratio': 0.0},
            'BEAR': {'target_cash_ratio': 0.5},
            'UNSTABLE': {'target_cash_ratio': 0.3},
            'PANIC': {'target_cash_ratio': 1.0}
        }
    }

@pytest.fixture
def sample_candidates():
    """
    정렬 우선순위 테스트용 샘플:
    1. AAPL (score 2.0, rs 1.5)
    2. NVDA (score 2.0, rs 1.5) -> AAPL과 점수/RS 동일, 심볼에서 밀림
    3. TSLA (score 2.0, rs 0.5) -> RS에서 밀림
    4. MSFT (score 1.5, rs 2.0) -> Score에서 밀림
    5. AMZN (signal False) -> 필터링됨
    6. GOOGL (score 0.5) -> 필터링됨
    """
    return [
        {'symbol': 'AAPL', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True},
        {'symbol': 'MSFT', 'score': 1.5, 'rs_val': 2.0, 'entry_signal': True},
        {'symbol': 'GOOGL', 'score': 0.5, 'rs_val': 1.0, 'entry_signal': True}, 
        {'symbol': 'AMZN', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': False},
        {'symbol': 'TSLA', 'score': 2.0, 'rs_val': 0.5, 'entry_signal': True},
        {'symbol': 'NVDA', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True}, 
    ]

# --- A단계 테스트 유지 ---

def test_bull_state_with_enough_candidates(base_config, sample_candidates):
    state = build_target_portfolio_state('BULL', sample_candidates, base_config)
    assert state.target_long_slots == 4
    assert state.target_symbols == ['AAPL', 'NVDA', 'TSLA', 'MSFT']

def test_panic_state_always_zero_slots(base_config, sample_candidates):
    state = build_target_portfolio_state('PANIC', sample_candidates, base_config)
    assert state.target_long_slots == 0
    assert state.target_symbols == []

def test_bear_state_rounding(base_config, sample_candidates):
    state = build_target_portfolio_state('BEAR', sample_candidates, base_config)
    assert state.target_long_slots == 1
    assert state.target_symbols == ['AAPL']

def test_rounding_logic_boundary(base_config, sample_candidates):
    config = base_config.copy()
    config['REGIME_RULES']['BULL'] = {'target_cash_ratio': 0.51}
    config['USE_HEDGE_MODE'] = False
    state = build_target_portfolio_state('BULL', sample_candidates, config)
    assert state.target_long_slots == 1

def test_tie_break_stability_symbol_asc(base_config):
    candidates = [
        {'symbol': 'B', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True},
        {'symbol': 'A', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True},
    ]
    state = build_target_portfolio_state('BULL', candidates, base_config)
    assert state.target_symbols == ['A', 'B']

# --- B단계 테스트: 리밸런싱 판정 ---

def test_rebalance_no_action_needed(base_config):
    target = TargetPortfolioState('BULL', 0.0, 0.0, 4, ['AAPL', 'MSFT'])
    current = CurrentPortfolioState(['AAPL', 'MSFT'], 0.0, 0.0)
    
    decision = evaluate_rebalance_need(current, target, base_config)
    
    assert decision.rebalance_needed is False
    assert decision.rebalance_reason == []

def test_rebalance_symbol_set_changed(base_config):
    target = TargetPortfolioState('BULL', 0.0, 0.0, 4, ['AAPL', 'MSFT'])
    current = CurrentPortfolioState(['AAPL', 'GOOGL'], 0.0, 0.0) # MSFT 대신 GOOGL 보유
    
    decision = evaluate_rebalance_need(current, target, base_config)
    
    assert decision.rebalance_needed is True
    assert "SYMBOL_SET_CHANGED" in decision.rebalance_reason
    assert decision.symbol_diff_added == ['MSFT']
    assert decision.symbol_diff_removed == ['GOOGL']

def test_rebalance_cash_ratio_deviation(base_config):
    # tolerance 0.05
    target = TargetPortfolioState('BEAR', 0.5, 0.2, 1, ['AAPL'])
    current = CurrentPortfolioState(['AAPL'], 0.44, 0.2) # diff 0.06 > 0.05
    
    decision = evaluate_rebalance_need(current, target, base_config)
    
    assert decision.rebalance_needed is True
    assert "CASH_RATIO_DEVIATION" in decision.rebalance_reason
    assert abs(decision.cash_ratio_diff - 0.06) < 1e-9

def test_rebalance_hedge_ratio_deviation(base_config):
    target = TargetPortfolioState('BEAR', 0.5, 0.2, 1, ['AAPL'])
    current = CurrentPortfolioState(['AAPL'], 0.5, 0.26) # diff 0.06 > 0.05
    
    decision = evaluate_rebalance_need(current, target, base_config)
    
    assert decision.rebalance_needed is True
    assert "HEDGE_RATIO_DEVIATION" in decision.rebalance_reason

def test_rebalance_order_insensitive(base_config):
    target = TargetPortfolioState('BULL', 0.0, 0.0, 4, ['AAPL', 'MSFT'])
    current = CurrentPortfolioState(['MSFT', 'AAPL'], 0.0, 0.0) # 순서만 다름
    
    decision = evaluate_rebalance_need(current, target, base_config)
    
    assert decision.rebalance_needed is False

def test_rebalance_tolerance_boundary(base_config):
    # tolerance 0.05
    target = TargetPortfolioState('BULL', 0.1, 0.0, 4, ['AAPL'])
    current = CurrentPortfolioState(['AAPL'], 0.05, 0.0) # diff 0.05 (딱 tolerance 걸림)
    
    decision = evaluate_rebalance_need(current, target, base_config)
    
    # 정책: abs(diff) > tolerance 일 때만 True. 0.05 > 0.05 는 False.
    assert decision.rebalance_needed is False

def test_rebalance_multiple_reasons(base_config):
    target = TargetPortfolioState('BEAR', 0.5, 0.2, 1, ['AAPL'])
    current = CurrentPortfolioState(['MSFT'], 0.1, 0.0) # 종목 다르고 비중도 다름
    
    decision = evaluate_rebalance_need(current, target, base_config)
    
    assert decision.rebalance_needed is True
    assert "SYMBOL_SET_CHANGED" in decision.rebalance_reason
    assert "CASH_RATIO_DEVIATION" in decision.rebalance_reason
    assert "HEDGE_RATIO_DEVIATION" in decision.rebalance_reason

def test_rebalance_fallback_tolerance():
    # config 가 비어있을 때 fallback 0.05 가 잘 작동하는지 확인
    target = TargetPortfolioState('BULL', 0.1, 0.0, 4, ['AAPL'])
    current = CurrentPortfolioState(['AAPL'], 0.04, 0.0) # diff 0.06 > 0.05
    
    decision = evaluate_rebalance_need(current, target, {})
    
    assert decision.rebalance_needed is True
    assert "CASH_RATIO_DEVIATION" in decision.rebalance_reason
