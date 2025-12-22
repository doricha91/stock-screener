# [ 📄 run_dema_test.py (신규 파일) ]

import config
from run_backtest import run_single_backtest  # 리팩토링된 단일 실행 함수 임포트


def main_dema_test():
    """
    'DEMA 크로스오버' 전략을 'SPY' 종목에 대해 1회 실행합니다.
    (SMA 전략과 비교)
    """

    # --- 1. 테스트할 종목 및 전략 설정 ---
    SYMBOL_TO_TEST = 'SPY'  # (대형주 지수 ETF)
    STRATEGY_NAME = 'dema'  # (★) 실행할 전략 이름

    # --- (★) 신규: 테스트할 시장 구간 ---
    START_DATE = '2022-01-01'  # (하락장 시작)
    END_DATE = '2025-10-31'  # (하락장 종료)

    print("=" * 50)
    print(f"DEMA 크로스오버 전략 백테스트를 시작합니다.")
    print(f"대상 종목: {SYMBOL_TO_TEST}")
    print("=" * 50)

    # --- 2. 전략에 필요한 모든 설정값 로드 ---
    # (run_single_backtest가 모든 키를 필요로 하므로,
    #  config.py의 모든 파라미터를 로드합니다)
    context = {
        # (실행 설정)
        'strategy_name': STRATEGY_NAME,
        'symbol': SYMBOL_TO_TEST,
        'initial_capital': 10000.0,
        'output_size': 'full',

        # (리스크/엔진 설정 - 공용)
        'risk_percent': config.RISK_PER_TRADE_PERCENT,
        'stop_loss_atr': config.STOP_LOSS_ATR_MULTIPLIER,
        'atr_period': config.ATR_PERIOD, # (공용)

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

    # --- 3. 단일 백테스트 실행 ---
    run_single_backtest(context)

    print("=" * 50)
    print("DEMA 전략 백테스트 완료.")
    print(f"결과는 {config.BACKTEST_DB_NAME} 파일에 저장되었습니다.")
    print("=" * 50)


if __name__ == "__main__":
    main_dema_test()