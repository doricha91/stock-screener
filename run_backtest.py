# [ 📄 run_backtest.py (4대 전략 추가 수정본) ]

import data_manager
import indicator
import strategy
import config
import pandas as pd

# 백테스팅 패키지에서 모듈들을 import
from backtesting import engine, metrics, report, logger

# --- 전략 맵(MAP) 정의 ---
INDICATOR_FUNCTIONS = {
    'turtle': indicator.add_turtle_indicators,
    'rsi': indicator.add_rsi_indicators,
    'sma': indicator.add_sma_indicators,
    # --- [ (신규) 4개 전략 함수 매핑 추가 ] ---
    'bbands': indicator.add_bollinger_band_indicators,
    'macd': indicator.add_macd_indicators,
    'bbs': indicator.add_bbs_indicators,
    'dema': indicator.add_dema_indicators,
}

SIGNAL_FUNCTIONS = {
    'turtle': strategy.generate_turtle_signals,
    'rsi': strategy.generate_rsi_signals,
    'sma': strategy.generate_sma_signals,
    # --- [ (신규) 4개 전략 함수 매핑 추가 ] ---
    'bbands': strategy.generate_bbands_signals,
    'macd': strategy.generate_macd_signals,
    'bbs': strategy.generate_bbs_signals,
    'dema': strategy.generate_dema_signals,
}


# ---------------------------------------------

def run_single_backtest(context):
    """
    하나의 설정값(context)을 받아 백테스트를 1회 실행합니다.
    (★) start_date, end_date가 context에 있으면 데이터를 필터링합니다.
    """

    # --- 1. 컨텍스트에서 설정값 추출 ---
    SYMBOL_TO_TEST = context.get('symbol', 'AAPL')
    INITIAL_CAPITAL = context.get('initial_capital', 10000.0)
    DATA_OUTPUT_SIZE = context.get('output_size', 'full')

    strategy_name = context.get('strategy_name', 'turtle')
    if strategy_name not in INDICATOR_FUNCTIONS or strategy_name not in SIGNAL_FUNCTIONS:
        print(f"오류: 알 수 없는 전략 이름 '{strategy_name}'. 백테스트를 종료합니다.")
        return

    # (로그용 파라미터 - 기존 코드 유지)
    entry_period = context.get('entry_period',
                               context.get('rsi_period',
                                           context.get('sma_short_period', '?')))

    # --- [ (★) 신규: 날짜 범위 추출 ] ---
    start_date = context.get('start_date', None)
    end_date = context.get('end_date', None)

    date_range_str = f" ({start_date} ~ {end_date})" if start_date and end_date else ""
    print(f"--- {SYMBOL_TO_TEST} 백테스트 시작 (전략: {strategy_name}{date_range_str}) ---")

    # --- 2. 데이터 준비 ---
    print("1/5: 데이터 로드 중...")
    df_raw = data_manager.get_stock_data(SYMBOL_TO_TEST, output_size=DATA_OUTPUT_SIZE)
    if df_raw is None:
        print(f"데이터 수집 실패. 백테스트를 종료합니다.")
        return

    # --- [ (★) 신규: 날짜 필터링 로직 ] ---
    # (데이터프레임 인덱스를 datetime으로 변환 (안전장치))
    try:
        df_raw.index = pd.to_datetime(df_raw.index)
    except Exception as e:
        print(f"데이터 인덱스 datetime 변환 오류: {e}")
        # (날짜 필터링이 안될 수 있으므로 원본 사용)

    if start_date and end_date:
        print(f"데이터 필터링 적용: {start_date} ~ {end_date}")
        df_filtered = df_raw.loc[start_date:end_date].copy()
        if df_filtered.empty:
            print(f"오류: {start_date} ~ {end_date} 범위에 데이터가 없습니다.")
            return
    else:
        df_filtered = df_raw.copy()
    # --------------------------------------

    # --- 3. 지표 계산 ---
    print("2/5: 기술적 지표 계산 중...")
    indicator_func = INDICATOR_FUNCTIONS[strategy_name]
    df_indicators = indicator_func(df_filtered, context)

    # --- 4. 매매 신호 생성 ---
    print("3/5: 매매 신호 생성 중...")
    signal_func = SIGNAL_FUNCTIONS[strategy_name]
    df_signals = signal_func(df_indicators, context)
    if df_signals is None:
        print(f"신호 생성 실패. 백테스트를 종료합니다.")
        return

    # --- 5. 가상 매매 시뮬레이션 ---
    print("4/5: 시뮬레이션 실행 중...")
    portfolio_history, trade_history = engine.run_backtest(df_signals, INITIAL_CAPITAL, context)

    # --- 6. 성과 통계 계산 ---
    print("5/5: 성과 통계 계산 중...")
    stats = metrics.calculate_metrics(portfolio_history, trade_history, df_signals, INITIAL_CAPITAL)

    # --- 7. 결과 로깅 ---
    print("결과 저장 중...")
    logger.log_backtest_result(context, stats)

    # --- 8. 결과 리포트 출력 ---
    print("\n--- 백테스트 결과 ---")
    report.show_console_report(stats, context)

    print("--------------------")
    print("백테스트 완료.")


# 이 파일(run_backtest.py)을 직접 실행했을 때:
if __name__ == "__main__":
    print(">>> 단일 백테스트 실행 (기본 설정값: 'turtle') <<<")

    # 1. config.py에서 기본 설정값 로드
    # (★수정★) 모든 전략의 파라미터를 context에 포함시킴
    default_context = {
        # (실행 설정)
        'strategy_name': 'turtle',  # (★) 실행할 전략 이름 (e.g., 'rsi', 'sma', 'bbands', 'macd', 'bbs', 'dema')
        'symbol': 'AAPL',
        'initial_capital': 10000.0,
        'output_size': 'full',

        # (리스크/엔진 설정 - 공용)
        'risk_percent': config.RISK_PER_TRADE_PERCENT,
        'stop_loss_atr': config.STOP_LOSS_ATR_MULTIPLIER,
        'atr_period': config.ATR_PERIOD,  # (공용)

        # (터틀 설정)
        'entry_period': config.TURTLE_ENTRY_PERIOD,
        'exit_period': config.TURTLE_EXIT_PERIOD,

        # (RSI 설정)
        'rsi_period': config.RSI_PERIOD,
        'rsi_oversold': config.RSI_OVERSOLD,
        'rsi_overbought': config.RSI_OVERBOUGHT,

        # (SMA 설정)
        'sma_short_period': config.SMA_SHORT_PERIOD,
        'sma_long_period': config.SMA_LONG_PERIOD,

        # --- [ (신규) 4개 전략 설정값 추가 ] ---

        # (볼린저 밴드 - 평균회귀 설정)
        'bbands_period': config.BBANDS_PERIOD,
        'bbands_std_dev': config.BBANDS_STD_DEV,

        # (MACD 설정)
        'macd_fast_period': config.MACD_FAST_PERIOD,
        'macd_slow_period': config.MACD_SLOW_PERIOD,
        'macd_signal_period': config.MACD_SIGNAL_PERIOD,

        # (볼린저 밴드 스퀴즈 설정)
        'bbs_period': config.BBS_PERIOD,
        'bbs_std_dev': config.BBS_STD_DEV,
        'bbs_squeeze_period': config.BBS_SQUEEZE_PERIOD,

        # (DEMA 설정)
        'dema_short_period': config.DEMA_SHORT_PERIOD,
        'dema_long_period': config.DEMA_LONG_PERIOD,
    }

    # 2. 단일 백테스트 함수 호출
    run_single_backtest(default_context)