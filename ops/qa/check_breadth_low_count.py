import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "outputs" / "market_data.db"

conn = sqlite3.connect(str(DB_PATH))
cur = conn.cursor()

cur.execute("""
SELECT
  COUNT(*) AS total_days,
  SUM(breadth_low) AS breadth_low_days,
  ROUND(100.0 * SUM(breadth_low) / COUNT(*), 2) AS breadth_low_pct
FROM market_status_log
WHERE date BETWEEN '2020-01-01' AND '2025-12-31';
""")
print(cur.fetchone())

conn.close()