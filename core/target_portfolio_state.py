from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
import math

@dataclass(frozen=True)
class TargetPortfolioState:
    """
    백테스트와 실전 스크리너에서 공통으로 사용하는 목표 포트폴리오 상태 정보.
    
    이 데이터 구조는 특정 시점(오늘)의 시장 상황과 후보 종목들을 기반으로
    시스템이 지향해야 할 최종적인 포트폴리오 구성을 정의합니다.
    """
    market_state: str        # 국면 (BULL, BEAR, UNSTABLE, PANIC)
    target_cash_ratio: float # 목표 현금 비중 (0.0 ~ 1.0)
    target_hedge_ratio: float # 목표 헤지(인버스) 비중 (0.0 ~ 1.0)
    target_long_slots: int   # 진입 가능한 롱(매수) 포지션 최대 개수
    target_symbols: List[str] # 최종 선택된 목표 매수 종목 리스트

@dataclass(frozen=True)
class CurrentPortfolioState:
    """
    현재 계좌의 포트폴리오 상태 정보를 담는 데이터 구조.
    
    TargetPortfolioState와 비교하여 리밸런싱 필요 여부를 판단하는 데 사용됩니다.
    """
    current_symbols: List[str]      # 현재 보유 중인 롱(매수) 종목 리스트
    current_cash_ratio: float       # 현재 계좌 내 현금 비중 (0.0 ~ 1.0)
    current_hedge_ratio: float      # 현재 계좌 내 헤지(인버스) 종목 비중 (0.0 ~ 1.0)
    absolute_cash: float            # 현재 계좌 내 실제 현금 금액
    shares: Dict[str, int]          # 종목별 보유 수량 (symbol: shares)
    avg_price: Dict[str, float]     # 종목별 평균 단가 (symbol: avg_price)
    highest_prices: Dict[str, float] # 보유 기간 중 최고가 (Trailing Stop용)
    hedge_symbols: List[str] = field(default_factory=list) # 현재 보유 중인 헤지 종목 리스트

    def __post_init__(self):
        """데이터 무결성 검증 (MFU-FT3 보완)"""
        if self.absolute_cash < 0:
            raise ValueError(f"❌ [Fail-safe] absolute_cash must be >= 0: {self.absolute_cash}")
        
        for symbol, qty in self.shares.items():
            if not isinstance(qty, int):
                raise ValueError(f"❌ [Fail-safe] shares for {symbol} must be int: {qty}")
        
        for symbol, price in self.avg_price.items():
            # 수량이 있는 종목에 대해서만 가격 검증
            if self.shares.get(symbol, 0) > 0:
                if price <= 0:
                    raise ValueError(f"❌ [Fail-safe] avg_price for {symbol} must be > 0: {price}")
                if self.highest_prices.get(symbol, 0) < price:
                    # 최고가는 최소한 평단보다는 크거나 같아야 함 (데이터 정합성)
                    raise ValueError(f"❌ [Fail-safe] highest_price for {symbol} cannot be less than avg_price")

@dataclass(frozen=True)
class RebalanceDecision:
    """
    현재 상태와 목표 상태를 비교한 리밸런싱 판단 결과.
    """
    rebalance_needed: bool          # 리밸런싱(주문)이 필요한지 여부
    rebalance_reason: List[str]     # 리밸런싱이 필요한 이유 코드 목록
    symbol_diff_added: List[str]    # 신규 진입이 필요한 종목
    symbol_diff_removed: List[str]  # 제외(매도)가 필요한 종목
    cash_ratio_diff: float          # 현금 비중 차이 (target - current)
    hedge_ratio_diff: float         # 헤지 비중 차이 (target - current)

def determine_target_long_slots(
    market_state: str, 
    max_positions: int, 
    target_cash_ratio: float, 
    target_hedge_ratio: float
) -> int:
    """
    [정책 명세] 국면별 목표 롱 슬롯 개수를 계산합니다.
    
    계산 정책:
    1. 가용 비중(available_ratio) = 1.0 - 현금 비중 - 헤지 비중
    2. 목표 슬롯 = int(max_positions * 가용 비중)
       - 내림(int/floor) 처리를 통해 보수적으로 슬롯을 할당합니다.
       - 소수점 이하 비중으로 인해 과도한 종목이 매수되는 것을 방지하기 위함입니다.
    3. PANIC 국면 예외 처리:
       - PANIC 국면에서는 가용 비중과 상관없이 목표 슬롯을 0으로 강제합니다.
       - 이는 '신규 롱 진입의 완전 차단'이라는 운영 정책을 반영한 것입니다.
    4. 최소 1슬롯 보장 정책은 현재 적용하지 않습니다. (가용 자산이 부족하면 0개가 될 수 있음)
    """
    if market_state == "PANIC":
        return 0
        
    available_ratio = max(0.0, 1.0 - target_cash_ratio - target_hedge_ratio)
    # 보수적 해석을 위해 int(내림) 사용
    slots = int(max_positions * available_ratio)
    return max(0, slots)

def get_target_allocation_by_market_state(market_state: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    [정책 명세] 시장 국면에 따른 자산 배분 및 슬롯 정책을 결정합니다.
    
    정책 출처:
    - target_cash_ratio: config['target_cash_ratio'] (동적 오버라이드 우선) 
      또는 기존 config.REGIME_RULES 값을 사용합니다.
    """
    # 1. 동적 오버라이드된 값이 있으면 우선 사용, 없으면 REGIME_RULES에서 추출
    if 'target_cash_ratio' in config:
        target_cash_ratio = config['target_cash_ratio']
    else:
        regime_rules = config.get('REGIME_RULES', {})
        rule = regime_rules.get(market_state, regime_rules.get('UNSTABLE', {
            'target_cash_ratio': 0.3
        }))
        target_cash_ratio = rule.get('target_cash_ratio', 0.0)
    
    # 2. 헤지 비중 계산 (기존 정책 재사용)
    target_hedge_ratio = 0.0
    if config.get('USE_HEDGE_MODE', False):
        if market_state == 'PANIC':
            target_hedge_ratio = config.get('HEDGE_RATIO_PANIC', 0.5)
        elif market_state == 'BEAR':
            target_hedge_ratio = config.get('HEDGE_RATIO_BEAR', 0.2)
            
    # 3. 롱 슬롯 수 계산 (분리된 정책 함수 호출)
    max_positions = config.get('max_positions', 4)
    target_long_slots = determine_target_long_slots(
        market_state, max_positions, target_cash_ratio, target_hedge_ratio
    )
        
    return {
        'target_cash_ratio': target_cash_ratio,
        'target_hedge_ratio': target_hedge_ratio,
        'target_long_slots': target_long_slots
    }

def validate_candidate_row(row: Dict[str, Any]) -> None:
    """
    후보 종목 데이터의 필수 필드를 검증합니다.
    
    필수 필드 정의:
    - symbol: 종목 식별자
    - score: 전략 앙상블 점수
    - rs_val: 상대 강도 값
    - entry_signal: 개별 전략의 진입 신호 발생 여부 (True/False)
    """
    required_fields = ['symbol', 'score', 'rs_val', 'entry_signal']
    missing = [field for field in required_fields if field not in row]
    if missing:
        raise ValueError(f"후보 종목 데이터에 필수 필드가 누락되었습니다: {missing}")

def filter_enterable_candidates(candidate_rows: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    [정책 명세] 진입 조건을 만족하는 후보만 남깁니다.
    
    필터링 기준:
    1. entry_signal: 전략상 매수 신호가 발생했는가
    2. score >= score_threshold: 앙상블 점수가 최소 기준을 넘었는가
    3. rs_val > 0: 상대 강도가 양수인가 (최소한의 우상향 확인)
    
    설계 의도:
    - 기존 전략의 'buy_signal' 판정 로직을 명시적 필터링 함수로 분리하여
      백테스트와 실전 스크리너가 동일한 필터링 기준을 공유하게 함.
    """
    # score_threshold 출처: config 우선 사용, 없을 시 1.0 (기본 보수값) 을 fallback 으로 사용
    threshold = config.get('score_threshold', 1.0)
    
    filtered = []
    for row in candidate_rows:
        validate_candidate_row(row)
        
        if (row.get('entry_signal') is True and 
            row.get('score', 0.0) >= threshold and 
            row.get('rs_val', 0.0) > 0):
            filtered.append(row)
            
    return filtered

def rank_candidates(candidate_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    [정책 명세] 후보 종목들 간의 우선순위를 결정합니다.
    
    정렬 순서:
    1. score (내림차순): 앙상블 신호가 강한 종목 우선
    2. rs_val (내림차순): 상대적 강세가 더 뚜렷한 종목 우선 (Tie-breaker 1)
    3. symbol (오름차순): 알파벳 순서 (Tie-breaker 2, 안정적 결과 보장용)
    
    설계 의도:
    - 단순 reverse=True 대신 명시적인 정렬 키를 사용하여 정책 의도를 분명히 함.
    - 동일 입력에 대해 항상 동일한 순서의 리스트를 반환하여 결정론적 결과를 보장함.
    """
    return sorted(
        candidate_rows, 
        key=lambda x: (-x.get('score', 0.0), -x.get('rs_val', 0.0), x.get('symbol', ''))
    )

def select_target_symbols(sorted_candidates: List[Dict[str, Any]], target_long_slots: int) -> List[str]:
    """
    [정책 명세] 정렬된 리스트에서 슬롯 수만큼 상위 종목을 추출합니다.
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
    시장 상황과 후보 종목 정보를 조합하여 '오늘의 목표 포트폴리오 상태'를 생성합니다. (오케스트레이터)
    
    이 함수는 모든 정책 함수를 순차적으로 실행하며, 
    외부 모듈(엔진, 스크리너)이 목표 상태를 알기 위해 호출하는 단일 진입점입니다.
    """
    # 1. 국면별 정책 계산 (현금, 헤지 비중 및 슬롯 수 결정)
    allocation = get_target_allocation_by_market_state(market_state, config)
    
    # 2. 후보 필터링 (진입 가능한 종목만 추출)
    enterable = filter_enterable_candidates(candidate_rows, config)
    
    # 3. 후보 정렬 (우선순위 부여)
    ranked = rank_candidates(enterable)
    
    # 4. 목표 종목 선택 (슬롯만큼 확보)
    target_symbols = select_target_symbols(ranked, allocation['target_long_slots'])
    
    return TargetPortfolioState(
        market_state=market_state,
        target_cash_ratio=allocation['target_cash_ratio'],
        target_hedge_ratio=allocation['target_hedge_ratio'],
        target_long_slots=allocation['target_long_slots'],
        target_symbols=target_symbols
    )

# --- C단계: 현금 집행 정책 (Cash Execution Policy) ---

"""
[MFU2 Phase 1: 현금 비중 정책 해석 정의]

이 섹션은 목표 현금 비중(target_cash_ratio)을 실제 매매 집행 시 어떻게 제약으로 해석할지 정의합니다.

정책 원칙:
1. Minimum Cash Buffer: target_cash_ratio는 계좌에서 '반드시 유지해야 하는 최소 현금 비율'로 해석합니다.
2. Buying Power 제한: 신규 매수 가능 금액(Buying Power)은 '현재 현금 - 필수 현금 버퍼'의 초과분으로 제한됩니다.
3. 보수적 집행: 현재 현금이 필수 버퍼보다 적을 경우, 추가 매수는 완전히 차단됩니다 (Buying Power = 0).
4. MFU2 1단계: 이 함수들은 정책을 '계산 가능'하게 만드는 helper이며, 실제 엔진(backtest_engine)과의 
   깊은 연결은 후속 단계에서 진행합니다.
"""

def calculate_required_cash_buffer(total_equity: float, target_cash_ratio: float) -> float:
    """
    [정책] 총 자산 대비 유지해야 할 최소 현금 버퍼 금액을 계산합니다.
    
    계산식: total_equity * target_cash_ratio
    """
    if total_equity <= 0:
        return 0.0
    return total_equity * max(0.0, min(1.0, target_cash_ratio))

def calculate_available_buying_power(
    current_cash: float, 
    total_equity: float, 
    target_cash_ratio: float,
    buffer_ratio: float = 0.02
) -> float:
    """
    [정책] 현재 현금과 목표 비중을 기반으로 실제 신규 매수 가능한 금액을 계산합니다.

    정책 해석:
    1. required_buffer = total_equity * target_cash_ratio
    2. available_buying_power = max(0, current_cash - required_buffer)
    3. 수동 주문 리스크 방어: 산출된 BP에서 buffer_ratio(기본 2%)만큼 추가로 제외하여 
       장중 가격 변동에 의한 주문 거부를 방지합니다.
    """
    if total_equity <= 0:
        return 0.0

    required_buffer = calculate_required_cash_buffer(total_equity, target_cash_ratio)
    available = current_cash - required_buffer

    # 버퍼 적용 (예: 2% 여유 현금 남김)
    safe_available = available * (1.0 - buffer_ratio)

    return max(0.0, safe_available)

def get_cash_policy_status(
    current_cash: float,
    total_equity: float,
    target_cash_ratio: float
) -> Dict[str, Any]:
    """
    [정책] 현금 정책 준수 현황을 종합하여 반환합니다. (로깅 및 판단용)
    """
    required_buffer = calculate_required_cash_buffer(total_equity, target_cash_ratio)
    buying_power = calculate_available_buying_power(current_cash, total_equity, target_cash_ratio)
    
    current_cash_ratio = current_cash / total_equity if total_equity > 0 else 1.0
    is_violating_buffer = current_cash < required_buffer
    
    return {
        'total_equity': total_equity,
        'current_cash': current_cash,
        'current_cash_ratio': current_cash_ratio,
        'target_cash_ratio': target_cash_ratio,
        'required_cash_buffer': required_buffer,
        'available_buying_power': buying_power,
        'is_violating_buffer': is_violating_buffer
    }


def compare_symbol_sets(current: List[str], target: List[str]) -> Dict[str, Any]:
    """
    [정책 명세] 현재 보유 종목과 목표 종목 구성을 비교합니다.
    
    정책:
    - 종목의 순서 차이는 리밸런싱 사유로 보지 않습니다. (순수한 집합 구성 비교)
    - 추가될 종목(added)과 제거될 종목(removed)을 반환합니다.
    """
    curr_set = set(current)
    targ_set = set(target)
    
    added = sorted(list(targ_set - curr_set))
    removed = sorted(list(curr_set - targ_set))
    
    return {
        'added': added,
        'removed': removed,
        'changed': len(added) > 0 or len(removed) > 0
    }

def compare_ratio(current: float, target: float, tolerance: float) -> Dict[str, Any]:
    """
    [정책 명세] 현재 비중과 목표 비중의 차이를 허용 오차 범위 내에서 비교합니다.
    
    정책:
    - abs(target - current) > tolerance 일 때만 유의미한 차이(deviation)로 간주합니다.
    - 정밀한 부동소수점 비교를 위해 '>' 대신 미세 오차를 고려할 수 있으나, 
      현재는 단순 '>' 기준을 적용합니다.
    """
    diff = target - current
    is_deviated = abs(diff) > tolerance
    return {
        'diff': diff,
        'is_deviated': is_deviated
    }

def evaluate_rebalance_need(
    current_state: CurrentPortfolioState,
    target_state: TargetPortfolioState,
    config: Optional[Dict[str, Any]] = None
) -> RebalanceDecision:
    """
    [정책 명세] 현재 포트폴리오 상태와 목표 상태를 비교하여 리밸런싱 필요 여부와 사유를 판정합니다.
    
    판정 기준:
    1. 종목 구성 차이 (SYMBOL_SET_CHANGED): 보유 종목 집합이 목표 종목 집합과 다를 때
    2. 현금 비중 이탈 (CASH_RATIO_DEVIATION): 현재 현금 비중이 목표와 허용 오차 이상 차이날 때
    3. 헤지 비중 이탈 (HEDGE_RATIO_DEVIATION): 현재 헤지 비중이 목표와 허용 오차 이상 차이날 때
    
    허용 오차 정책:
    - config 내 'cash_ratio_tolerance', 'hedge_ratio_tolerance'를 우선 참조
    - 없을 경우 fallback: 0.05 (5%) 적용
    """
    config = config or {}
    cash_tol = config.get('cash_ratio_tolerance', 0.05)
    hedge_tol = config.get('hedge_ratio_tolerance', 0.05)
    
    rebalance_needed = False
    rebalance_reasons = []
    
    # 1. 종목 비교
    sym_diff = compare_symbol_sets(current_state.current_symbols, target_state.target_symbols)
    if sym_diff['changed']:
        rebalance_needed = True
        rebalance_reasons.append("SYMBOL_SET_CHANGED")
        
    # 2. 현금 비중 비교
    cash_comp = compare_ratio(current_state.current_cash_ratio, target_state.target_cash_ratio, cash_tol)
    if cash_comp['is_deviated']:
        rebalance_needed = True
        rebalance_reasons.append("CASH_RATIO_DEVIATION")
        
    # 3. 헤지 비중 비교
    hedge_comp = compare_ratio(current_state.current_hedge_ratio, target_state.target_hedge_ratio, hedge_tol)
    if hedge_comp['is_deviated']:
        rebalance_needed = True
        rebalance_reasons.append("HEDGE_RATIO_DEVIATION")
        
    return RebalanceDecision(
        rebalance_needed=rebalance_needed,
        rebalance_reason=rebalance_reasons,
        symbol_diff_added=sym_diff['added'],
        symbol_diff_removed=sym_diff['removed'],
        cash_ratio_diff=cash_comp['diff'],
        hedge_ratio_diff=hedge_comp['diff']
    )
