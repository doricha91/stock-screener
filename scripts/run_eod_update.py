# scripts/run_eod_update.py
import sys
import argparse
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.execution_logger import parse_journal_from_markdown, append_to_execution_log, map_journal_to_trades
from core.portfolio_state_manager import update_portfolio_state_after_close, load_current_state
from core.performance_tracker import PerformanceTracker
from core.paths import FRONT_TEST_DIR

def main():
    parser = argparse.ArgumentParser(description="End-of-Day Front-test Update")
    parser.add_argument("--date", type=str, help="Target date (YYYYMMDD). Defaults to latest report.")
    args = parser.parse_args()

    print("\n" + "🌙"*30)
    print(" STOCK SCREENER - NIGHTLY CLOSE PIPELINE")
    print("🌙"*30)

    # 1. 대상 리포트 파일 결정
    if args.date:
        clean_date = args.date.replace("-", "")
        report_path = FRONT_TEST_DIR / f"daily_action_plan_{clean_date}.md"
    else:
        # 가장 최근 리포트 탐색
        reports = sorted(list(FRONT_TEST_DIR.glob("daily_action_plan_*.md")), reverse=True)
        if not reports:
            print("❌ No action plan reports found.")
            sys.exit(1)
        report_path = reports[0]
        clean_date = report_path.name.replace("daily_action_plan_", "").replace(".md", "")

    print(f"📂 Processing report: {report_path.name}")

    # 2. 마크다운 파싱 및 검증 (FT5)
    try:
        journal_entries = parse_journal_from_markdown(report_path)
        actual_trades = []
        trade_net_amount = 0.0
        
        if journal_entries:
            append_to_execution_log(journal_entries)
            actual_trades = map_journal_to_trades(journal_entries)
            # 오늘 매매 총액 계산 (BUY는 양수, SELL은 음수 수량이므로 - 곱함)
            for t in actual_trades:
                trade_net_amount += (t['shares'] * t['price'])
        
        # 3. 예상 잔고 계산 및 현금 입력 검증 (지침 1, 2 반영)
        from core.portfolio_state_manager import load_current_state
        from core.execution_logger import clean_numeric
        
        prev_state = load_current_state() # 이전 날짜 스냅샷
        expected_cash = prev_state.absolute_cash - trade_net_amount
        
        actual_cash = 0.0
        retry_count = 0
        while retry_count < 3:
            raw_cash_input = input(f"\n💰 오늘 장 마감 실제 계좌 총 현금(예상: ${expected_cash:,.2f}) 입력: ")
            try:
                actual_cash = float(clean_numeric(raw_cash_input))
                
                # 오차 검증
                diff = abs(actual_cash - expected_cash)
                error_rate = (diff / expected_cash * 100) if expected_cash != 0 else 0
                
                # 지침 3: 이중 임계값 (10% 오차 또는 $5,000 차이)
                if error_rate > 10.0 or diff > 5000.0:
                    print(f"\n⚠️  [WARNING] 입력값(${actual_cash:,.2f})이 예상치(${expected_cash:,.2f})와 크게 다릅니다!")
                    print(f"   - 오차: ${diff:,.2f} ({error_rate:.2f}%)")
                    confirm = input("👉 오타가 아닙니까? 정말 이 금액으로 동기화할까요? [y/N]: ")
                    if confirm.lower() != 'y':
                        print("🔄 재입력을 시도합니다.")
                        retry_count += 1
                        continue
                
                break # 검증 통과
            except ValueError:
                print("❌ 유효한 숫자를 입력하세요.")
                retry_count += 1

        if retry_count >= 3:
            print("🛑 [BLOCK] 과도한 입력 오류로 마감을 중단합니다.")
            sys.exit(1)

        print(f"🔄 현금 잔고를 ${actual_cash:,.2f}로 최종 동기화합니다.")

    except ValueError as e:
        print(f"\n🛑 [BLOCK] {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)

    # 4. 포트폴리오 상태 갱신 (FT3 연동)
    try:
        formatted_date = f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:]}"
        new_state_path = update_portfolio_state_after_close(
            formatted_date, 
            actual_trades, 
            actual_cash=actual_cash
        )
        print(f"✅ Portfolio state updated and saved to snapshot: {new_state_path.name}")

        # 5. 성과 추적 기록 (FT8 연동)
        updated_state = load_current_state(formatted_date)
        tracker = PerformanceTracker()
        tracker.update_performance(formatted_date, updated_state)

    except Exception as e:
        print(f"\n❌ Failed to update portfolio state or track performance: {e}")
        sys.exit(1)

    print("\n✨ NIGHTLY CLOSE COMPLETE. Ready for tomorrow's preflight check.")
    print("🌙"*30 + "\n")

if __name__ == "__main__":
    main()
