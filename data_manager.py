import pandas as pd
import sqlite3
import os

# 데이터베이스 파일 경로 (database.py에서 설정한 경로와 동일해야 함)
DB_PATH = "market_data.db"


class DataManager:
    """
    SQLite 데이터베이스에서 주식 데이터를 조회하여 DataFrame으로 반환하는 클래스
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        if not os.path.exists(self.db_path):
            print(f"⚠️ 경고: 데이터베이스 파일({self.db_path})을 찾을 수 없습니다.")
            print("database.py와 data_collector.py를 먼저 실행하여 DB를 구축해주세요.")

    def get_connection(self):
        """DB 연결 객체 반환"""
        return sqlite3.connect(self.db_path)

    def get_price_data(self, ticker, start_date=None, end_date=None):
        """
        특정 종목의 OHLCV 데이터를 DB에서 가져옵니다.

        :param ticker: 종목 코드 (예: 'AAPL')
        :param start_date: 시작 날짜 (YYYY-MM-DD, Optional)
        :param end_date: 종료 날짜 (YYYY-MM-DD, Optional)
        :return: 날짜를 인덱스로 갖는 Pandas DataFrame
        """
        conn = self.get_connection()

        # 1. 기본 쿼리 작성 (필요한 컬럼만 조회)
        query = """
            SELECT date, open, high, low, close, adj_close, volume 
            FROM daily_price 
            WHERE symbol = ?
        """
        params = [ticker]

        # 2. 날짜 필터링 추가
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        # 3. 날짜 오름차순 정렬 (백테스팅에 필수)
        query += " ORDER BY date ASC"

        try:
            # Pandas의 read_sql을 사용하여 DataFrame으로 변환
            df = pd.read_sql(query, conn, params=params)

            if df.empty:
                print(f"⚠️ [{ticker}] 해당 기간의 데이터가 DB에 없습니다.")
                return pd.DataFrame()

            # 4. 데이터 전처리 (시스템 호환성 유지)
            # 날짜 컬럼을 datetime 객체로 변환 후 인덱스로 설정
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            # 숫자형 데이터 강제 변환 (문자열로 들어갔을 경우 대비)
            numeric_cols = ['open', 'high', 'low', 'close', 'adj_close', 'volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            return df

        except Exception as e:
            print(f"❌ [{ticker}] 데이터 조회 중 오류 발생: {e}")
            return pd.DataFrame()

        finally:
            conn.close()

    def get_ticker_list(self):
        """
        DB에 저장된 모든 종목(Ticker) 리스트를 반환합니다.
        스크리너가 반복문을 돌 때 사용합니다.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        try:
            # tickers 테이블에서 가져오거나, daily_price에서 중복 제거하여 가져옴
            cursor.execute("SELECT symbol FROM tickers")
            rows = cursor.fetchall()

            # 리스트 형태로 변환 [('AAPL',), ('MSFT',)] -> ['AAPL', 'MSFT']
            tickers = [row[0] for row in rows]

            # 만약 tickers 테이블이 비어있으면 daily_price에서 조회
            if not tickers:
                cursor.execute("SELECT DISTINCT symbol FROM daily_price")
                rows = cursor.fetchall()
                tickers = [row[0] for row in rows]

            return tickers

        except Exception as e:
            print(f"❌ 종목 리스트 조회 중 오류: {e}")
            return []
        finally:
            conn.close()

    def get_all_price_data_bulk(self, start_date=None):
        """
        [속도 최적화] 모든 종목의 데이터를 한 번의 쿼리로 가져옵니다.
        """
        conn = self.get_connection()
        query = "SELECT date, symbol, open, high, low, close, volume FROM daily_price"
        params = []

        if start_date:
            query += " WHERE date >= ?"
            params.append(start_date)

        try:
            # 한 번에 모든 데이터 로드 (메모리 사용량은 늘지만 속도는 빠름)
            df = pd.read_sql(query, conn, params=params)

            if df.empty: return pd.DataFrame()

            df['date'] = pd.to_datetime(df['date'])

            # 숫자 변환
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            return df

        except Exception as e:
            print(f"❌ 전체 데이터 조회 실패: {e}")
            return pd.DataFrame()
        finally:
            conn.close()


# --- 전역 인스턴스 생성 ---
# 기존 코드들이 'import data_manager' 후 'data_manager.get_price_data'로
# 호출할 수 있도록 인스턴스를 미리 생성해둡니다.
manager = DataManager()


# 하위 호환성을 위한 래퍼 함수 (기존 코드가 data_manager.get_price_data() 함수를 직접 호출할 경우 대비)
def get_price_data(ticker, start_date=None, end_date=None):
    return manager.get_price_data(ticker, start_date, end_date)


def get_ticker_list():
    return manager.get_ticker_list()

def get_all_price_data_bulk(start_date=None):
    return manager.get_all_price_data_bulk(start_date)