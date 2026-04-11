import os
import warnings
import datetime

from core.config_factory import make_config
from core.backtest_engine import run_backtest_with_config
import config as global_config

warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore")

FAST_MODE = os.getenv("FAST_MODE", "0") == "1"

def run_portfolio_simulation():
    print("🚀 단독 백테스트 모드 (PortfolioDB 사용)")

    # 1. 고유한 run_id 생성 (결과 저장을 위해 필수)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"backtest_{timestamp}"

    # 2. 오버라이드 설정 (로깅 및 결과 저장 활성화)
    overrides = {
        "run_id": run_id,
        "enable_decision_logging": True
    }

    # make_config를 사용하여 global config를 동기화
    start_date = global_config.IN_SAMPLE_START
    end_date = global_config.OUT_OF_SAMPLE_END # 전체 기간 테스트
    
    config = make_config({}, start_date, end_date, fast_mode=FAST_MODE, runtime_overrides=overrides)

    if config is None:
        raise ValueError("config must be provided")

    print(f"📅 테스트 기간: {start_date} ~ {end_date}")
    print(f"🔄 리밸런싱 주기: {config.get('REBALANCE_FREQUENCY', 'D')}")
    print(f"🆔 실행 ID: {run_id}")
    print(f"📂 결과 저장: outputs/logs/, outputs/summary/ 경로 확인 요망")

    results = run_backtest_with_config(config, verbose=True)
    
    if results and 'all_trades' in results:
        print(f"\n✅ 백테스트 완료. 총 {len(results['all_trades'])}건의 거래가 기록되었습니다.")


if __name__ == "__main__":
    run_portfolio_simulation()
