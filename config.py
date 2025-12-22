import os
from dotenv import load_dotenv

load_dotenv()

ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# 2. Screener Settings
MIN_MARKET_CAP = 10_000_000_000 # 최소 시가총액 (예: 100억 달러)
MIN_VOLUME_AVG = 10_000_000 # 최소 일평균 거래대금 (예: 1천만 달러)

# 3. Strategy Settings
TURTLE_ENTRY_PERIOD = 20 # 진입 신호 (예: 20일 신고가)
TURTLE_EXIT_PERIOD = 10 # 청산 신호 (예: 10일 신저가)
ATR_PERIOD = 20 # ATR 계산 기간

# 4. Screener Target List
TICKER_LIST = [
    'AAPL', # Apple
    'MSFT', # Microsoft
    'GOOGL', # Google
    'AMZN', # Amazon
    'TSLA', # Tesla
    'NVDA', # Nvidia
    'META', # Meta
    'JPM', # JPMorgan Chase
    'JNJ', # Johnson & Johnson
    'V', # Visa
]

# 5. Backtesting Settings
# (총 자본 대비) 한 번의 거래에서 감수할 최대 손실 비율
RISK_PER_TRADE_PERCENT = 0.01  # (예: 1%)

# (N = ATR) 1주당 손절폭(리스크)을 ATR의 몇 배로 잡을 것인가
STOP_LOSS_ATR_MULTIPLIER = 2.0  # (예: 2N = 2 * ATR)

# 6. Database Settings
BACKTEST_DB_NAME = 'backtest_log.db'

# 7. RSI Strategy Settings
RSI_PERIOD = 14       # RSI 계산 기간 (표준: 14)
RSI_OVERSOLD = 30     # 과매도 기준 (이하 매수)
RSI_OVERBOUGHT = 70    # 과매수 기준 (이상 매도)

# 8. SMA Golden Cross Strategy Settings
SMA_SHORT_PERIOD = 50
SMA_LONG_PERIOD = 200

# 9. Bollinger Bands Strategy Settings
BBANDS_PERIOD = 20
BBANDS_STD_DEV = 2.0  # 표준편차 (Standard Deviation)

# 10. MACD Crossover Strategy Settings
MACD_FAST_PERIOD = 12
MACD_SLOW_PERIOD = 26
MACD_SIGNAL_PERIOD = 9

# 11. Bollinger Bands Squeeze Strategy Settings
# (기존 BBANDS_PERIOD, BBANDS_STD_DEV와 공용으로 사용 가능하나,
#  전략별로 파라미터를 분리하는 것이 명확할 수 있습니다.)
BBS_PERIOD = 20        # 스퀴즈 전략용 BB 기간
BBS_STD_DEV = 2.0      # 스퀴즈 전략용 BB 표준편차
BBS_SQUEEZE_PERIOD = 120 # 밴드폭(BBW)이 N일 중 최저인지 확인하는 기간

# 12. DEMA/TEMA Crossover Strategy Settings
# (DEMA, TEMA 전략 모두 이 값을 공용으로 사용할 수 있습니다)
DEMA_SHORT_PERIOD = 20
DEMA_LONG_PERIOD = 50

# 13. Data Partitioning (OOS 검증용)
# 훈련 데이터 (In-Sample): 여기서 규칙을 찾습니다.
IN_SAMPLE_START = '2015-01-01'
IN_SAMPLE_END = '2020-12-31'

# 검증 데이터 (Out-of-Sample): 여기서 규칙을 검증합니다. (절대 훈련에 쓰면 안 됨)
OUT_OF_SAMPLE_START = '2021-01-01'
OUT_OF_SAMPLE_END = '2025-12-16' # 혹은 현재 날짜까지

# 14. Market Regime Definitions (시장 상태 정의)
# 시장의 기준이 되는 벤치마크 심볼
MARKET_BENCHMARK_SYMBOL = 'SPY'

# 추세 판단용 SMA (이동평균선)
REGIME_SMA_PERIOD = 200

# 추세 강도 판단용 ADX (Average Directional Index)
# ADX가 낮으면 '횡보', 높으면 '추세(상승/하락)'
REGIME_ADX_PERIOD = 14
REGIME_ADX_THRESHOLD = 25

# 15. Optimization Parameter Grids (v4.0 연구소용)
# 각 전략별로 테스트해볼 파라미터 후보군을 정의합니다.
# (너무 많은 숫자를 넣으면 계산 시간이 기하급수적으로 늘어나니 주의하세요!)

# 1) MACD 전략 그리드
# - fast/slow 조합을 통해 "더 민감한 신호"와 "더 둔감한 신호"를 비교합니다.
MACD_GRID = {
    'macd_fast_period': [3, 6, 8, 12],     # (기본 12) 빠름/표준/느림
    'macd_slow_period': [15, 20, 30, 40],    # (기본 26)
    'macd_signal_period': [6, 9, 12]            # (기본 9) 고정 (복잡도 감소)
}
# -> 총 조합 수: 3 x 3 x 1 = 9가지

# 2) DEMA 전략 그리드
# - 강세장에서 추세를 얼마나 빨리/깊게 탈 것인지 테스트합니다.
DEMA_GRID = {
    'dema_short_period': [3, 5, 10, 20, 30],
    'dema_long_period': [30, 50, 70]
}
# -> 총 조합 수: 3 x 3 = 9가지

# 3) Bollinger Bands Squeeze (BBS) 그리드
# - 핵심은 'squeeze_period'입니다. "얼마나 오랫동안 힘을 응축한 종목이 크게 터지는가?"를 찾습니다.
BBS_GRID = {
    'bbs_period': [10, 20, 30],                  # 표준값 고정
    'bbs_std_dev': [1.0, 2.0, 3.0],                # 표준값 고정
    'bbs_squeeze_period': [10, 20, 30] # 일
}
# -> 총 조합 수: 3가지

# 4) SMA 골든크로스 그리드
# - 초강세장에서 쓸 "가장 묵직한 추세선"을 찾습니다.
SMA_GRID = {
    'sma_short_period': [10, 20, 50],
    'sma_long_period': [100, 150, 200]
}
# -> 총 조합 수: 2 x 2 = 4가지

# 5) 터틀 트레이딩 그리드
# - 진입 시점을 짧게 잡을지(20일), 길게 잡을지(50일) 테스트합니다.
TURTLE_GRID = {
    'entry_period': [10, 20, 50],
    'exit_period': [5, 10, 20],
    'atr_period': [5, 10, 20]
}
# -> 총 조합 수: 2 x 2 x 1 = 4가지


# ★ 전략 그리드 매핑 (오토메이션을 위해 필수)
# run_optimization.py 에서 전략 이름만으로 그리드를 찾기 위해 사용합니다.
STRATEGY_GRID_MAP = {
    'macd': MACD_GRID,
    'dema': DEMA_GRID,
    'bbs': BBS_GRID,
    'sma': SMA_GRID,
    'turtle': TURTLE_GRID,
    # 'bbands', 'rsi' 등도 필요하면 추가 가능
}