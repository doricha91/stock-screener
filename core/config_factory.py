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
        # 리밸런싱 관련
        'REBALANCE_FREQUENCY',
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

def get_regime_config(current_regime: str, base_config: dict) -> dict:
    """
    현재 국면(current_regime)에 맞춰 base_config를 덮어씌워(Override) 반환합니다.
    (AGENTS.md SSOT 준수: 데이터는 config.REGIME_RULES에서 가져옴)
    """
    # 1. 원본 설정 복사 (Side-effect 방지)
    new_config = base_config.copy()
    
    # 2. 해당 국면의 설정 가져오기 (config.py의 REGIME_RULES 참조)
    regime_rules = getattr(config, 'REGIME_RULES', {})
    
    # 명칭 호환성 처리 (SIDEWAY -> RANGE 등)
    target_key = current_regime
    if target_key not in regime_rules:
        if target_key == "SIDEWAY": target_key = "RANGE"
        else: target_key = "UNSTABLE"
        
    regime_params = regime_rules.get(target_key, regime_rules.get('UNSTABLE', {}))
    
    # 3. 파라미터 오버라이드
    for key, value in regime_params.items():
        if key == 'weights':
            # 가중치는 {strat}_weight 형태로 주입
            for strat, weight in value.items():
                new_config[f"{strat}_weight"] = weight
        elif key == 'description':
            continue # 설명 필드는 무시
        else:
            # 일반 설정값 (target_cash_ratio, SWITCHING_PREMIUM, trailing_stop_multiplier 등)
            new_config[key] = value
            
    return new_config
