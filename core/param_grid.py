# core/param_grid.py
"""
🔬 Stock Screener 전략 최적화 파라미터 그리드 정의 (ID 586 Reproduce Mode)
이 파일은 과거 최고 성과를 냈던 ID 586의 수치를 현재 엔진에서 재검증하기 위해 작성되었습니다.
모든 리스트를 1개로 고정하여 단일 백테스트를 수행합니다.
"""

params_grid = {
    # ------------------------------------------------------------------
    # ID 586 고정 파라미터 (Success Formula)
    # ------------------------------------------------------------------
    'entry_period': [12],
    'exit_period': [20],
    'rs_lookback': [30],
    'atr_period': [20],
    'rsi_period': [14],
    'mfi_period': [14],
    'sma_short_period': [50],
    'sma_long_period': [200],
    'score_threshold': [1.5],
    'trailing_stop_multiplier': [2.5],
    'max_positions': [10],
    'SWITCHING_PREMIUM': [1.0],
    'MIN_MODE_MAINTAIN_DAYS': [5],
    'HEDGE_LIQUIDATION_PRIORITY': ['rs_low'],

    # --- [국면별 설정 (ID 586 재현)] ---
    'BULL_target_cash_ratio': [0.05],
    'BULL_switching_premium': [1.0, 1.3, 1.5, 1.8],
    'BULL_score_threshold': [1.5, 1.8], # 586 당시 추정값
    'BULL_trailing_stop_multiplier': [4.0],

    'BEAR_target_cash_ratio': [0.7],
    'BEAR_score_threshold': [2.0],
    'BEAR_trailing_stop_multiplier': [1.5],

    'UNSTABLE_target_cash_ratio': [0.3],
    'UNSTABLE_score_threshold': [1.5],
    'PANIC_target_cash_ratio': [1.0],
    'PANIC_trailing_stop_multiplier': [0.5],
}

"""
[BACKUP: Full Matrix Grid]
기존의 방대한 그리드는 아래에 주석 처리하여 보존합니다.

params_grid_backup = {
    'entry_period': [12],
    'exit_period': [20],
    'rs_lookback': [30],
    'BULL_switching_premium': [0.2, 0.4, 0.6],
    'BULL_turtle_weight': [1.5, 2.0, 2.5],
    'BULL_score_threshold': [1.0, 1.3],
    'BULL_trailing_stop_multiplier': [3.5, 4.5],
    'BEAR_target_cash_ratio': [0.3, 0.5, 0.7],
    'BEAR_hedge_ratio': [0.3, 0.5],
    'BEAR_switching_premium': [2.0, 2.5],
    'UNSTABLE_target_cash_ratio': [0.3, 0.5, 0.7],
    'PANIC_switching_premium': [3.0, 4.0, 5.0],
    ... (나머지 전략 가중치 생략)
}
"""
