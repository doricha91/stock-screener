import pytest
from core.target_portfolio_state import (
    build_target_portfolio_state,
    TargetPortfolioState,
    get_target_allocation_by_market_state,
    validate_candidate_row,
    filter_enterable_candidates,
    rank_candidates,
    select_target_symbols
)

@pytest.fixture
def base_config():
    return {
        'max_positions': 4,
        'score_threshold': 1.0,
        'USE_HEDGE_MODE': True,
        'HEDGE_RATIO_BEAR': 0.2,
        'HEDGE_RATIO_PANIC': 0.5,
        'REGIME_RULES': {
            'BULL': {'target_cash_ratio': 0.0},
            'BEAR': {'target_cash_ratio': 0.5},
            'UNSTABLE': {'target_cash_ratio': 0.3},
            'PANIC': {'target_cash_ratio': 1.0}
        }
    }

@pytest.fixture
def sample_candidates():
    return [
        {'symbol': 'AAPL', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True},
        {'symbol': 'MSFT', 'score': 1.5, 'rs_val': 2.0, 'entry_signal': True},
        {'symbol': 'GOOGL', 'score': 0.5, 'rs_val': 1.0, 'entry_signal': True}, # score low
        {'symbol': 'AMZN', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': False}, # no signal
        {'symbol': 'TSLA', 'score': 2.0, 'rs_val': 0.5, 'entry_signal': True},
        {'symbol': 'NVDA', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True}, # tie with AAPL
    ]

def test_bull_state_with_enough_candidates(base_config, sample_candidates):
    state = build_target_portfolio_state('BULL', sample_candidates, base_config)
    
    assert state.market_state == 'BULL'
    assert state.target_cash_ratio == 0.0
    assert state.target_hedge_ratio == 0.0
    assert state.target_long_slots == 4
    # Expected filtered & ranked: 
    # 1. AAPL (score 2.0, rs 1.5) or NVDA (score 2.0, rs 1.5) or TSLA (score 2.0, rs 0.5)
    # Ranked: [AAPL/NVDA (score 2.0, rs 1.5), TSLA (score 2.0, rs 0.5), MSFT (score 1.5, rs 2.0)]
    # Tie-break (symbol desc): NVDA > AAPL
    assert len(state.target_symbols) == 4
    assert 'NVDA' in state.target_symbols
    assert 'AAPL' in state.target_symbols
    assert 'TSLA' in state.target_symbols
    assert 'MSFT' in state.target_symbols

def test_panic_state(base_config, sample_candidates):
    state = build_target_portfolio_state('PANIC', sample_candidates, base_config)
    
    assert state.market_state == 'PANIC'
    assert state.target_cash_ratio == 1.0
    assert state.target_hedge_ratio == 0.5
    assert state.target_long_slots == 0
    assert state.target_symbols == []

def test_bear_state(base_config, sample_candidates):
    state = build_target_portfolio_state('BEAR', sample_candidates, base_config)
    
    # target_cash_ratio 0.5, hedge 0.2 -> available 0.3. 4 * 0.3 = 1.2 -> 1 slot
    assert state.target_long_slots == 1
    assert len(state.target_symbols) == 1
    assert state.target_symbols[0] == 'NVDA' # Highest ranked

def test_stability(base_config, sample_candidates):
    state1 = build_target_portfolio_state('BULL', sample_candidates, base_config)
    state2 = build_target_portfolio_state('BULL', sample_candidates, base_config)
    
    assert state1 == state2
    assert state1.target_symbols == state2.target_symbols

def test_missing_fields():
    bad_row = {'symbol': 'AAPL', 'score': 2.0} # Missing rs_val, entry_signal
    with pytest.raises(ValueError, match="필수 필드가 누락되었습니다"):
        validate_candidate_row(bad_row)

def test_empty_candidates(base_config):
    state = build_target_portfolio_state('BULL', [], base_config)
    assert state.target_symbols == []
    assert state.target_long_slots == 4

def test_fewer_candidates_than_slots(base_config):
    small_candidates = [
        {'symbol': 'AAPL', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True}
    ]
    state = build_target_portfolio_state('BULL', small_candidates, base_config)
    assert len(state.target_symbols) == 1
    assert state.target_symbols == ['AAPL']

def test_tie_break_stability(base_config):
    # Two identical candidates except symbol
    candidates = [
        {'symbol': 'B', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True},
        {'symbol': 'A', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True},
    ]
    state = build_target_portfolio_state('BULL', candidates, base_config)
    # Sorted by symbol desc (reverse=True): B then A
    assert state.target_symbols == ['B', 'A']
