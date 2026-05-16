import sqlite3
from pathlib import Path

db_path = Path("outputs/market_data.db")
print("DB exists:", db_path.exists(), db_path)

if not db_path.exists():
    raise SystemExit("ERROR: outputs/market_data.db not found")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

tables = ["daily_price", "daily_indicators", "market_index", "market_status_log"]

for table in tables:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    exists = cur.fetchone() is not None
    print(f"\n[{table}] exists:", exists)

    if exists:
        try:
            cur.execute(f"SELECT MIN(date), MAX(date), COUNT(*) FROM {table}")
            print("min/max/count:", cur.fetchone())
        except Exception as e:
            print("summary error:", e)

print("\n[latest daily_indicators dates]")
try:
    cur.execute("""
        SELECT date, COUNT(*)
        FROM daily_indicators
        GROUP BY date
        ORDER BY date DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print("daily_indicators date check error:", e)

print("\n[latest daily_price dates]")
try:
    cur.execute("""
        SELECT date, COUNT(*)
        FROM daily_price
        GROUP BY date
        ORDER BY date DESC
        LIMIT 10
    """)
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print("daily_price date check error:", e)

conn.close()