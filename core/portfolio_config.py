# ==========================================
# ⚙️ 포트폴리오 설정 (기본값)
# ==========================================
# 이 값은 참고용일 뿐, 실제 실행 시에는 외부에서 주입된 config가 사용됩니다.
PORTFOLIO_CONFIG = {
    'initial_capital': 100000.0,
    'risk_per_trade': 0.05,
    'max_positions': 5,
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

    # 능동적 스위칭 (MFU 5)
    'SWITCHING_PREMIUM': 1.0,
    'ALLOW_PROFIT_SWITCH': False,
    'SWITCHING_MAX_COUNT': 2,

    # [Legacy/Moved] 전역 정책 관련 설정은 config.py에서 관리합니다.
    # PORTFOLIO_CONFIG는 포트폴리오 기본 구조 및 백테스트 실행을 위한 기본값만 정의합니다.
}