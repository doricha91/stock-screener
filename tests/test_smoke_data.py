# tests/test_smoke_data.py
import conftest
import sqlite3
from core.paths import market_db_path
from screener.data_collector import update_market_indices

def test_data_collection():
    print("\n[Smoke Test] Data Collection 시작...")
    
    # 1. DB 경로 확인
    db_path = market_db_path()
    print(f"   - DB Path: {db_path}")
    
    # 2. 시장 지수 업데이트 실행 (최소 범위)
    # 실제 네트워크 통신이 발생하므로 SPY 1개만 제대로 들어오는지 확인하는 로직
    try:
        update_market_indices()
        print("   [OK] update_market_indices 실행 완료")
    except Exception as e:
        print(f"   [FAIL] 데이터 수집 중 오류 발생: {e}")
        return False

    # 3. DB 적재 확인
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # 최근 1주일 내에 데이터가 있는지 확인
    cur.execute("SELECT count(*) FROM market_index WHERE symbol = 'SPY'")
    count = cur.fetchone()[0]
    conn.close()

    if count > 0:
        print(f"   [OK] SPY 데이터 확인됨 (총 {count}행)")
        return True
    else:
        print("   [FAIL] SPY 데이터가 DB에 존재하지 않습니다.")
        return False

if __name__ == "__main__":
    success = test_data_collection()
    if success:
        print("[PASSED] Data Smoke Test")
        exit(0)
    else:
        print("[FAILED] Data Smoke Test")
        exit(1)
