import yfinance as yf
import pandas as pd
import sqlite3
import requests  # <-- 이 모듈을 import 해야 합니다!
from io import StringIO
import time
from datetime import datetime

# DB 경로 (database.py에서 만든 경로와 동일해야 함)
DB_PATH = "market_data.db"


def get_sp500_tickers():
    """위키피디아에서 S&P500 종목 리스트를 크롤링합니다 (헤더 추가 버전)."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

    # 봇 차단 방지용 헤더 (브라우저인 척 속임)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    # 1. requests로 HTML 데이터 가져오기
    response = requests.get(url, headers=headers)
    # 2. HTML 텍스트를 pandas로 파싱
    # StringIO를 사용하여 문자열을 파일처럼 취급 (Pandas 최신 버전 경고 방지)
    tables = pd.read_html(StringIO(response.text))
    df = tables[0]
    tickers = df['Symbol'].tolist()
    # 3. 티커 기호 변환 (예: BRK.B -> BRK-B)
    tickers = [ticker.replace('.', '-') for ticker in tickers]
    print(f"S&P500 종목 리스트 확보 완료: {len(tickers)}개")
    return tickers


# --- 2. [신규] 종목 상세 정보(tickers 테이블) 업데이트 ---
def update_tickers_info(tickers):
    """
    종목의 이름, 섹터, 산업군 정보를 tickers 테이블에 저장합니다.
    (주의: yfinance info 속성은 느리므로, DB에 없는 것만 업데이트합니다.)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("\n[Tickers Info] 종목 상세 정보 업데이트 시작...")
    # 이미 정보가 있는 종목은 건너뛰기
    cursor.execute("SELECT symbol FROM tickers")
    existing_tickers = set(row[0] for row in cursor.fetchall())
    cnt = 0
    for ticker in tickers:
        if ticker in existing_tickers:
            continue
        try:
            # yfinance Ticker 객체 생성
            t = yf.Ticker(ticker)
            info = t.info
            # 필요한 정보 추출
            name = info.get('shortName', info.get('longName', 'Unknown'))
            sector = info.get('sector', 'Unknown')
            industry = info.get('industry', 'Unknown')
            # DB 저장
            cursor.execute("""
                INSERT OR REPLACE INTO tickers (symbol, name, sector, industry, listing_board, last_updated)
                VALUES (?, ?, ?, ?, 'SP500', ?)
            """, (ticker, name, sector, industry, datetime.now().strftime('%Y-%m-%d')))
            conn.commit()
            cnt += 1
            print(f" - {ticker}: 정보 저장 완료 ({sector})")
            # 차단 방지 딜레이 (info 요청은 무거운 편입니다)
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠ {ticker} 정보 수집 실패: {e}")
    conn.close()
    if cnt > 0:
        print(f"✅ 총 {cnt}개 종목 정보 업데이트 완료.")
    else:
        print("✅ 모든 종목 정보가 이미 최신입니다.")

# --- 3. [신규] 시장 지수(market_index 테이블) 업데이트 ---
def update_market_indices():
    """
    SPY(S&P500), QQQ(Nasdaq), ^VIX(공포지수), ^TNX(10년물 금리), DX-Y.NYB(달러)
    데이터를 수집하여 market_index 테이블에 저장합니다.
    """
    # 수집할 지수 목록 정의
    indices = {
        'SPY': 'S&P 500 ETF',
        'QQQ': 'NASDAQ 100 ETF',
        '^VIX': 'Volatility Index',
        '^TNX': '10-Year Treasury Yield',
        'DX-Y.NYB': 'US Dollar Index'
    }
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("\n[Market Index] 시장 지표 업데이트 시작...")
    for symbol, name in indices.items():
        try:
            # DB에서 마지막 날짜 확인
            cursor.execute("SELECT MAX(date) FROM market_index WHERE symbol = ?", (symbol,))
            last_date = cursor.fetchone()[0]
            start_date = "2000-01-01"
            if last_date:
                start_date = (pd.to_datetime(last_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            if start_date > datetime.today().strftime('%Y-%m-%d'):
                print(f" - {symbol} ({name}): 이미 최신입니다.")
                continue
            # 데이터 다운로드
            df = yf.download(symbol, start=start_date, progress=False, auto_adjust=False)
            if df.empty:
                print(f"⚠ {symbol}: 데이터 없음")
                continue
            df = df.reset_index()
            # MultiIndex 컬럼 처리
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            # 컬럼명 통일
            df = df.rename(columns={'Date': 'date', 'Close': 'close', 'Adj Close': 'adj_close'})
            df['date'] = df['date'].dt.strftime('%Y-%m-%d')
            # DB 저장
            data_list = []
            for _, row in df.iterrows():
                # 200일 이평선은 나중에 계산하므로 0.0 또는 NULL로 저장
                data_list.append((symbol, row['date'], row['close'], row.get('adj_close', row['close']), 0.0))
            cursor.executemany("""
                INSERT OR IGNORE INTO market_index (symbol, date, close, adj_close, moving_avg_200)
                VALUES (?, ?, ?, ?, ?)
            """, data_list)
            conn.commit()
            print(f" - {symbol}: 업데이트 완료 ({len(df)}일 추가)")
        except Exception as e:
            print(f"❌ {symbol} 업데이트 중 오류: {e}")
    conn.close()
    print("✅ 시장 지표 업데이트 완료.")

def update_stock_data(tickers):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print(f"총 {len(tickers)}개 종목 업데이트 시작...")
    for i, ticker in enumerate(tickers):
        try:
            # 1. DB에서 마지막 날짜 확인 (증분 업데이트)
            cursor.execute("SELECT MAX(date) FROM daily_price WHERE symbol = ?", (ticker,))
            last_date = cursor.fetchone()[0]
            start_date = "2000-01-01"  # 기본 시작일
            if last_date:
                # 마지막 날짜 다음날부터 수집
                start_date = (pd.to_datetime(last_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')
            # 오늘 날짜와 비교하여 이미 최신이면 스킵
            if start_date > datetime.today().strftime('%Y-%m-%d'):
                print(f"[{i + 1}/{len(tickers)}] {ticker}: 이미 최신입니다.")
                continue
            # 2. yfinance로 데이터 다운로드
            df = yf.download(ticker, start=start_date, progress=False, auto_adjust=False)
            if df.empty:
                print(f"[{i + 1}/{len(tickers)}] {ticker}: 데이터 없음 (Pass)")
                continue
            # 3. 데이터 전처리 및 저장
            df = df.reset_index()
            # yfinance 최신 버전은 컬럼이 튜플(Price, Ticker)로 올 수 있음. 단순화 처리
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            # DB 컬럼명에 맞춤
            df = df.rename(columns={
                'Date': 'date', 'Open': 'open', 'High': 'high',
                'Low': 'low', 'Close': 'close', 'Adj Close': 'adj_close', 'Volume': 'volume'
            })
            # 날짜 포맷 통일 (YYYY-MM-DD)
            df['date'] = df['date'].dt.strftime('%Y-%m-%d')
            # Insert
            data_list = []
            for _, row in df.iterrows():
                data_list.append((
                    ticker, row['date'], row['open'], row['high'],
                    row['low'], row['close'], row['adj_close'], row['volume']
                ))
            cursor.executemany("""
                INSERT OR IGNORE INTO daily_price 
                (symbol, date, open, high, low, close, adj_close, volume) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, data_list)
            conn.commit()
            print(f"[{i + 1}/{len(tickers)}] {ticker}: 업데이트 완료 ({len(df)}일 추가)")
            # 차단 방지용 딜레이
            time.sleep(0.1)
        except Exception as e:
            print(f"Error updating {ticker}: {e}")

    conn.close()
    print("모든 업데이트가 완료되었습니다.")


# --- 메인 실행 ---
if __name__ == "__main__":
    # 1. 종목 리스트 확보
    sp500 = get_sp500_tickers()
    # 2. 시장 지수 업데이트 (Priority 1)
    update_market_indices()
    # 3. 종목 상세 정보 업데이트 (Priority 2 - 최초 1회는 오래 걸림)
    # 필요 없다면 주석 처리 가능하지만, tickers 테이블을 채우기 위해 실행 권장
    update_tickers_info(sp500)
    # 4. 개별 종목 주가 업데이트 (Priority 3)
    update_stock_data(sp500)