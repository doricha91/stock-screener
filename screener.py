# [ 📄 screener.py ]

import config
import data_manager
import indicator
import strategy
from tqdm import tqdm  # 진행률 표시를 위해 import


def run_screener():
    """
    config.py의 TICKER_LIST를 순회하며 스크리닝을 실행합니다.
    'Buy' 신호가 발생한 종목을 찾아 리스트로 반환합니다.
    """

    print(f"총 {len(config.TICKER_LIST)}개 종목 스크리닝 시작...")

    # 'Buy' 신호가 나온 종목 정보를 저장할 리스트
    buy_signals = []

    # tqdm으로 TICKER_LIST를 감싸면 진행률 표시줄이 생김
    for symbol in tqdm(config.TICKER_LIST):

        # 1. (2단계) 데이터 가져오기
        df = data_manager.get_stock_data(symbol, output_size='compact')
        if df is None:
            print(f"[{symbol}] 데이터 수집 실패, 건너뜁니다.") # 진행률 표시줄이 깨질 수 있어 주석 처리
            continue

        # 2. (3단계) 지표 계산
        df_indicators = indicator.add_all_indicators(df)

        # 3. (4단계) 신호 생성
        df_signals = strategy.generate_signals(df_indicators)
        if df_signals is None:
            print(f"[{symbol}] 신호 생성 실패, 건너뜁니다.") # 진행률 표시줄이 깨질 수 있어 주석 처리
            continue

        # 4. 최종 결정: "가장 마지막 날짜(오늘)의 신호" 확인
        try:
            latest_signal_info = df_signals.iloc[-1]
        except IndexError:
            print(f"[{symbol}] 데이터가 비어있어 분석 불가, 건너뜁니다.") # 진행률 표시줄이 깨질 수 있어 주석 처리
            continue

        # 5. 'Buy' 신호인지 확인
        if latest_signal_info['signal'] == 'Buy':
            # tqdm의 진행률 표시줄과 겹치지 않게 print() 앞에 \n(줄바꿈) 추가
            print(f"\n*** 'Buy' 신호 발견! [{symbol}] ***")

            # 리포트에 저장할 정보 생성
            result = {
                'symbol': symbol,
                'date': latest_signal_info.name.strftime('%Y-%m-%d'),  # 날짜(인덱스)
                'close': latest_signal_info['close'],
                'atr': latest_signal_info['atr'],
                'signal': 'Buy'
            }
            buy_signals.append(result)

    # 6. 모든 'Buy' 신호 리스트를 반환
    return buy_signals