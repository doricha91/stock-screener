# add_etf_data.py
import yfinance as yf
import sqlite3
import pandas as pd
from datetime import datetime

# DB 경로
DB_PATH = "market_data.db"


def add_etf_to_daily_price():
    # 추가할 ETF 목록
    etfs = ['SPY', 'QQQ']

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🚀 ETF 데이터를 daily_price 테이블에 추가합니다...")

    for ticker in etfs:
        print(f" - {ticker} 다운로드 중...")
        # 전체 기간 다운로드
        df = yf.download(ticker, start="2010-01-01", progress=False, auto_adjust=False)

        if df.empty:
            print(f"   ⚠️ {ticker} 데이터 없음")
            continue

        # 컬럼 정리
        df = df.reset_index()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        df = df.rename(columns={
            'Date': 'date', 'Open': 'open', 'High': 'high',
            'Low': 'low', 'Close': 'close', 'Adj Close': 'adj_close', 'Volume': 'volume'
        })
        df['date'] = df['date'].dt.strftime('%Y-%m-%d')

        # 데이터 삽입
        data_list = []
        for _, row in df.iterrows():
            data_list.append((
                ticker, row['date'], row['open'], row['high'],
                row['low'], row['close'], row['adj_close'], row['volume']
            ))

        try:
            cursor.executemany("""
                INSERT OR IGNORE INTO daily_price 
                (symbol, date, open, high, low, close, adj_close, volume) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, data_list)
            conn.commit()
            print(f"   ✅ {ticker} 저장 완료 ({len(data_list)}건)")

        except Exception as e:
            print(f"   ❌ 저장 실패: {e}")

    conn.close()
    print("🏁 작업 완료. 이제 검증 스크립트를 실행해보세요.")


if __name__ == "__main__":
    add_etf_to_daily_price()