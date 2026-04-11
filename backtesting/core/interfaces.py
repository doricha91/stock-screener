# backtesting/core/interfaces.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import datetime

class DataLoaderInterface(ABC):
    """
    [Phase 1] 과거 데이터를 안전하게 제공하는 인터페이스.
    미래 참조(Look-Ahead Bias)를 방지하기 위해 특정 시점(current_date)까지의 데이터만 반환합니다.
    """
    @abstractmethod
    def get_historical_data(self, symbol: str, current_date: datetime) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_market_regime(self, current_date: datetime) -> str:
        """해당 시점의 시장 국면(Regime)을 반환 (미래 VIX 데이터 참조 금지)"""
        pass

class VectorizedSignalGeneratorInterface(ABC):
    """
    [Phase 2] 전체 기간에 대한 시그널을 일괄 연산하여 성능을 극대화하는 인터페이스.
    """
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame, parameters: Dict[str, Any]) -> pd.DataFrame:
        """기술적 지표 및 진입/청산 시그널이 추가된 DataFrame 반환"""
        pass

class SimulatorInterface(ABC):
    """
    [Phase 2] 이벤트 드리븐(Event-driven) 방식으로 매일의 포트폴리오 상태를 갱신하는 시뮬레이터.
    """
    @abstractmethod
    def run(self, start_date: datetime, end_date: datetime, parameters: Dict[str, Any]) -> pd.DataFrame:
        """
        주어진 기간 동안 일별 포트폴리오 가치(Equity Curve)와 
        CurrentPortfolioState 로그를 담은 DataFrame 반환
        """
        pass

class OptimizerInterface(ABC):
    """
    [Phase 3] 전진 분석(Walk-Forward Optimization)을 수행하는 최적화 엔진.
    """
    @abstractmethod
    def optimize(self, param_grid: Dict[str, List[Any]]) -> Dict[str, Any]:
        """고원(Plateau) 탐색 알고리즘을 적용하여 최적 파라미터 반환"""
        pass
