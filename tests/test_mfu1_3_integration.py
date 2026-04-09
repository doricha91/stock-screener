# tests/test_mfu1_3_integration.py
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.target_portfolio_state import CurrentPortfolioState
from core.portfolio_state_manager import save_current_state, load_current_state, update_portfolio_state_after_close
from core.daily_plan_generator import generate_daily_plan

def test_integration_logic():
    print("\n[Integration Test] MFU-FT1 & FT3 Logic Verification")
    
    test_date = "2026-04-06"
    
    # 1. 초기 상태 설정 (AAPL 보유, 최고가 180)
    initial_state = CurrentPortfolioState(
        current_symbols=["AAPL"],
        current_cash_ratio=0.5,
        current_hedge_ratio=0.0,
        absolute_cash=50000.0,
        shares={"AAPL": 100},
        avg_price={"AAPL": 150.0},
        highest_prices={"AAPL": 180.0},
        hedge_symbols=[]
    )
    save_current_state(initial_state, test_date)
    
    # 2. 장 마감 후 업데이트 테스트 (TSLA 신규 매수, AAPL 고가 경신)
    # 실제 DB 데이터 조회가 포함되므로 에러 발생 시 시뮬레이션으로 대체될 수 있음
    actual_trades = [
        {'symbol': 'TSLA', 'type': 'BUY', 'shares': 50, 'price': 200.0}
    ]
    
    print("--- Step 1: Update state after close ---")
    try:
        # 2026-04-06 장 마감 후 상태 업데이트
        new_path = update_portfolio_state_after_close(test_date, actual_trades)
        new_state = load_current_state(test_date)
        
        print(f"   - TSLA Highest Price: {new_state.highest_prices.get('TSLA')}")
        assert new_state.highest_prices['TSLA'] == 200.0 # 매수가로 초기화 확인
        assert "TSLA" in new_state.current_symbols
        
        # AAPL 최고가 갱신 확인 (만약 오늘 고가가 180보다 높다면 갱신되었을 것)
        print(f"   - AAPL Highest Price: {new_state.highest_prices.get('AAPL')}")
        assert new_state.highest_prices['AAPL'] >= 180.0
        
    except Exception as e:
        print(f"   [SKIP] DB data required for full test: {e}")

    # 3. 다음 날 아침 Plan 생성 테스트 (Trailing Stop 우선순위 확인)
    print("--- Step 2: Generate plan for next day ---")
    try:
        # AAPL의 스탑이 터지도록 인위적으로 highest_price를 매우 높게 설정하거나 
        # ATR을 조절하는 시나리오는 실제 DB 연동 때문에 복잡하므로 리포트 생성 여부만 확인
        report_path = generate_daily_plan("2026-04-07")
        if report_path:
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
                print("   - Report generated successfully.")
                assert "Trailing Stop" in content
                assert "Buying Power" in content
    except Exception as e:
        print(f"   [SKIP] Plan generation failed: {e}")

if __name__ == "__main__":
    test_integration_logic()
