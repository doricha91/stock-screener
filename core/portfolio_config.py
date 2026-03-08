# ==========================================
# ⚙️ 포트폴리오 설정 (기본값)
# ==========================================
# 이 값은 참고용일 뿐, 실제 실행 시에는 외부에서 주입된 config가 사용됩니다.
PORTFOLIO_CONFIG = {
    'initial_capital': 100000.0,
    'risk_per_trade': 0.05,
    'max_positions': 4,
    'entry_period': 20,
    'exit_period': 10,
    'score_threshold': 1.0,

    # 가중치 변수들
    'turtle_weight': 1.0,
    'rs_weight': 3.0,
    'rsi_weight': 1.0,
    'sma_weight': 1.0,
    'bbands_weight': 1.0,
    'macd_weight': 1.0,
    'bbs_weight': 1.0,
    'dema_weight': 1.0,
    'obv_weight': 0.5,
    'mfi_weight': 0.5,
    'vol_spike_weight': 0.5,

    # 지표 기간
    'atr_period': 20,
    'rsi_period': 14,
    'sma_short_period': 50,
    'sma_long_period': 200,
    'bbands_period': 20,
    'macd_fast_period': 12,
    'macd_slow_period': 26,
    'dema_short_period': 20,
    'mfi_period': 14,
    'rs_lookback': 120,

    # 트레일링 스탑 설정
    'trailing_stop_multiplier': 2.5,

    # [신규] Hedge Mode 설정 (config.py와 연동)
    'USE_HEDGE_MODE': False,
    'HEDGE_ASSET': 'PSQ',
    'HEDGE_TICKERS': ['SH', 'SDS', 'SPXU', 'PSQ', 'QID', 'SQQQ', 'SOXS', 'BIL'],
    'HEDGE_RATIO_BEAR': 0.2,
    'HEDGE_RATIO_PANIC': 0.5,
    'HEDGE_LIQUIDATION_PRIORITY': 'rs_low',
    'MIN_MODE_MAINTAIN_DAYS': 5
}