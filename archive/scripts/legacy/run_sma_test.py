# [ 📄 run_sma_test.py (신규 파일) ]

import config
from run_backtest import run_single_backtest  # 리팩토링된 단일 실행 함수 임포트


def main_sma_test():
    """
    'SMA 골든 크로스' 전략을 'SPY' 종목에 대해 1회 실행합니다.
    (이 전략이 B&H를 이기는지 확인)
    """

    # --- 1. 테스트할 종목 및 전략 설정 ---
    SYMBOL_TO_TEST = 'SPY'  # (대형주 지수 ETF)
    STRATEGY_NAME = 'sma'  # (★) 실행할 전략 이름

    print("=" * 50)
    print(f"SMA 골든 크로스 전략 백테스트를 시작합니다.")
    print(f"대상 종목: {SYMBOL_TO_TEST}")
    print("=" * 50)

    # --- 2. 전략에 필요한 모든 설정값 로드 ---
    # (run_single_backtest가 모든 키를 필요로 하므로,
    #  터틀/RSI/SMA 설정값을 모두 로드합니다)
    context = {
        'strategy_name': STRATEGY_NAME,
        'symbol': SYMBOL_TO_TEST,
        'initial_capital': 10000.0,
        'output_size': 'full',

        # (터틀 설정)
        'entry_period': config.TURTLE_ENTRY_PERIOD,
        'exit_period': config.TURTLE_EXIT_PERIOD,
        'atr_period': config.ATR_PERIOD,

        # (RSI 설정)
        'rsi_period': config.RSI_PERIOD,
        'rsi_oversold': config.RSI_OVERSOLD,
        'rsi_overbought': config.RSI_OVERBOUGHT,

        # (SMA 설정) - SMA 지표/신호 함수가 사용할 값
        'sma_short_period': config.SMA_SHORT_PERIOD,
        'sma_long_period': config.SMA_LONG_PERIOD,

        # (리스크/엔진 설정) - SMA 전략에도 동일하게 적용
        'risk_percent': config.RISK_PER_TRADE_PERCENT,
        'stop_loss_atr': config.STOP_LOSS_ATR_MULTIPLIER
    }

    # --- 3. 단일 백테스트 실행 ---
    run_single_backtest(context)

    print("=" * 50)
    print("SMA 전략 백테스트 완료.")
    print(f"결과는 {config.BACKTEST_DB_NAME} 파일에 저장되었습니다.")
    print("=" * 50)


if __name__ == "__main__":
    main_sma_test()