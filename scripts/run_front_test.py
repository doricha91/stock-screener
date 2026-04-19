# scripts/run_front_test.py
import sys
import sqlite3
import json
from pathlib import Path

# 프로젝트 루트 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import config
import market_analyzer
from core.preflight_check import run_preflight_checks
from core.daily_plan_generator import generate_daily_plan

def display_market_dashboard():
    """
    [MFU4 Step 3] 실전 상황 대시보드를 터미널에 출력합니다.
    최근 시장 국면의 변화와 현재 판정의 근거를 한눈에 보여줍니다.
    """
    print("\n" + "═"*60)
    print(" 📊 [MARKET STATUS DASHBOARD]")
    print("═"*60)

    try:
        # 1. DB 연결 및 최근 10일간의 국면 이력 조회
        from core.paths import market_db_path
        conn = sqlite3.connect(market_db_path())
        cur = conn.cursor()
        
        # 최근 10일치 기록 가져오기
        cur.execute("""
            SELECT date, status, vix_value, trade_halted, triggers 
            FROM market_status_log 
            ORDER BY date DESC LIMIT 10
        """)
        rows = cur.fetchall()
        conn.close()

        if not rows:
            print(" ⚠️ 최근 시장 국면 이력을 찾을 수 없습니다. (DB Empty)")
            return

        latest = rows[0] # 오늘(가장 최근) 데이터
        
        # 2. 최근 국면 추이(Transition) 생성
        history = [r[1] for r in reversed(rows)]
        transition_str = " ➔ ".join(history[-5:]) # 최근 5일치만 화살표로 연결
        
        # 3. 현재 국면 상세 정보 파싱
        status = latest[1]
        vix = latest[2]
        halted = "🚨 HALTED" if latest[3] else "✅ NORMAL"
        triggers = json.loads(latest[4]) if latest[4] else {}

        # 4. 화면 출력
        print(f" ● Current Date  : {latest[0]}")
        print(f" ● Current Regime: [{status}] ({halted})")
        print(f" ● Recent Flow   : {transition_str}")
        print("-" * 60)
        
        print(" [Critical Triggers]")
        print(f"  - VIX Index    : {vix:.2f} (Avg: {triggers.get('vix_ma', 0):.2f})")
        print(f"  - Market Breadth: {triggers.get('breadth_val', 0):.1f}% (Threshold: {config.BREADTH_THRESHOLD}%)")
        print(f"  - Trend Status : BULL={triggers.get('trend_bull')}, BEAR={triggers.get('trend_bear')}")
        print("-" * 60)

        # 5. 현재 적용 중인 정책 (config.py 연동)
        rule = config.REGIME_RULES.get(status, {})
        print(" [Action Policy]")
        print(f"  - Target Cash Ratio : {rule.get('target_cash_ratio', 0)*100:.0f}%")
        print(f"  - Stop-Loss Tightness: {rule.get('trailing_stop_multiplier', 0):.1f}x (ATR)")
        print(f"  - Strategy Weights   : Turtle({rule.get('weights',{}).get('turtle',0)}), RSI({rule.get('weights',{}).get('rsi',0)})")

    except Exception as e:
        print(f" ❌ 대시보드 출력 중 오류 발생: {e}")
    
    print("═"*60 + "\n")

def main():
    print("\n" + "◈"*30)
    print(" STOCK SCREENER - FRONT-TEST PIPELINE")
    print("◈"*30)

    # 0단계: 대시보드 출력 (MFU4)
    display_market_dashboard()

    # 1단계: 집행 전 체크리스트 (FT4)
    if not run_preflight_checks():
        print("🛑 [STP] Pipeline stopped due to preflight failure.")
        sys.exit(1)

    # 2단계: 일일 판단 산출물 생성 (FT1)
    try:
        report_path = generate_daily_plan()
        if report_path:
            print(f"\n✨ DONE! Action Plan is ready at:")
            print(f"👉 {report_path}")
        else:
            print("\n❌ Failed to generate Action Plan.")
    except Exception as e:
        print(f"\n❌ Unexpected error during pipeline: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
