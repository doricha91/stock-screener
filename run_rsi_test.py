# [ 📄 run_rsi_test.py (신규 파일) ]

import config
from run_backtest import run_single_backtest  # 리팩토링된 단일 실행 함수 임포트


def main_rsi_test():
    """
    'RSI' 전략을 'SPY' 종목에 대해 1회 실행합니다.
    (터틀 전략이 아닌 RSI 전략이 B&H를 이기는지 확인)
    """

    # --- 1. 테스트할 종목 및 전략 설정 ---
    SYMBOL_TO_TEST = 'SPY'  # (대형주 지수 ETF)
    STRATEGY_NAME = 'rsi'  # (★) 실행할 전략 이름

    print("=" * 50)
    print(f"RSI 전략 백테스트를 시작합니다.")
    print(f"대상 종목: {SYMBOL_TO_TEST}")
    print("=" * 50)

    # --- 2. 전략에 필요한 모든 설정값 로드 ---
    # (run_single_backtest가 모든 키를 필요로 하므로,
    #  터틀/RSI 설정값을 모두 로드합니다)
    context = {
        'strategy_name': STRATEGY_NAME,
        'symbol': SYMBOL_TO_TEST,
        'initial_capital': 10000.0,
        'output_size': 'full',

        # (터틀 설정) - 사용되진 않지만, 로깅 등을 위해 전달
        'entry_period': config.TURTLE_ENTRY_PERIOD,
        'exit_period': config.TURTLE_EXIT_PERIOD,
        'atr_period': config.ATR_PERIOD,

        # (RSI 설정) - RSI 지표/신호 함수가 사용할 값
        'rsi_period': config.RSI_PERIOD,
        'rsi_oversold': config.RSI_OVERSOLD,
        'rsi_overbought': config.RSI_OVERBOUGHT,

        # (리스크/엔진 설정) - RSI 전략에도 동일하게 적용해볼 값
        'risk_percent': config.RISK_PER_TRADE_PERCENT,
        'stop_loss_atr': config.STOP_LOSS_ATR_MULTIPLIER
    }

    # --- 3. 단일 백테스트 실행 ---
    run_single_backtest(context)

    print("=" * 50)
    print("RSI 전략 백테스트 완료.")
    print(f"결과는 {config.BACKTEST_DB_NAME} 파일에 저장되었습니다.")
    print("=" * 50)


if __name__ == "__main__":
    main_rsi_test()