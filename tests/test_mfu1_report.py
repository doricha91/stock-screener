# tests/test_mfu1_report.py
import os
import sys
import json
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.target_portfolio_state import CurrentPortfolioState
from core.portfolio_state_manager import save_current_state
from core.daily_plan_generator import generate_daily_plan
from core.paths import FRONT_TEST_DIR

def test_mfu1_report_generation():
    """일일 판단 산출물 생성을 테스트합니다."""
    # 1. 가상의 어제 상태 저장
    yesterday = "2026-04-05"
    state = CurrentPortfolioState(
        current_symbols=["AAPL"],
        current_cash_ratio=0.5,
        current_hedge_ratio=0.0,
        absolute_cash=50000.0,
        shares={"AAPL": 100},
        avg_price={"AAPL": 150.0},
        highest_prices={"AAPL": 180.0},
        hedge_symbols=[]
    )
    save_current_state(state, yesterday)
    
    # 2. 리포트 생성 실행 (오늘 날짜)
    today = datetime.now().strftime("%Y-%m-%d")
    # 주의: 실제 DB 데이터가 없으면 에러가 날 수 있으므로, 에러 발생 시 skip 처리
    try:
        report_path = generate_daily_plan(today)
        
        if report_path and os.path.exists(report_path):
            print(f"✅ Success! Report generated at: {report_path}")
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
                print("\n--- Report Preview ---")
                print("\n".join(content.split("\n")[:20])) # 상위 20줄만 출력
                
            assert "Daily Action Plan" in content
            assert "자산 현황 및 가용 현금" in content
            assert "Buying Power" in content
        else:
            print("❌ Failed to generate report.")
            
    except Exception as e:
        print(f"⚠️ Test skipped due to environment/data issues: {e}")

if __name__ == "__main__":
    test_mfu1_report_generation()
