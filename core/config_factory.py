from core.portfolio_config import PORTFOLIO_CONFIG
import config

def make_config(params: dict, start_date: str, end_date: str, fast_mode: bool = False):
    """
    기존 PORTFOLIO_CONFIG를 기반으로, 
    1) global config.py의 최신 값 (patch_global_config 반영됨)을 덮어쓰고
    2) 개별 최적화 파라미터(params)를 최종 적용하여 
    완전한 실행용 Config를 생성합니다.
    """
    cfg = PORTFOLIO_CONFIG.copy()
    
    # 1. Global config.py의 주요 설정 동기화 (특히 Hedge 및 Safety 관련)
    # 이 부분은 config.py에 있는 값이 PORTFOLIO_CONFIG보다 우선순위를 갖게 합니다.
    sync_keys = [
        'USE_HEDGE_MODE', 'HEDGE_TICKERS', 'HEDGE_ASSET', 
        'HEDGE_RATIO_BEAR', 'HEDGE_RATIO_PANIC', 'HEDGE_LIQUIDATION_PRIORITY', 
        'MIN_MODE_MAINTAIN_DAYS',
        'USE_CIRCUIT_BREAKER', 'USE_MA_CROSS', 'USE_MARKET_BREADTH', 
        'USE_DRAWDOWN_TRIGGER', 'USE_VIX_BREAKOUT'
    ]
    
    for key in sync_keys:
        if hasattr(config, key):
            cfg[key] = getattr(config, key)

    # 2. 최적화 파라미터 덮어쓰기 (가장 높은 우선순위)
    cfg.update(params)
    
    # 3. 필수 실행 환경 설정
    cfg["start_date"] = start_date
    cfg["end_date"] = end_date

    if fast_mode:
        cfg["_fast_mode"] = True
        cfg["use_market_regime"] = False
        cfg["target_tickers"] = ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA"]

    return cfg
