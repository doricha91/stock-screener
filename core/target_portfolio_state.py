from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import pandas as pd

@dataclass(frozen=True)
class TargetPortfolioState:
    """
    백테스트와 실전 스크리너에서 공통으로 사용하는 목표 포트폴리오 상태 정보.
    """
    market_state: str
    target_cash_ratio: float
    target_hedge_ratio: float
    target_long_slots: int
    target_symbols: List[str] = field(default_factory=list)

def get_target_allocation_by_market_state(market_state: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    국면별 목표 정책(현금 비중, 헤지 비중, 롱 슬롯 수)을 계산합니다.
    """
    # 1. 기존 REGIME_RULES에서 정책 추출
    # market_analyzer 등에서 이미 config.REGIME_RULES를 사용하므로 여기서도 이를 존중함
    regime_rules = config.get('REGIME_RULES', {})
    rule = regime_rules.get(market_state, regime_rules.get('UNSTABLE', {
        'target_cash_ratio': 0.3,
        'trailing_stop_multiplier': 2.5
    }))
    
    target_cash_ratio = rule.get('target_cash_ratio', 0.0)
    
    # 2. 헤지 비중 계산
    target_hedge_ratio = 0.0
    if config.get('USE_HEDGE_MODE', False):
        if market_state == 'PANIC':
            target_hedge_ratio = config.get('HEDGE_RATIO_PANIC', 0.5)
        elif market_state == 'BEAR':
            target_hedge_ratio = config.get('HEDGE_RATIO_BEAR', 0.2)
            
    # 3. 롱 슬롯 수 계산 (전체 슬롯 중 가용 비중만큼 할당)
    max_positions = config.get('max_positions', 4)
    
    # PANIC일 경우 신규 진입 금지 정책 (target_long_slots = 0)
    if market_state == 'PANIC':
        target_long_slots = 0
    else:
        # 가용 비중 = 1.0 - 현금비중 - 헤지비중
        available_ratio = max(0.0, 1.0 - target_cash_ratio - target_hedge_ratio)
        # 가용 비중에 따른 슬롯 수 (내림 처리하여 보수적으로 계산)
        target_long_slots = int(max_positions * available_ratio)
        
    return {
        'target_cash_ratio': target_cash_ratio,
        'target_hedge_ratio': target_hedge_ratio,
        'target_long_slots': target_long_slots
    }

def validate_candidate_row(row: Dict[str, Any]) -> None:
    """
    후보 종목 데이터의 필수 필드를 검증합니다.
    """
    required_fields = ['symbol', 'score', 'rs_val', 'entry_signal']
    missing = [field for field in required_fields if field not in row]
    if missing:
        raise ValueError(f"후보 종목 데이터에 필수 필드가 누락되었습니다: {missing}")

def filter_enterable_candidates(candidate_rows: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    진입 가능한 후보 종목만 필터링합니다.
    """
    threshold = config.get('score_threshold', 1.0)
    
    filtered = []
    for row in candidate_rows:
        validate_candidate_row(row)
        
        # 필터링 조건:
        # 1. entry_signal (buy_signal) 이 True 여야 함
        # 2. score 가 threshold 이상이어야 함
        # 3. rs_val 이 0 보다 커야 함
        if (row.get('entry_signal') is True and 
            row.get('score', 0.0) >= threshold and 
            row.get('rs_val', 0.0) > 0):
            filtered.append(row)
            
    return filtered

def rank_candidates(candidate_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    후보 종목을 정렬합니다. (1순위: score 내림차순, 2순위: rs_val 내림차순)
    """
    # symbol을 tie-breaker로 추가하여 동일 입력 시 동일 결과 보장
    return sorted(
        candidate_rows, 
        key=lambda x: (x.get('score', 0.0), x.get('rs_val', 0.0), x.get('symbol', '')), 
        reverse=True
    )

def select_target_symbols(sorted_candidates: List[Dict[str, Any]], target_long_slots: int) -> List[str]:
    """
    정렬된 후보 중에서 목표 슬롯 수만큼 심볼을 선택합니다.
    """
    if target_long_slots <= 0:
        return []
    
    selected = []
    seen = set()
    
    for row in sorted_candidates:
        symbol = row.get('symbol')
        if symbol and symbol not in seen:
            selected.append(symbol)
            seen.add(symbol)
            if len(selected) >= target_long_slots:
                break
                
    return selected

def build_target_portfolio_state(
    market_state: str, 
    candidate_rows: List[Dict[str, Any]], 
    config: Dict[str, Any]
) -> TargetPortfolioState:
    """
    시장 상태와 후보 종목들을 입력받아 최종 목표 포트폴리오 상태를 생성합니다.
    """
    # 1. 국면별 정책 계산
    allocation = get_target_allocation_by_market_state(market_state, config)
    
    # 2. 후보 필터링
    enterable = filter_enterable_candidates(candidate_rows, config)
    
    # 3. 후보 정렬
    ranked = rank_candidates(enterable)
    
    # 4. 목표 종목 선택
    target_symbols = select_target_symbols(ranked, allocation['target_long_slots'])
    
    return TargetPortfolioState(
        market_state=market_state,
        target_cash_ratio=allocation['target_cash_ratio'],
        target_hedge_ratio=allocation['target_hedge_ratio'],
        target_long_slots=allocation['target_long_slots'],
        target_symbols=target_symbols
    )
