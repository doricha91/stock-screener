import copy
from core.portfolio_config import PORTFOLIO_CONFIG
import config

# 동적 라우팅을 허용할 핵심 파라미터 화이트리스트 (보안 및 오염 방지)
ALLOWED_ROUTING_PARAMS = [
    'target_cash_ratio',
    'hedge_ratio',
    'switching_premium',
    'SWITCHING_PREMIUM',
    'score_threshold',
    'trailing_stop_multiplier',
    'ALLOW_PROFIT_SWITCH',
    'SWITCHING_MAX_COUNT',
    'MIN_MODE_MAINTAIN_DAYS',
    'HEDGE_LIQUIDATION_PRIORITY',
    # 전략별 가중치 (Weights)
    'turtle_weight', 'rsi_weight', 'sma_weight', 'bbands_weight', 
    'macd_weight', 'bbs_weight', 'dema_weight', 
    'obv_weight', 'mfi_weight', 'vol_spike_weight', 'rs_weight'
]


def make_config(params: dict, start_date: str, end_date: str, fast_mode: bool = False, runtime_overrides: dict = None):
    """
    유일한 실행용 Config 생성 지점 (SSOT).
    """
    cfg = PORTFOLIO_CONFIG.copy()

    # 1. Global config.py의 주요 설정 동기화
    sync_keys = [
        'USE_HEDGE_MODE', 'HEDGE_TICKERS', 'HEDGE_ASSET',
        'HEDGE_RATIO_BEAR', 'HEDGE_RATIO_PANIC', 'HEDGE_LIQUIDATION_PRIORITY',
        'MIN_MODE_MAINTAIN_DAYS', 'ALLOW_PROFIT_SWITCH', 'SWITCHING_MAX_COUNT',
        'USE_CIRCUIT_BREAKER', 'USE_MA_CROSS', 'USE_MARKET_BREADTH',
        'USE_DRAWDOWN_TRIGGER', 'USE_VIX_BREAKOUT',
        'CB_DROP_THRESHOLD', 'CB_COOLDOWN_DAYS', 'MA_CROSS_FAST', 'MA_CROSS_SLOW',
        'BREADTH_THRESHOLD', 'BREADTH_OVERSOLD_THRESHOLD', 'DD_LOOKBACK', 'DD_THRESHOLD',
        'VIX_MA_PERIOD', 'VIX_MULTIPLIER',
        'MARKET_BENCHMARK_SYMBOL', 'REGIME_SMA_PERIOD', 'REGIME_SMA_SHORT_PERIOD',
        'REGIME_ADX_PERIOD', 'REGIME_ADX_THRESHOLD', 'REGIME_RULES',
        'REBALANCE_FREQUENCY', 'enable_decision_logging'
    ]

    for key in sync_keys:
        if hasattr(config, key):
            cfg[key] = getattr(config, key)

    if 'REGIME_RULES' in cfg:
        cfg['REGIME_RULES'] = copy.deepcopy(cfg['REGIME_RULES'])
    else:
        cfg['REGIME_RULES'] = {}

    valid_regimes = list(cfg['REGIME_RULES'].keys())

    # 2. 파라미터 통합
    overrides_to_apply = {}
    if params: overrides_to_apply.update(params)
    if runtime_overrides: overrides_to_apply.update(runtime_overrides)

    # 3. 파라미터 적용 및 동적 라우팅
    for key, value in overrides_to_apply.items():
        is_routed = False
        key_upper = key.upper()

        for regime in valid_regimes:
            prefix = f"{regime}_"
            if key_upper.startswith(prefix):
                param_name = key[len(prefix):]
                
                # 대소문자 무시하고 화이트리스트 일치 항목 찾기
                match = next((p for p in ALLOWED_ROUTING_PARAMS if p.lower() == param_name.lower()), None)
                
                if not match:
                    raise ValueError(f"[라우팅 오류] 허용되지 않은 국면 변수이거나 오타가 발생했습니다: '{key}'")

                cfg['REGIME_RULES'][regime][match] = value
                is_routed = True
                break

        if not is_routed:
            cfg[key] = value

    cfg["start_date"] = start_date
    cfg["end_date"] = end_date
    if fast_mode:
        cfg["_fast_mode"] = True
        cfg["use_market_regime"] = False
        cfg["target_tickers"] = ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA"]
    else:
        if "use_market_regime" not in cfg: cfg["use_market_regime"] = True

    return cfg


def get_regime_config(current_regime: str, base_config: dict) -> dict:
    """
    현재 국면(current_regime)에 맞춰 base_config를 덮어씌워 반환합니다.
    """
    new_config = base_config.copy()
    regime_rules = base_config.get('REGIME_RULES', getattr(config, 'REGIME_RULES', {}))

    target_key = current_regime
    if target_key not in regime_rules:
        target_key = "UNSTABLE"

    regime_params = regime_rules.get(target_key, regime_rules.get('UNSTABLE', {}))

    # 3. 국면 특화 파라미터 오버라이드
    for key, value in regime_params.items():
        if key == 'weights':
            for strat, weight in value.items():
                new_config[f"{strat}_weight"] = weight
        elif key == 'description':
            continue
        else:
            # [Case-Agnostic Injection] 엔진이 대소문자 무엇을 쓰든 반영되도록 이중/삼중 주입
            new_config[key] = value
            new_config[key.upper()] = value
            new_config[key.lower()] = value

    return new_config