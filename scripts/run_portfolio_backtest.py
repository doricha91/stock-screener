import os
import warnings

from core.config_factory import make_config
from core.backtest_engine import run_backtest_with_config
import config as global_config

warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore")

FAST_MODE = os.getenv("FAST_MODE", "0") == "1"

def run_portfolio_simulation():
    print("🚀 단독 백테스트 모드 (PortfolioDB 사용)")

    # make_config를 사용하여 global config(Hedge, Safety 등)를 동기화
    # 단독 백테스트는 config.py에 정의된 기간을 기본으로 사용
    start_date = global_config.IN_SAMPLE_START
    end_date = global_config.OUT_OF_SAMPLE_END # 전체 기간 테스트
    
    config = make_config({}, start_date, end_date, fast_mode=FAST_MODE)

    if config is None:
        raise ValueError("config must be provided")

    run_backtest_with_config(config, verbose=True)

if __name__ == "__main__":
    run_portfolio_simulation()