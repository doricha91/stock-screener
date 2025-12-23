import sqlite3
import os

# DB 파일 경로 설정
DB_PATH = "market_data.db"


def get_connection():
    """데이터베이스 연결 객체를 반환합니다."""
    conn = sqlite3.connect(DB_PATH)
    return conn


def create_tables():
    """
    시스템에 필요한 테이블들을 생성합니다.
    """
    conn = get_connection()
    cursor = conn.cursor()

    print("Checking and creating tables...")

    # 1. Tickers Table (종목 정보)
    # listing_board 컬럼을 통해 SP500, RUSSELL2000 등을 구분합니다.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tickers (
        symbol TEXT PRIMARY KEY,
        name TEXT,
        sector TEXT,
        industry TEXT,
        listing_board TEXT, 
        last_updated DATE
    )
    """)

    # 2. Daily Price Table (일별 시세)
    # 조회 속도를 높이기 위해 symbol과 date에 인덱스를 겁니다.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS daily_price (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        date DATE,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        adj_close REAL,
        volume INTEGER,
        FOREIGN KEY (symbol) REFERENCES tickers (symbol),
        UNIQUE(symbol, date)
    )
    """)

    # 인덱스 생성 (백테스트 속도 향상 핵심)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_price_symbol_date ON daily_price (symbol, date)")

    # 3. Market Index Table (시장 지수 및 매크로)
    # SPY, QQQ, VIX, 금리 등을 저장
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS market_index (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        date DATE,
        close REAL,
        adj_close REAL,
        moving_avg_200 REAL,
        UNIQUE(symbol, date)
    )
    """)

    # 4. Financials Table (재무제표 - 가치투자용)
    # 분기별 실적 데이터
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS financials (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT,
        date DATE,
        revenue REAL,
        net_income REAL,
        eps REAL,
        total_assets REAL,
        total_equity REAL,
        FOREIGN KEY (symbol) REFERENCES tickers (symbol),
        UNIQUE(symbol, date)
    )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_status_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE,
            status TEXT,          -- BULL, BEAR, UNSTABLE, PANIC
            vix_value REAL,       -- 당시 VIX 지수
            description TEXT,     -- 판단 근거 (텍스트)
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date)          -- 하루에 하나의 기록만 남김
        )
        """)

    print("Checking tables... (market_status_log added)")


    conn.commit()
    conn.close()
    print(f"Database initialized successfully at: {os.path.abspath(DB_PATH)}")


def check_db_status():
    """DB 상태를 간단히 확인합니다."""
    conn = get_connection()
    cursor = conn.cursor()

    tables = ['tickers', 'daily_price', 'market_index', 'financials']
    print("\n--- Current Database Status ---")
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"[{table}]: {count} rows")
        except sqlite3.OperationalError:
            print(f"[{table}]: Not created yet")

    conn.close()


if __name__ == "__main__":
    create_tables()
    check_db_status()