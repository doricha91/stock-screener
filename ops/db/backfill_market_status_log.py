from pathlib import Path
import sys
import os
import sqlite3
from typing import List, Set

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB_PATH = str(ROOT / "outputs" / "market_data.db")
START_DATE = "2000-02-01"


def get_latest_spy_date(conn: sqlite3.Connection) -> str:
    cur = conn.cursor()
    cur.execute("SELECT MAX(date) FROM market_index WHERE symbol='SPY'")
    d = cur.fetchone()[0]
    if not d:
        raise RuntimeError("market_index 테이블에 SPY 데이터가 없습니다.")
    return d


def get_spy_trading_days(conn: sqlite3.Connection, start_date: str, end_date: str) -> List[str]:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date
        FROM market_index
        WHERE symbol='SPY'
          AND date BETWEEN ? AND ?
        ORDER BY date
        """,
        (start_date, end_date),
    )
    return [r[0] for r in cur.fetchall()]


def get_existing_logged_dates(conn: sqlite3.Connection) -> Set[str]:
    cur = conn.cursor()
    cur.execute("SELECT date FROM market_status_log")
    return {r[0] for r in cur.fetchall()}


def main():
    # market_analyzer가 반드시 outputs/market_data.db를 쓰게 강제
    os.environ["STOCK_SCREENER_MARKET_DB"] = DB_PATH

    import market_analyzer  # 사용자가 수정 적용한 버전

    conn = sqlite3.connect(DB_PATH)
    try:
        end_date = get_latest_spy_date(conn)
        trading_days = get_spy_trading_days(conn, START_DATE, end_date)
        existing = get_existing_logged_dates(conn)

        targets = [d for d in trading_days if d not in existing]
        total = len(targets)

        print(f"DB: {DB_PATH}")
        print(f"Range: {START_DATE} ~ {end_date} (SPY trading days)")
        print(f"Existing rows: {len(existing)}")
        print(f"To backfill: {total}")

        if total == 0:
            print("✅ 백필할 날짜가 없습니다.")
            return

        done = 0
        for d in targets:
            try:
                market_analyzer.get_market_state(d)  # 내부에서 upsert
                done += 1
                if done % 50 == 0 or done == total:
                    print(f"Progress: {done}/{total} (last={d})")
            except Exception as e:
                # 실패해도 계속 진행. 재실행하면 누락분만 다시 처리됨
                print(f"⚠️ Failed at {d}: {e}")

        print("✅ Backfill completed.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()