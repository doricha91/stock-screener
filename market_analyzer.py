import sqlite3
import pandas as pd
import pandas_ta as ta  # 지표 계산용
#10년물 금리, 달러인덱스 확장 예정
# DB 경로 설정
DB_PATH = "market_data.db"


def get_index_data_from_db(symbol):
    """
    DB의 'market_index' 테이블에서 지수 데이터를 가져옵니다.
    (SPY, QQQ 등)
    """
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT date, close, adj_close 
        FROM market_index 
        WHERE symbol = ? 
        ORDER BY date ASC
    """
    try:
        df = pd.read_sql(query, conn, params=[symbol])
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            # 숫자형 변환
            df['close'] = pd.to_numeric(df['close'])
            df['adj_close'] = pd.to_numeric(df['adj_close'])
        return df
    except Exception as e:
        print(f"❌ [Market Analyzer] {symbol} 데이터 로드 실패: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def save_market_log(date, status, vix, description):
    """
    [신규] 분석 결과를 DB(market_status_log 테이블)에 저장합니다.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO market_status_log (date, status, vix_value, description)
            VALUES (?, ?, ?, ?)
        """, (date, status, vix, description))
        conn.commit()
        # print(f"💾 시장 상태 기록 완료: {date} [{status}]") # 로그 확인용
    except Exception as e:
        print(f"❌ 시장 상태 저장 실패: {e}")
    finally:
        conn.close()


def analyze_market_status():
    """
    SPY, QQQ, VIX를 분석하여 시장 상태를 판단하고 DB에 기록합니다.
    """
    # 1. 데이터 로드
    df_spy = get_index_data_from_db('SPY')
    df_qqq = get_index_data_from_db('QQQ')
    df_vix = get_index_data_from_db('^VIX')

    if df_spy.empty or df_qqq.empty:
        return {'status': 'ERROR', 'reason': '데이터 부족'}

    # 2. 지표 계산 (200일선)
    df_spy['sma_200'] = df_spy['close'].rolling(window=200).mean()
    df_qqq['sma_200'] = df_qqq['close'].rolling(window=200).mean()

    # 오늘 기준 데이터
    last_spy = df_spy.iloc[-1]
    last_qqq = df_qqq.iloc[-1]

    # VIX (데이터 없으면 0 처리)
    current_vix = df_vix.iloc[-1]['close'] if not df_vix.empty else 0.0

    # 3. 판단 로직
    spy_bull = last_spy['close'] > last_spy['sma_200']
    qqq_bull = last_qqq['close'] > last_qqq['sma_200']

    status = "NEUTRAL"
    description = ""

    # (1) 공포장 (VIX 필터)
    if current_vix > 30.0:
        status = "PANIC"
        description = f"🚨 공포 구간 (VIX {current_vix:.1f}) - 매매 중단"
    # (2) 상승장
    elif spy_bull and qqq_bull:
        status = "BULL"
        description = "📈 상승장 (SPY, QQQ 모두 200일선 위)"
    # (3) 하락장
    elif not spy_bull and not qqq_bull:
        status = "BEAR"
        description = "📉 하락장 (모두 200일선 아래)"
    # (4) 혼조세
    else:
        status = "UNSTABLE"
        desc_spy = "SPY상승" if spy_bull else "SPY하락"
        desc_qqq = "QQQ상승" if qqq_bull else "QQQ하락"
        description = f"⚠️ 혼조세 ({desc_spy}, {desc_qqq})"

    today_date = last_spy.name.strftime('%Y-%m-%d')

    # 4. [중요] 결과 DB 저장
    save_market_log(today_date, status, current_vix, description)

    return {
        'date': today_date,
        'status': status,
        'description': description,
        'spy_close': round(last_spy['close'], 2),
        'qqq_close': round(last_qqq['close'], 2),
        'vix': round(current_vix, 2)
    }


if __name__ == "__main__":
    # 테스트 실행
    res = analyze_market_status()
    print(f"\n[결과] {res['date']} : {res['status']}")
    print(f"설명: {res['description']}")