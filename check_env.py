# check_env.py (진단용)
import data_manager
import indicator
import pandas as pd


def check():
    print("🔍 환경 진단 시작...")

    # 1. 데이터 로드 확인
    symbol = 'AAPL'
    df = data_manager.get_price_data(symbol, start_date='2024-01-01')

    if df is None:
        print("❌ 데이터 로드 실패")
        return

    print(f"\n1. 데이터 구조 확인 (Raw Data):")
    print(f" - Index Type: {type(df.index)}")
    print(f" - Index Name: {df.index.name}")
    print(f" - Columns: {list(df.columns)}")
    print(df.head(2))

    # 2. 지표 계산 후 컬럼 확인
    # (에러가 날 경우 어디서 나는지 확인)
    try:
        # 빈 딕셔너리라도 넘겨서 기본값으로 돌아가는지 확인
        df = indicator.add_turtle_indicators(df, {})
        print(f"\n2. 터틀 지표 계산 후 Columns:")
        print(list(df.columns))
    except Exception as e:
        print(f"\n❌ add_turtle_indicators 에러: {e}")

    try:
        # 기존에 있던 함수 이름 확인 (add_atr 등)
        if hasattr(indicator, 'add_atr'):
            print("\n3. ATR 함수 존재 여부: YES (add_atr)")
        elif hasattr(indicator, 'add_atr_indicators'):
            print("\n3. ATR 함수 존재 여부: YES (add_atr_indicators)")
        else:
            print("\n3. ATR 함수 존재 여부: NO (함수명 확인 필요)")
    except:
        pass


if __name__ == "__main__":
    check()