# fix_tags.py (DB 태그 수정용)
import sqlite3
import yfinance as yf
import pandas as pd
import requests
from io import StringIO


def get_nasdaq100_tickers():
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    tables = pd.read_html(StringIO(response.text))

    df = None
    for t in tables:
        if 'Ticker' in t.columns:
            df = t; break
        elif 'Symbol' in t.columns:
            df = t; break

    tickers = df['Ticker' if 'Ticker' in df.columns else 'Symbol'].tolist()
    return [str(t).replace('.', '-') for t in tickers]


def fix_db_tags():
    nasdaq100 = get_nasdaq100_tickers()
    conn = sqlite3.connect("outputs/market_data.db")
    cursor = conn.cursor()

    print(f"🔧 나스닥 100 종목({len(nasdaq100)}개) 태그 업데이트 중...")

    # 1. 모든 태그를 일단 'Other'로 초기화 (선택 사항)
    # cursor.execute("UPDATE tickers SET listing_board = 'Other'")

    # 2. 나스닥 100 종목만 태그 업데이트
    for ticker in nasdaq100:
        cursor.execute("UPDATE tickers SET listing_board = 'NASDAQ100' WHERE symbol = ?", (ticker,))

    conn.commit()
    conn.close()
    print("✅ DB 태그 수정 완료! 이제 백테스트를 다시 돌려보세요.")


if __name__ == "__main__":
    fix_db_tags()