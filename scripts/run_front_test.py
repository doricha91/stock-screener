# scripts/run_front_test.py
import sys
from pathlib import Path

# 프로젝트 루트 추가
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.preflight_check import run_preflight_checks
from core.daily_plan_generator import generate_daily_plan

def main():
    print("\n" + "◈"*30)
    print(" STOCK SCREENER - FRONT-TEST PIPELINE")
    print("◈"*30)

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
