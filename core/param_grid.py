params_grid = {
    # Best Known Parameter:
    # exit:15, rs_lookback:30, entry_period:20, max_positions:5, rs_weight:1.0, score_threshold:1.5, turtle weight: 1.0
    # [1] 핵심 변수
    'exit_period': [10],  # 익절/손절 기준일 (기본값: 10)
    'rs_lookback': [30],  # RS(상대강도) 비교 기간 (기본값: 120)
    'entry_period': [20],  # 진입(신고가) 기준일 (기본값: 20)
    'max_positions': [5],  # 최대 보유 종목 수 (기본값: 4)

    # [NEW] 트레일링 스탑 설정 (PortfolioDB 기능 활용)
    'trailing_stop_multiplier': [2.5], # ATR의 N배만큼 하락하면 이익 실현/손절

    # [2] 필터링 및 핵심 가중치
    'score_threshold': [1.5],  # 진입 점수 문턱 (기본값: 1.0)
    'rs_weight': [1.0],  # RS 점수 가중치 (기본값: 3.0)
    'turtle_weight': [1.0],  # 터틀(신고가) 전략 가중치 (기본값: 1.0)

    # [3] 추가 전략 가중치 (실험 시 주석 해제하여 사용)
    # -----------------------------------------------------------
    # 'rsi_weight': [1.0],       # RSI(과매도/과매수) 전략 가중치 (기본값: 1.0)
    # 'sma_weight': [1.0],       # SMA(골든크로스) 전략 가중치 (기본값: 1.0)
    # 'bbands_weight': [1.0],    # 볼린저밴드(역추세) 전략 가중치 (기본값: 1.0)
    # 'macd_weight': [1.0],      # MACD(추세반전) 전략 가중치 (기본값: 1.0)
    # 'bbs_weight': [1.0],       # BBS(볼린저 스퀴즈) 전략 가중치 (기본값: 1.0)
    # 'dema_weight': [1.0],      # DEMA(이중지수이동평균) 전략 가중치 (기본값: 1.0)
    # 'obv_weight': [0.5],       # OBV(거래량 추세) 보조점수 (기본값: 0.5)
    # 'mfi_weight': [0.5],       # MFI(자금흐름) 보조점수 (기본값: 0.5)
    # 'vol_spike_weight': [0.5], # 거래량 폭발 보조점수 (기본값: 0.5)
    # -----------------------------------------------------------

    # [4] 보조지표 세부 설정
    'atr_period': [20],  # 변동성(ATR) 계산 기간 (기본값: 20)
    'rsi_period': [14],  # RSI 계산 기간 (기본값: 14)
    'mfi_period': [14],  # MFI 계산 기간 (기본값: 14)
    'sma_short_period': [50],  # 단기 이평선 기간 (기본값: 50)
    'sma_long_period': [200],  # 장기 이평선 기간 (기본값: 200)


    # [5] 최적화 실험용 그리드 (필요시 주석 해제)
    # 'atr_period': [14, 20, 30],
    # 'rsi_period': [9, 14, 21],
    # 'sma_short_period': [20, 50, 60],
    # 'sma_long_period': [150, 200, 250],
}
