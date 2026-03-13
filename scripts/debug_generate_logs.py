import os
import sys
import datetime

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.config_factory import make_config
from core.backtest_engine import run_backtest_with_config
import config as global_config

def generate_3y_final_logs():
    # 최종 비교 기간: 2023-01-01 ~ 2025-12-31 (정확히 3년)
    # 최근 3년 데이터를 사용하여 데이터 로딩 속도 최적화 및 최신 시장 트렌드 반영
    start_date = "2023-01-01"
    end_date = "2025-12-31"
    
    print(f"🚀 [최종 3개년 통합판] NASDAQ100 Hedge 비교 데이터 생성 시작")
    print(f"📅 기간: {start_date} ~ {end_date} (3 Years)")

    # 1. Hedge OFF 설정
    runtime_off = {
        "USE_HEDGE_MODE": False,
        "enable_decision_logging": True,
        "run_name": "final_3y_nasdaq100_off",
        "target_tickers": None  # NASDAQ100 전체 사용
    }
    
    print("\n--- [1/2] Hedge OFF 백테스트 시작 (3개년) ---")
    config_off = make_config({}, start_date, end_date, fast_mode=False, runtime_overrides=runtime_off)
    run_backtest_with_config(config_off, verbose=False)
    
    # 2. Hedge ON 설정
    runtime_on = {
        "USE_HEDGE_MODE": True,
        "enable_decision_logging": True,
        "run_name": "final_3y_nasdaq100_on",
        "target_tickers": None
    }
    
    print("\n--- [2/2] Hedge ON 백테스트 시작 (3개년) ---")
    config_on = make_config({}, start_date, end_date, fast_mode=False, runtime_overrides=runtime_on)
    run_backtest_with_config(config_on, verbose=False)
    
    print("\n✅ [완료] 최종 3개년 통합 비교 로그가 생성되었습니다 (outputs/logs/).")

if __name__ == "__main__":
    generate_3y_final_logs()
