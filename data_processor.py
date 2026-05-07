# data_processor.py

import pandas as pd
import pandas_ta as ta
from tqdm import tqdm
from screener import database


def update_technical_indicators():
    """
    daily_price 테이블의 데이터를 읽어와서
    SMA_20, RSI_14 등 필요한 지표를 계산한 뒤 daily_indicators 테이블에 저장합니다.
    (이미 계산된 데이터는 건너뛰는 증분 업데이트 방식)
    """
    conn = database.get_connection()
    cursor = conn.cursor()

    print("[Data Processor] 보조지표 계산 및 DB 업데이트 시작...")

    # 1. 대상 종목 가져오기 (전체 종목)
    cursor.execute("SELECT symbol FROM tickers")
    tickers = [row[0] for row in cursor.fetchall()]

    if not tickers:
        print("[WARN] 종목 데이터가 없습니다. data_collector.py를 먼저 실행하세요.")
        return

    updated_count = 0

    # 2. 종목별 루프
    for symbol in tqdm(tickers, desc="Processing Indicators"):
        try:
            # (1) 이미 지표가 계산된 최신 날짜 확인
            cursor.execute("SELECT MAX(date) FROM daily_indicators WHERE symbol = ?", (symbol,))
            last_calc_date = cursor.fetchone()[0]

            # (2) 가격 데이터 가져오기 (200일선 계산을 위해 넉넉하게 300일 전부터)
            if last_calc_date:
                # 200일 이동평균 계산을 위해 최소 200일+alpha 데이터 필요
                query = """
                                SELECT date, high, low, close 
                                FROM daily_price 
                                WHERE symbol = ? AND date >= date(?, '-300 days')
                                ORDER BY date ASC
                            """
                params = (symbol, last_calc_date)
            else:
                query = """
                                SELECT date, high, low, close 
                                FROM daily_price 
                                WHERE symbol = ? 
                                ORDER BY date ASC
                            """
                params = (symbol,)

            df = pd.read_sql(query, conn, params=params)

            if df.empty or len(df) < 20:
                continue

            # (3) 지표 계산 (pandas_ta 활용)
            # A. 이동평균선 (Trend)
            df['sma_20'] = ta.sma(df['close'], length=20)
            df['sma_50'] = ta.sma(df['close'], length=50)
            df['sma_200'] = ta.sma(df['close'], length=200)

            # B. 모멘텀 (Momentum)
            df['rsi_14'] = ta.rsi(df['close'], length=14)

            # C. 변동성 (Volatility) - 리스크 관리용 핵심
            df['atr_20'] = ta.atr(df['high'], df['low'], df['close'], length=20)

            # (4) DB 저장할 데이터 필터링
            if last_calc_date:
                df = df[df['date'] > last_calc_date]

            if df.empty:
                continue

            # (5) 저장 (컬럼 순서 주의!)
            data_to_insert = []
            for _, row in df.iterrows():
                # 필수 지표(sma_20 등)가 NaN이면 저장 스킵 (데이터 부족 초기 구간)
                if pd.isna(row['sma_20']): continue

                # 나머지 지표는 NaN일 경우 None으로 처리 (DB에는 NULL로 들어감)
                sma_20 = row['sma_20']
                sma_50 = row['sma_50'] if pd.notna(row['sma_50']) else None
                sma_200 = row['sma_200'] if pd.notna(row['sma_200']) else None
                rsi_14 = row['rsi_14'] if pd.notna(row['rsi_14']) else None
                atr_20 = row['atr_20'] if pd.notna(row['atr_20']) else None

                data_to_insert.append((symbol, row['date'], sma_20, sma_50, sma_200, rsi_14, atr_20))

            if data_to_insert:
                cursor.executemany("""
                                INSERT OR IGNORE INTO daily_indicators 
                                (symbol, date, sma_20, sma_50, sma_200, rsi_14, atr_20)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, data_to_insert)
                updated_count += 1

        except Exception as e:
            print(f"[ERROR] {symbol} 처리 중 오류: {e}")
            continue

    conn.commit()
    conn.close()
    print(f"[OK] 업데이트 완료: 총 {updated_count}개 종목의 지표가 최신화되었습니다.")


if __name__ == "__main__":
    # 1. DB 테이블 생성 확인
    database.create_tables()

    # 2. 지표 업데이트 실행
    update_technical_indicators()
