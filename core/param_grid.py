# ==========================================
# 📊 최적화 파라미터 그리드 (범주 C: Opt Params)
# ==========================================
# Optimizer가 탐색할 변수 후보군을 정의합니다.
# 여기에 정의된 값은 PORTFOLIO_CONFIG 및 config.py의 기본값을 덮어씁니다.

params_grid = {
    # 1. 핵심 진입/청산 전략
    'entry_period': [20],       # 진입(신고가) 기준일
    'exit_period': [10],        # 익절/손절 기준일
    'rs_lookback': [30],        # RS(상대강도) 비교 기간

    # 2. 포트폴리오 운용 비중
    'max_positions': [5],       # 최대 보유 종목 수
    'score_threshold': [1.5],   # 진입 점수 문턱

    # 3. 전략 가중치
    'rs_weight': [1.0],         # RS 점수 가중치
    'turtle_weight': [1.0],     # 터틀(신고가) 전략 가중치
    
    # 4. 리스크 관리
    'trailing_stop_multiplier': [2.5], # ATR 기반 트레일링 스탑 배수

    # 5. 보조지표 기간 (필요 시 그리드 추가)
    'atr_period': [20],
    'rsi_period': [14],
    'sma_short_period': [50],
    'sma_long_period': [200],
}
