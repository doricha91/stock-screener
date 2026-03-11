from core.portfolio_config import PORTFOLIO_CONFIG
import config

def make_config(params: dict, start_date: str, end_date: str, fast_mode: bool = False, runtime_overrides: dict = None):
    """
    유일한 실행용 Config 생성 지점 (SSOT).
    병합 순서 (뒤로 갈수록 우선순위 높음):
    1. PORTFOLIO_CONFIG (기본 구조)
    2. config.py (전역 정책 및 기본값)
    3. params (최적화 대상 파라미터)
    4. runtime_overrides (실행 시점 강제값)
    """
    cfg = PORTFOLIO_CONFIG.copy()
    
    # 1. Global config.py의 주요 설정 동기화 (전역 정책)
    sync_keys = [
        # Hedge 관련
        'USE_HEDGE_MODE', 'HEDGE_TICKERS', 'HEDGE_ASSET', 
        'HEDGE_RATIO_BEAR', 'HEDGE_RATIO_PANIC', 'HEDGE_LIQUIDATION_PRIORITY', 
        'MIN_MODE_MAINTAIN_DAYS',
        # Safety 관련
        'USE_CIRCUIT_BREAKER', 'USE_MA_CROSS', 'USE_MARKET_BREADTH', 
        'USE_DRAWDOWN_TRIGGER', 'USE_VIX_BREAKOUT',
        # Market Regime 및 기타 정책
        'MARKET_BENCHMARK_SYMBOL', 'REGIME_SMA_PERIOD', 'REGIME_ADX_PERIOD', 'REGIME_RULES',
        # Logging 관련
        'enable_decision_logging'
    ]
    
    for key in sync_keys:
        if hasattr(config, key):
            cfg[key] = getattr(config, key)

    # 2. 최적화 파라미터 적용 (C범주)
    cfg.update(params)
    
    # 3. 런타임 오버라이드 및 환경 설정 (D범주)
    if runtime_overrides:
        cfg.update(runtime_overrides)

    cfg["start_date"] = start_date
    cfg["end_date"] = end_date
    
    # fast_mode 설정 (환경 변수 및 정책 강제)
    if fast_mode:
        cfg["_fast_mode"] = True
        cfg["use_market_regime"] = False
        cfg["target_tickers"] = ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA"]
    else:
        # 기본적으로 market regime 사용 (정책상 기본값)
        if "use_market_regime" not in cfg:
            cfg["use_market_regime"] = True

    return cfg
