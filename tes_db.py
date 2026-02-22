# test_db.py
from screener.data_manager import get_price_data, get_ticker_list

# 1. 종목 리스트 확인
tickers = get_ticker_list()
print(f"DB에 저장된 종목 수: {len(tickers)}개")
print(f"첫 5개 종목: {tickers[:5]}")

# 2. 특정 종목 데이터 확인 (예: 리스트의 첫 번째 종목)
if tickers:
    test_ticker = tickers[0]
    print(f"\n--- {test_ticker} 데이터 조회 테스트 ---")

    df = get_price_data(test_ticker, start_date="2023-01-01")

    if not df.empty:
        print(df.head())
        print(df.tail())
        print("\n성공! 데이터가 DataFrame으로 잘 변환되었습니다.")
    else:
        print("실패: 데이터프레임이 비어있습니다.")