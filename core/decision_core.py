from __future__ import annotations
import pandas as pd

def compute_candidate_score(row: pd.Series, weights: dict[str, float]) -> tuple[float, list[str]]:
    """
    단일 데이터 스냅샷(pd.Series)을 받아 전략별 가중치 합산 점수를 계산합니다.
    
    Args:
        row: 기술적 지표 및 신호가 포함된 단일 행 데이터. (예: df.iloc[-1])
        weights: 전략명을 키로, 가중치를 값으로 가지는 딕셔너리.
        
    Returns:
        tuple[float, list[str]]: (합산 점수, 발생한 전략 리스트)
    """
    total_score = 0.0
    triggered_strategies: list[str] = []

    for strategy_name, weight in weights.items():
        col_name = f"signal_{strategy_name}"
        # 해당 전략의 신호 컬럼이 존재하고 값이 1(매수 신호)인 경우 점수 합산
        if col_name in row and row[col_name] == 1:
            total_score += weight
            triggered_strategies.append(strategy_name)

    return total_score, triggered_strategies

def is_enterable_candidate(score: float, threshold: float, regime: str) -> bool:
    """
    계산된 점수와 시장 국면을 바탕으로 신규 진입 가능 여부를 판단합니다.
    
    Args:
        score: compute_candidate_score에서 계산된 점수.
        threshold: 진입을 위한 최소 점수 임계값.
        regime: 현재 시장 국면 (예: BULL, BEAR, PANIC 등)
        
    Returns:
        bool: 진입 가능 여부
    """
    # 1. PANIC 국면인 경우 무조건 진입 불가 (대소문자 무시)
    if regime.upper() == "PANIC":
        return False
    
    # 2. 점수가 임계값 이상인지 확인
    if score < threshold:
        return False
        
    return True
