# [ 📄 optimizer.py (신규 파일) ]

import config
from run_backtest import run_single_backtest  # 리팩토링된 단일 실행 함수 임포트
from tqdm import tqdm  # (선택) 진행률 표시를 위해


def run_optimization():
    """
    정의된 파라미터 리스트를 순회하며 전략 최적화를 실행합니다.
    """

    # --- 1. 최적화할 파라미터 정의 ---
    # 'entry_period' 값을 20일, 30일, 40일, 50일로 바꿔가며 테스트
    entry_periods_to_test = [20, 30, 40, 50, 60]

    # (향후 확장 예시)
    # exit_periods_to_test = [10, 15]
    # stop_loss_multipliers = [2.0, 2.5]

    print("=" * 50)
    print(f"전략 최적화를 시작합니다. (총 {len(entry_periods_to_test)}회 실행)")
    print(f"대상 종목: AAPL")
    print(f"테스트할 Entry 값: {entry_periods_to_test}")
    print("=" * 50)

    # --- 2. 기본 설정값 로드 (config.py에서) ---
    base_context = {
        'symbol': 'AAPL',
        'initial_capital': 10000.0,
        'output_size': 'full',
        'exit_period': config.TURTLE_EXIT_PERIOD,
        'atr_period': config.ATR_PERIOD,
        'risk_percent': config.RISK_PER_TRADE_PERCENT,
        'stop_loss_atr': config.STOP_LOSS_ATR_MULTIPLIER
    }

    # --- 3. 파라미터 리스트 순회 (tqdm 적용) ---
    for entry_period in tqdm(entry_periods_to_test, desc="최적화 진행률"):
        # 3-1. 현재 루프의 설정값으로 context 복사 및 수정
        current_context = base_context.copy()
        current_context['entry_period'] = entry_period

        # (향후 확장 예시: 2중 for문)
        # for exit_period in exit_periods_to_test:
        #    current_context['exit_period'] = exit_period
        #    ...

        # 3-2. 단일 백테스트 실행
        # (run_single_backtest 함수가 DB 저장 및 콘솔 리포트까지 모두 처리)
        run_single_backtest(current_context)

        print(f"\nEntry: {entry_period}일 테스트 완료.\n" + "-" * 50)

    print("=" * 50)
    print("전략 최적화 완료.")
    print(f"모든 결과는 {config.BACKTEST_DB_NAME} 파일에 저장되었습니다.")
    print("=" * 50)


if __name__ == "__main__":
    run_optimization()