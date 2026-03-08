# tests/test_smoke_optimizer.py
import conftest
import os
import sqlite3
from core.optimizer_engine import run_optimization
from core.paths import backtest_log_db_path

def test_optimizer_engine():
    print("\n[Smoke Test] Optimizer Engine 시작...")
    
    # 1. 이전 테스트 기록과의 충돌 방지를 위해 DB 상태 확인
    db_path = backtest_log_db_path()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT count(*) FROM optimization_log")
        before_count = cur.fetchone()[0]
    except:
        before_count = 0
    conn.close()
    
    print(f"   - 실행 전 DB 레코드 수: {before_count}")

    try:
        # 2. 최적화 실행 (FAST_MODE는 conftest에서 설정됨)
        # optimizer_engine 내부에서 param_grid를 읽으므로, 
        # 실제 환경과 동일하게 실행하되 FAST_MODE 플래그를 전달함
        run_optimization(fast_mode=True)
        
        # 3. DB 저장 결과 확인
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM optimization_log")
        after_count = cur.fetchone()[0]
        
        # OOS 검증 테이블도 확인
        cur.execute("SELECT count(*) FROM oos_validation_log")
        oos_count = cur.fetchone()[0]
        conn.close()

        if after_count > before_count:
            print(f"   [OK] 최적화 결과 저장 확인: {before_count} -> {after_count}")
            print(f"   [OK] OOS 검증 결과 존재: {oos_count}행")
            return True
        else:
            print("   [FAIL] 최적화 결과가 DB에 저장되지 않았습니다.")
            return False

    except Exception as e:
        print(f"   [FAIL] 최적화 중 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_optimizer_engine()
    if success:
        print("[PASSED] Optimizer Smoke Test")
        exit(0)
    else:
        print("[FAILED] Optimizer Smoke Test")
        exit(1)
