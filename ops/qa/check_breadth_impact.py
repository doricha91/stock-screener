# ops/qa/check_breadth_impact.py
#
# 목적
# - market_status_log에서 breadth_low(브레드스 저하) 트리거가
#   실제로 어떤 상태(status)와 함께 나타났는지 확인
# - 브레드스가 "단독 영향 가능성"이 있었는지 확인
#
# 실행
#   python ops/qa/check_breadth_impact.py
#
# 전제
# - outputs/market_data.db 에 market_status_log가 존재
# - breadth_low / ma_cross_bearish / drawdown / vix_breakout / trend_bear 컬럼이 채워져 있어야 함

from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "outputs" / "market_data.db"
START_DATE = "2020-01-01"
END_DATE = "2025-12-31"


def main():
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    print(f"DB: {DB_PATH}")
    print(f"Period: {START_DATE} ~ {END_DATE}")
    print()

    # 1) 전체 breadth_low 발동 일수
    cur.execute("""
        SELECT
          COUNT(*) AS total_days,
          SUM(breadth_low) AS breadth_low_days,
          ROUND(100.0 * SUM(breadth_low) / COUNT(*), 2) AS breadth_low_pct
        FROM market_status_log
        WHERE date BETWEEN ? AND ?;
    """, (START_DATE, END_DATE))
    total_days, breadth_low_days, breadth_low_pct = cur.fetchone()

    print("=== Breadth Trigger Summary ===")
    print(f"Total days         : {total_days}")
    print(f"Breadth low days   : {breadth_low_days}")
    print(f"Breadth low pct    : {breadth_low_pct}%")
    print()

    # 2) breadth_low=1 인 날의 status 분포
    cur.execute("""
        SELECT status, COUNT(*) AS cnt
        FROM market_status_log
        WHERE date BETWEEN ? AND ?
          AND breadth_low = 1
        GROUP BY status
        ORDER BY cnt DESC, status ASC;
    """, (START_DATE, END_DATE))
    rows = cur.fetchall()

    print("=== Status distribution on breadth_low=1 days ===")
    if not rows:
        print("No rows found.")
    else:
        for status, cnt in rows:
            print(f"{status:10s} : {cnt}")
    print()

    # 3) breadth_low=1 이면서 다른 주요 트리거가 꺼져 있는 "단독 영향 가능성" 일수
    cur.execute("""
        SELECT COUNT(*)
        FROM market_status_log
        WHERE date BETWEEN ? AND ?
          AND breadth_low = 1
          AND ma_cross_bearish = 0
          AND drawdown = 0
          AND vix_breakout = 0
          AND trend_bear = 0;
    """, (START_DATE, END_DATE))
    standalone_days = cur.fetchone()[0]

    print("=== Breadth standalone candidate days ===")
    print(f"breadth_low=1 AND ma_cross_bearish=0 AND drawdown=0 AND vix_breakout=0 AND trend_bear=0")
    print(f"Count: {standalone_days}")
    print()

    # 4) 단독 영향 가능성이 있었던 날짜 샘플 보기 (최대 30개)
    cur.execute("""
        SELECT date, status, breadth_low, ma_cross_bearish, drawdown, vix_breakout, trend_bear
        FROM market_status_log
        WHERE date BETWEEN ? AND ?
          AND breadth_low = 1
          AND ma_cross_bearish = 0
          AND drawdown = 0
          AND vix_breakout = 0
          AND trend_bear = 0
        ORDER BY date ASC
        LIMIT 30;
    """, (START_DATE, END_DATE))
    sample_rows = cur.fetchall()

    print("=== Sample standalone candidate dates (up to 30) ===")
    if not sample_rows:
        print("No standalone candidate dates found.")
    else:
        for row in sample_rows:
            print(row)
    print()

    # 5) 참고: breadth_low=1 인 날에 다른 트리거들과 같이 얼마나 겹쳤는지
    cur.execute("""
        SELECT
          SUM(CASE WHEN ma_cross_bearish = 1 THEN 1 ELSE 0 END) AS with_ma_cross,
          SUM(CASE WHEN drawdown = 1 THEN 1 ELSE 0 END) AS with_drawdown,
          SUM(CASE WHEN vix_breakout = 1 THEN 1 ELSE 0 END) AS with_vix,
          SUM(CASE WHEN trend_bear = 1 THEN 1 ELSE 0 END) AS with_trend_bear
        FROM market_status_log
        WHERE date BETWEEN ? AND ?
          AND breadth_low = 1;
    """, (START_DATE, END_DATE))
    with_ma_cross, with_drawdown, with_vix, with_trend_bear = cur.fetchone()

    print("=== Overlap counts on breadth_low=1 days ===")
    print(f"With ma_cross_bearish : {with_ma_cross}")
    print(f"With drawdown         : {with_drawdown}")
    print(f"With vix_breakout     : {with_vix}")
    print(f"With trend_bear       : {with_trend_bear}")

    conn.close()


if __name__ == "__main__":
    main()