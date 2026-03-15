import sqlite3
import os
import sys
from pathlib import Path

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.optimizer_storage import ensure_table_exists, TABLE_NAME
from core.paths import market_db_path

def verify_schema_update():
    db_path = "outputs/backtest_log.db"
    if not os.path.exists(db_path):
        print(f"⚠️ DB 파일이 존재하지 않습니다: {db_path}")
        return

    print(f"🔍 DB 스키마 검증 시작: {db_path}")
    conn = sqlite3.connect(db_path)
    
    # 1. 스키마 보강 함수 호출 (파라미터 예시: entry_period, exit_period)
    ensure_table_exists(conn, ["entry_period", "exit_period"])
    
    # 2. 컬럼 존재 여부 확인
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
    columns = [row[1] for row in cursor.fetchall()]
    
    required_cols = ['mode_change_count', 'regime_change_count', 'order_blocked_count']
    all_passed = True
    
    print("\n[컬럼 체크 결과]")
    for col in required_cols:
        if col in columns:
            print(f"✅ {col}: 존재함")
        else:
            print(f"❌ {col}: 누락됨")
            all_passed = False
            
    conn.close()
    
    if all_passed:
        print("\n✨ 모든 신규 컬럼이 정상적으로 DB 스키마에 반영되었습니다.")
    else:
        print("\n❗ 일부 컬럼이 누락되었습니다. 로직 확인이 필요합니다.")

if __name__ == "__main__":
    verify_schema_update()
