import sqlite3
import pandas as pd
import market_analyzer
import config
from pathlib import Path

def run_v2_validation():
    print("🔬 [검증 시작] Market Regime V2 로직 테스트 (Inertia & Priority)")
    print("-" * 60)

    conn = market_analyzer.get_db_connection()
    
    # 1. 최근 10일치 데이터를 가져와서 로직 시뮬레이션
    query = "SELECT date, status FROM market_status_log ORDER BY date DESC LIMIT 10"
    df_history = pd.read_sql(query, conn)
    
    if df_history.empty:
        print("❌ DB에 국면 로그가 없습니다. 먼저 데이터 업데이트가 필요합니다.")
        conn.close()
        return

    print("📜 [최근 국면 이력]")
    print(df_history.to_string(index=False))
    print("-" * 60)

    # 2. 개별 트리거 상황 가정 테스트
    test_cases = [
        {
            "name": "강력한 하락장 (SPY/QQQ 200일선 하회)",
            "triggers": {"spy_below_200": True, "qqq_below_200": True, "vix_breakout": False, "drawdown": False},
            "prev": "BULL", "dur": 3, "expected": "BULL"  # 관성(5일) 때문에 BULL 유지 기대
        },
        {
            "name": "관성 돌파 (5일 이상 유지 후 전환)",
            "triggers": {"spy_below_200": True, "qqq_below_200": True, "vix_breakout": False, "drawdown": False},
            "prev": "BULL", "dur": 6, "expected": "BEAR"  # 5일 지났으므로 BEAR 전환 기대
        },
        {
            "name": "PANIC 즉시 발동 (관성 무시)",
            "triggers": {"spy_below_200": False, "qqq_below_200": False, "vix_breakout": True, "drawdown": True},
            "prev": "BULL", "dur": 1, "expected": "PANIC" # 1일차여도 PANIC은 즉시 발동
        },
        {
            "name": "브레드스 경고 (WARNING)",
            "triggers": {"breadth_low": "WARNING", "spy_below_50": True},
            "prev": "BULL", "dur": 10, "expected": "UNSTABLE"
        }
    ]

    success_count = 0
    for case in test_cases:
        print(f"▶ 테스트 케이스: {case['name']}")
        result = market_analyzer._decide_regime(case['triggers'], case['prev'], case['dur'])
        
        if result == case['expected']:
            print(f"✅ PASS: {case['prev']}({case['dur']}일) -> {result}")
            success_count += 1
        else:
            print(f"❌ FAIL: {case['prev']}({case['dur']}일) -> Expected {case['expected']}, Got {result}")
        print("-" * 30)

    print(f"\n✅ 최종 결과: {success_count}/{len(test_cases)} 통과")
    conn.close()

if __name__ == "__main__":
    run_v2_validation()
