#data_collector.py

import yfinance as yf
import pandas as pd
import sqlite3
import requests
from io import StringIO
import time
from datetime import datetime
import config
from core.paths import market_db_path

DB_PATH = market_db_path()


# --- 1. S&P 500 종목 리스트 (기존 함수 복구) ---
def get_sp500_tickers():
    """위키피디아에서 S&P500 종목 리스트를 크롤링합니다."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
        tables = pd.read_html(StringIO(response.text))
        df = tables[0]
        tickers = df['Symbol'].tolist()
        tickers = [ticker.replace('.', '-') for ticker in tickers]
        print(f"✅ S&P 500 종목 리스트 확보: {len(tickers)}개")
        return tickers
    except Exception as e:
        print(f"❌ S&P 500 수집 실패: {e}")
        return []


# --- 2. Nasdaq 100 종목 리스트 (신규 추가) ---
def get_nasdaq100_tickers():
    """위키피디아에서 Nasdaq 100 종목 리스트를 크롤링합니다."""
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers)
        tables = pd.read_html(StringIO(response.text))

        df = None
        for t in tables:
            if 'Ticker' in t.columns:
                df = t;
                break
            elif 'Symbol' in t.columns:
                df = t;
                break

        if df is None: raise Exception("테이블 못 찾음")

        col_name = 'Ticker' if 'Ticker' in df.columns else 'Symbol'
        tickers = df[col_name].tolist()
        tickers = [str(ticker).replace('.', '-') for ticker in tickers]
        print(f"✅ Nasdaq 100 종목 리스트 확보: {len(tickers)}개")
        return tickers
    except Exception as e:
        print(f"❌ Nasdaq 100 수집 실패: {e}")
        return []


# --- 3. 정보 및 주가 업데이트 함수 (기존과 동일) ---
def update_tickers_info(tickers):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("\n[Tickers Info] 종목 상세 정보 업데이트 시작...")

    cursor.execute("SELECT symbol FROM tickers")
    existing_tickers = set(row[0] for row in cursor.fetchall())

    cnt = 0
    for ticker in tickers:
        if ticker in existing_tickers: continue
        try:
            t = yf.Ticker(ticker)
            info = t.info
            name = info.get('shortName', info.get('longName', 'Unknown'))
            sector = info.get('sector', 'Unknown')
            industry = info.get('industry', 'Unknown')

            # 출처 구분 없이 일단 저장 (나중에 분석할 때 구분 가능)
            cursor.execute("""
                INSERT OR REPLACE INTO tickers (symbol, name, sector, industry, listing_board, last_updated)
                VALUES (?, ?, ?, ?, 'US_Stock', ?)
            """, (ticker, name, sector, industry, datetime.now().strftime('%Y-%m-%d')))
            conn.commit()
            cnt += 1
            print(f" - {ticker}: 정보 저장 완료")
            time.sleep(0.3)
        except Exception as e:
            print(f"⚠ {ticker} 정보 수집 실패: {e}")
    conn.close()
    print(f"✅ 총 {cnt}개 신규 종목 정보 업데이트 완료.")


def update_market_indices():
    indices = {
        'SPY': 'S&P 500 ETF', 'QQQ': 'NASDAQ 100 ETF',
        '^VIX': 'Volatility Index', '^TNX': '10-Year Treasury Yield',
        'DX-Y.NYB': 'US Dollar Index'
    }
    
    # [신규] 인버스 ETF 리스트 추가
    hedge_tickers = getattr(config, 'HEDGE_TICKERS', [])
    for t in hedge_tickers:
        if t not in indices:
            indices[t] = f'Hedge Asset {t}'

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print("\n[Market Index] 시장 지표 업데이트 시작...")
    for symbol, name in indices.items():
        try:
            cursor.execute("SELECT MAX(date) FROM market_index WHERE symbol = ?", (symbol,))
            last_date = cursor.fetchone()[0]
            start_date = "2000-01-01"
            if last_date:
                start_date = (pd.to_datetime(last_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')

            if start_date > datetime.today().strftime('%Y-%m-%d'):
                print(f" - {symbol}: 이미 최신입니다.")
                continue

            df = yf.download(symbol, start=start_date, progress=False, auto_adjust=False)
            if df.empty: continue

            df = df.reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
            df = df.rename(columns={'Date': 'date', 'Close': 'close', 'Adj Close': 'adj_close'})
            df['date'] = df['date'].dt.strftime('%Y-%m-%d')

            data_list = []
            for _, row in df.iterrows():
                data_list.append((symbol, row['date'], row['close'], row.get('adj_close', row['close']), 0.0))

            cursor.executemany(
                "INSERT OR IGNORE INTO market_index (symbol, date, close, adj_close, moving_avg_200) VALUES (?, ?, ?, ?, ?)",
                data_list)
            conn.commit()
            print(f" - {symbol}: 업데이트 완료")
        except Exception as e:
            print(f"Error {symbol}: {e}")
    conn.close()


def update_stock_data(tickers):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    print(f"\n📊 총 {len(tickers)}개 종목 주가 업데이트 시작...")

    for i, ticker in enumerate(tickers):
        try:
            cursor.execute("SELECT MAX(date) FROM daily_price WHERE symbol = ?", (ticker,))
            last_date = cursor.fetchone()[0]
            start_date = "2000-01-01"
            if last_date:
                start_date = (pd.to_datetime(last_date) + pd.Timedelta(days=1)).strftime('%Y-%m-%d')

            if start_date > datetime.today().strftime('%Y-%m-%d'):
                # print(f"[{i + 1}/{len(tickers)}] {ticker}: 이미 최신입니다.")
                continue

            df = yf.download(ticker, start=start_date, progress=False, auto_adjust=False)
            if df.empty:
                print(f"[{i + 1}/{len(tickers)}] {ticker}: 데이터 없음")
                continue

            df = df.reset_index()
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
            df = df.rename(columns={'Date': 'date', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close',
                                    'Adj Close': 'adj_close', 'Volume': 'volume'})
            df['date'] = df['date'].dt.strftime('%Y-%m-%d')

            data_list = []
            for _, row in df.iterrows():
                data_list.append((ticker, row['date'], row['open'], row['high'], row['low'], row['close'],
                                  row['adj_close'], row['volume']))

            cursor.executemany(
                "INSERT OR IGNORE INTO daily_price (symbol, date, open, high, low, close, adj_close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                data_list)
            conn.commit()
            print(f"[{i + 1}/{len(tickers)}] {ticker}: 업데이트 완료")
            time.sleep(0.1)
        except Exception as e:
            print(f"Error {ticker}: {e}")
    conn.close()
    print("✅ 모든 업데이트가 완료되었습니다.")


# --- 메인 실행 ---
if __name__ == "__main__":
    # 1. 두 리스트 모두 가져오기
    sp500 = get_sp500_tickers()
    nasdaq100 = get_nasdaq100_tickers()

    # 2. 합치고 중복 제거 (Set 활용)
    # S&P500과 나스닥100에 동시에 포함된 종목(예: AAPL, NVDA) 중복 방지
    all_tickers = list(set(sp500 + nasdaq100))
    print(f"\n📌 최종 수집 대상: {len(all_tickers)}개 종목 (S&P500 + Nasdaq100)")

    # 3. 데이터 수집 실행
    update_market_indices()  # 지수 업데이트
    update_tickers_info(all_tickers)  # 종목 정보 업데이트
    update_stock_data(all_tickers)  # 주가 데이터 업데이트