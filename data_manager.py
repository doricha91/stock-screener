import requests
import pandas as pd
import os
from io import StringIO
import config
import yfinance as yf  # <--- [필수] 무료 데이터 수집을 위해 추가

# 데이터 저장 폴더
DATA_DIR = "data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)


# 1. 기존 Alpha Vantage 함수 (유지하되, 에러 처리 강화)
def get_stock_data(symbol, output_size='compact'):
    file_path = os.path.join(DATA_DIR, f"{symbol}_{output_size}.csv")

    # 캐시 확인
    if os.path.exists(file_path):
        print(f"[{symbol}] 캐시 파일 로드 중... ({file_path})")
        try:
            return pd.read_csv(file_path, index_col='date', parse_dates=True)
        except:
            print(f"[{symbol}] 캐시 파일 오류. API 재시도.")

    # API 호출
    print(f"[{symbol}] Alpha Vantage API 호출 중...")
    try:
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize={output_size}&apikey={config.ALPHA_VANTAGE_API_KEY}&datatype=csv"
        response = requests.get(url)

        # [에러 체크] API 한도 초과 시 CSV가 아닌 텍스트가 옴
        if "Error" in response.text or "Note" in response.text:
            print(f"❌ [{symbol}] API 한도 초과 또는 오류 (Alpha Vantage)")
            return None

        df = pd.read_csv(StringIO(response.text))

        # 컬럼 확인 (timestamp가 없으면 데이터가 아님)
        if 'timestamp' not in df.columns:
            print(f"❌ [{symbol}] 데이터 형식 오류 (timestamp 컬럼 없음)")
            return None

        df = df.rename(columns={'timestamp': 'date'})
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date').sort_index()

        df.to_csv(file_path)
        print(f"✅ [{symbol}] 저장 완료 (Alpha Vantage)")
        return df

    except Exception as e:
        print(f"❌ [{symbol}] 오류 발생: {e}")
        return None


# 2. [수정됨] 야후 파이낸스 강제 다운로드 함수
def update_data_with_yfinance(ticker_list):
    print("\n🚀 [야후 파이낸스] 데이터 수집 시작 (무제한)...")

    for ticker in ticker_list:
        print(f"   [{ticker}] 다운로드 중...", end=" ")
        try:
            # 야후에서 전체 데이터 받기
            df = yf.download(ticker, period="max", progress=False, auto_adjust=True)

            if df.empty:
                print("⚠️ 실패 (데이터 없음)")
                continue

            # --- [수정된 부분: 튜플 컬럼 처리] ---
            # 컬럼이 MultiIndex(튜플)인 경우, 첫 번째 레벨(Price)만 가져와서 평탄화
            # 예: ('Close', 'TQQQ') -> 'Close'
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            # ----------------------------------

            # 포맷 맞추기 (Index -> Date 컬럼)
            df = df.reset_index()

            # 이제 컬럼이 문자열이므로 .lower() 사용 가능
            df.columns = [str(c).lower() for c in df.columns]

            # 날짜 변환
            if 'date' in df.columns:
                df['date'] = df['date'].dt.strftime('%Y-%m-%d')

            # 필요한 컬럼만 남기기
            wanted = ['date', 'open', 'high', 'low', 'close', 'volume']
            df = df[[c for c in wanted if c in df.columns]]

            # 저장
            save_path = f"data/{ticker}_full.csv"
            df.to_csv(save_path, index=False)
            print(f"✅ 성공 -> {save_path}")

        except Exception as e:
            print(f"❌ 에러: {e}")
    print("🏁 수집 완료.\n")


# 3. [중요] 실행 명령 블록 (이게 없어서 실행이 안 됐던 겁니다!)
if __name__ == "__main__":
    # 여기에 받고 싶은 종목을 적으세요
    target_tickers = ['TQQQ', 'SOXL', 'TSLA', 'SPY']

    # 야후 파이낸스 함수 실행!
    update_data_with_yfinance(target_tickers)