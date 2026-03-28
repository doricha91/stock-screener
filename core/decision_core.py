from __future__ import annotations
import pandas as pd
import numpy as np

def compute_candidate_score(data: pd.Series | pd.DataFrame, weights: dict[str, float]) -> tuple[float | pd.Series, list[str]]:
    """
    데이터(Series 또는 DataFrame)를 받아 전략별 가중치 합산 점수를 계산합니다.
    (하이브리드: 스크리너 스칼라 연산 + 백테스터 벡터 연산 지원)
    """
    if isinstance(data, pd.DataFrame):
        # 1. DataFrame 벡터 연산 (백테스트용)
        # 신호값이 정확히 1인 경우에만 가중치를 부여하여 로직 왜곡 방지
        total_score = pd.Series(0.0, index=data.index)
        for strategy_name, weight in weights.items():
            col_name = f"signal_{strategy_name}"
            if col_name in data.columns:
                total_score += (data[col_name] == 1).astype(float) * weight
        return total_score, [] # 벡터 모드에서는 성능을 위해 전략 리스트 반환 생략
    
    else:
        # 2. Series 스칼라 연산 (스크리너용)
        total_score = 0.0
        triggered_strategies: list[str] = []
        for strategy_name, weight in weights.items():
            col_name = f"signal_{strategy_name}"
            if col_name in data and data[col_name] == 1:
                total_score += weight
                triggered_strategies.append(strategy_name)
        return total_score, triggered_strategies

def is_enterable_candidate(score: float | pd.Series, threshold: float, regime: str | pd.Series) -> bool | pd.Series:
    """
    점수와 시장 국면을 바탕으로 진입 가능 여부를 판단합니다.
    (하이브리드: 스칼라 및 벡터 논리 연산 지원)
    """
    if isinstance(score, pd.Series):
        # 1. 벡터 연산 처리
        if isinstance(regime, pd.Series):
            panic_mask = regime.str.upper() == "PANIC"
        else:
            panic_mask = (str(regime).upper() == "PANIC")
        return (score >= threshold) & (~panic_mask)
    
    else:
        # 2. 스칼라 연산 처리
        if str(regime).upper() == "PANIC":
            return False
        return score >= threshold
