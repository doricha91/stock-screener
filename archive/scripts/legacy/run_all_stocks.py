# [ 📄 run_all_stocks.py (신규 파일) ]

import config
from run_backtest import run_single_backtest  # 리팩토링된 단일 실행 함수 임포트
from tqdm import tqdm


def run_multi_stock_test():
    """
    config.py의 TICKER_LIST를 순회하며,
    '최적의 설정값'으로 다중 종목 백테스트를 실행합니다.
    """

    # --- 1. 테스트할 종목 리스트 ---
    # (config.py에 정의된 10개 종목 리스트)
    symbols_to_test = config.TICKER_LIST

    # --- 2. '최적의 설정값' 정의 ---
    # (방금 'AAPL' 최적화에서 찾은 값으로 고정)
    OPTIMAL_ENTRY_PERIOD = 20

    print("=" * 50)
    print(f"다중 종목 백테스트를 시작합니다. (총 {len(symbols_to_test)}개 종목)")
    print(f"적용할 전략: 터틀 (Entry: {OPTIMAL_ENTRY_PERIOD}일)")
    print("=" * 50)

    # --- 3. 기본 설정값 로드 (config.py에서) ---
    base_context = {
        'initial_capital': 10000.0,
        'output_size': 'full',
        'entry_period': OPTIMAL_ENTRY_PERIOD,  # (★) 고정된 최적값 사용
        'exit_period': config.TURTLE_EXIT_PERIOD,
        'atr_period': config.ATR_PERIOD,
        'risk_percent': config.RISK_PER_TRADE_PERCENT,
        'stop_loss_atr': config.STOP_LOSS_ATR_MULTIPLIER
    }

    # --- 4. 종목 리스트 순회 (tqdm 적용) ---
    for symbol in tqdm(symbols_to_test, desc="다중 종목 테스트 진행률"):
        # 4-1. 현재 루프의 종목으로 context 수정
        current_context = base_context.copy()
        current_context['symbol'] = symbol

        # 4-2. 단일 백테스트 실행
        run_single_backtest(current_context)

        print(f"\n{symbol} 테스트 완료.\n" + "-" * 50)

    print("=" * 50)
    print("다중 종목 백테스트 완료.")
    print(f"모든 결과는 {config.BACKTEST_DB_NAME} 파일에 저장되었습니다.")
    print("=" * 50)


if __name__ == "__main__":
    run_multi_stock_test()