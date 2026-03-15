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

def test_bull_state_with_enough_candidates(base_config, sample_candidates):
    # 정책: BULL -> cash 0.0, hedge 0.0 -> slots 4
    state = build_target_portfolio_state('BULL', sample_candidates, base_config)
    
    assert state.target_long_slots == 4
    # 정렬 순서: AAPL -> NVDA -> TSLA -> MSFT
    assert state.target_symbols == ['AAPL', 'NVDA', 'TSLA', 'MSFT']

def test_panic_state_always_zero_slots(base_config, sample_candidates):
    # 정책: PANIC -> 무조건 slots 0 (신규 진입 차단)
    state = build_target_portfolio_state('PANIC', sample_candidates, base_config)
    
    assert state.target_long_slots == 0
    assert state.target_symbols == []

def test_bear_state_rounding(base_config, sample_candidates):
    # 정책: BEAR -> cash 0.5, hedge 0.2 -> available 0.3
    # 4 * 0.3 = 1.2 -> int(1.2) = 1 (보수적 내림 정책)
    state = build_target_portfolio_state('BEAR', sample_candidates, base_config)
    
    assert state.target_long_slots == 1
    assert state.target_symbols == ['AAPL']

def test_rounding_logic_boundary(base_config, sample_candidates):
    # 가용 비중이 0.49일 때: 4 * 0.49 = 1.96 -> 1 슬롯 (내림 확인)
    config = base_config.copy()
    config['REGIME_RULES']['BULL'] = {'target_cash_ratio': 0.51} # available 0.49
    config['USE_HEDGE_MODE'] = False
    
    state = build_target_portfolio_state('BULL', sample_candidates, config)
    assert state.target_long_slots == 1

def test_tie_break_stability_symbol_asc(base_config):
    # 정책: 점수/RS 같으면 심볼 오름차순 (A가 B보다 우선)
    candidates = [
        {'symbol': 'B', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True},
        {'symbol': 'A', 'score': 2.0, 'rs_val': 1.5, 'entry_signal': True},
    ]
    state = build_target_portfolio_state('BULL', candidates, base_config)
    assert state.target_symbols == ['A', 'B']

def test_score_threshold_fallback(base_config, sample_candidates):
    # 정책: config에 score_threshold가 없으면 1.0 기본값 사용
    config = base_config.copy()
    if 'score_threshold' in config:
        del config['score_threshold']
        
    state = build_target_portfolio_state('BULL', sample_candidates, config)
    # score 0.5인 GOOGL은 여전히 제외되어야 함 (threshold 1.0)
    assert 'GOOGL' not in state.target_symbols

def test_missing_fields_validation():
    bad_row = {'symbol': 'AAPL', 'score': 2.0}
    with pytest.raises(ValueError, match="필수 필드가 누락되었습니다"):
        validate_candidate_row(bad_row)

def test_empty_candidates_returns_empty_symbols(base_config):
    state = build_target_portfolio_state('BULL', [], base_config)
    assert state.target_symbols == []
    assert state.target_long_slots == 4
