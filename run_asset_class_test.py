# [ 📄 run_asset_class_test.py (신규 파일) ]

import config
from run_backtest import run_single_backtest  # 리팩토링된 단일 실행 함수 임포트
from tqdm import tqdm


def run_multi_asset_test():
    """
    다양한 자산군(ETF) 리스트를 순회하며,
    '최적의 설정값'으로 다중 자산군 백테스트를 실행합니다.
    """

    # --- 1. 테스트할 자산군(ETF) 리스트 ---
    # (사용자가 제안한 다양한 자산군 대표 ETF)
    asset_class_tickers = [
        'SPY',  # 미국 대형주 (S&P 500)
        'QQQ',  # 미국 성장주 (Nasdaq 100)
        'IWM',  # 미국 소형주 (Russell 2000)
        'SCHD',  # 미국 배당주
        'TLT',  # 미국 장기 채권 (20+년)
        'AGG',  # 미국 종합 채권
        'GLD',  # 금 (상품)
        'USO',  # 원유 (상품)
        'VNQ',  # 부동산 (섹터)
        'EEM',  # 신흥국 (해외)
    ]

    # --- 2. '최적의 설정값' 정의 ---
    # (우리가 'AAPL'에서 찾은 값으로 고정)
    OPTIMAL_ENTRY_PERIOD = 20

    print("=" * 50)
    print(f"다중 자산군 백테스트를 시작합니다. (총 {len(asset_class_tickers)}개 자산군)")
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
    for symbol in tqdm(asset_class_tickers, desc="다중 자산군 테스트 진행률"):

        # 4-1. 현재 루프의 종목으로 context 수정
        current_context = base_context.copy()
        current_context['symbol'] = symbol

        # 4-2. 단일 백테스트 실행
        try:
            run_single_backtest(current_context)
        except Exception as e:
            # (데이터가 없거나(예: USO) 중간에 오류가 나도 멈추지 않도록)
            print(f"\n*** {symbol} 테스트 중 오류 발생: {e} ***")
            print("다음 종목으로 넘어갑니다.")

        print(f"\n{symbol} 테스트 완료.\n" + "-" * 50)

    print("=" * 50)
    print("다중 자산군 백테스트 완료.")
    print(f"모든 결과는 {config.BACKTEST_DB_NAME} 파일에 저장되었습니다.")
    print("=" * 50)


if __name__ == "__main__":
    run_multi_asset_test()