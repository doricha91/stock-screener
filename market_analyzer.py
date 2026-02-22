import os
import sqlite3
import pandas as pd
import config  # 설정 파일 로드
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

def _project_root() -> Path:
    here = Path(__file__).resolve()
    # config.py나 .git이 있는 폴더를 프로젝트 루트로 간주
    for p in [here.parent, *here.parents]:
        if (p / "config.py").exists() or (p / ".git").exists():
            return p
    return here.parent

ROOT = _project_root()

def _resolve_market_db() -> Path:
    # 1) 환경변수로 강제 지정 가능 (선택)
    env = os.getenv("STOCK_SCREENER_MARKET_DB")
    if env:
        return Path(env).expanduser()

    # 2) 자주 쓰는 위치 후보들
    candidates = [
        ROOT / "outputs" / "market_data.db",
        ROOT / "data" / "market_data.db",
        ROOT / "market_data.db",
    ]
    for p in candidates:
        if p.exists():
            return p

    # 3) 못 찾으면 명확한 에러로 안내 (빈 DB 새로 만들지 않게)
    raise FileNotFoundError(
        "market_data.db not found. Put it in one of: "
        f"{(ROOT/'outputs')}, {(ROOT/'data')}, or set env STOCK_SCREENER_MARKET_DB"
    )

DB_PATH = str(_resolve_market_db())


def get_db_connection():
    return sqlite3.connect(DB_PATH)


def calculate_breadth(conn, target_date=None, universe='NASDAQ100'):
    """
    [모멘텀] 특정 날짜 기준, 200일 이동평균선 위에 있는 종목의 비율(%)을 계산합니다.
    :param universe: 'NASDAQ100', 'SP500', 또는 'ALL' (대상 종목군)
    """
    cursor = conn.cursor()

    # 1. 분석할 날짜 확정 (target_date가 없으면 DB의 가장 최신 날짜 사용)
    if target_date:
        query_date = "SELECT MAX(date) FROM daily_indicators WHERE date <= ?"
        cursor.execute(query_date, (target_date,))
    else:
        cursor.execute("SELECT MAX(date) FROM daily_indicators")

    calc_date = cursor.fetchone()[0]

    if not calc_date:
        return 50.0  # 데이터가 없으면 중립 반환

    # 2. 대상 종목 필터링 쿼리 생성
    if universe == 'ALL':
        ticker_condition = ""
    else:
        ticker_condition = f"AND p.symbol IN (SELECT symbol FROM tickers WHERE listing_board = '{universe}')"

    # 3. 핵심 쿼리: 가격(p)과 지표(i)를 조인하여 비율 계산
    try:
        query = f"""
            SELECT 
                COUNT(CASE WHEN p.close > i.sma_200 THEN 1 END) as bull_count,
                COUNT(*) as total_count
            FROM daily_price p
            JOIN daily_indicators i ON p.symbol = i.symbol AND p.date = i.date
            WHERE p.date = ? 
            {ticker_condition}
        """

        cursor.execute(query, (calc_date,))
        row = cursor.fetchone()

        bull_count = row[0] if row[0] else 0
        total_count = row[1] if row[1] else 0

        if total_count == 0:
            return 50.0

        ratio = (bull_count / total_count) * 100.0
        return ratio

    except Exception as e:
        print(f"⚠️ Breadth 계산 실패: {e}")
        return 50.0


def get_market_regime(target_date=None):
    """
    [통합 판단] 1.추세(Trend) + 2.공포(Fear) + 3.모멘텀(Breadth) -> 최종 국면 판정
    """
    conn = get_db_connection()

    # 날짜 필터
    date_condition = "AND date <= ?" if target_date else ""
    params = [target_date] if target_date else []

    try:
        # ---------------------------------------------------------
        # 1. 지수 데이터 가져오기 (SPY, QQQ, VIX)
        # ---------------------------------------------------------
        dfs = {}
        for sym in ['SPY', 'QQQ', '^VIX']:
            query = f"""
                SELECT date, close 
                FROM market_index 
                WHERE symbol = '{sym}' {date_condition}
                ORDER BY date ASC
            """
            df = pd.read_sql(query, conn, params=params)
            if not df.empty:
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                df['close'] = pd.to_numeric(df['close'])
            dfs[sym] = df

        # [수정 2] 예외 발생 시 반환값 수정 (UNSTABLE_WEIGHTS -> REGIME_RULES['UNSTABLE'])
        if dfs['SPY'].empty or len(dfs['SPY']) < 200:
            conn.close()
            return "UNSTABLE", config.REGIME_RULES['UNSTABLE']

        # ---------------------------------------------------------
        # 2. 지표 계산
        # ---------------------------------------------------------
        # (1) 추세 (Trend): SPY, QQQ의 200일 이동평균선
        spy_ma200 = dfs['SPY']['close'].rolling(200).mean().iloc[-1]
        qqq_ma200 = dfs['QQQ']['close'].rolling(200).mean().iloc[-1]

        current_spy = dfs['SPY']['close'].iloc[-1]
        current_qqq = dfs['QQQ']['close'].iloc[-1]

        # (2) 공포 (Fear): VIX 지수
        current_vix = dfs['^VIX']['close'].iloc[-1] if not dfs['^VIX'].empty else 0.0

        # (3) 모멘텀 (Momentum): Market Breadth (진짜 SQL 계산)
        market_breadth = calculate_breadth(conn, target_date, universe='NASDAQ100')

        conn.close()

        # ---------------------------------------------------------
        # 3. 최종 판단 로직 (The Brain)
        # ---------------------------------------------------------

        # A. [공포] VIX 폭발 -> 무조건 도망
        if current_vix >= 30.0:
            return "PANIC", config.REGIME_RULES['PANIC']

        # B. [추세] 지수 가격이 200일선 위에 있는가?
        is_bull_trend = (current_spy > spy_ma200) and (current_qqq > qqq_ma200)
        is_bear_trend = (current_spy < spy_ma200) and (current_qqq < qqq_ma200)

        # C. [결합] 추세 + 모멘텀(Breadth)
        if is_bull_trend:
            if market_breadth >= 40.0:
                return "BULL", config.REGIME_RULES['BULL']
            else:
                return "UNSTABLE", config.REGIME_RULES['UNSTABLE']

        elif is_bear_trend:
            return "BEAR", config.REGIME_RULES['BEAR']

        else:
            return "UNSTABLE", config.REGIME_RULES['UNSTABLE']

    except Exception as e:
        print(f"❌ Market Regime 판단 오류: {e}")
        if 'conn' in locals(): conn.close()
        # [수정 3] 예외 발생 시 반환값 수정 (구버전 변수 제거)
        return "UNSTABLE", config.REGIME_RULES['UNSTABLE']


if __name__ == "__main__":
    # 테스트 실행
    regime, plan = get_market_regime()
    print(f"\n[The Brain 최종 진단]")
    print(f"1. 국면 판정: {regime}")
    print(f"2. 자금 관리: 현금 {plan['target_cash_ratio'] * 100}% 확보")
    print(f"3. 전략 가중치: {plan['weights']}")