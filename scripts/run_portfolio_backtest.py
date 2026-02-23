import os
import warnings

from core.portfolio_config import PORTFOLIO_CONFIG
from core.backtest_engine import run_backtest_with_config

warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.filterwarnings("ignore")

FAST_MODE = os.getenv("FAST_MODE", "0") == "1"

def run_portfolio_simulation():
    print("🚀 단독 백테스트 모드 (PortfolioDB 사용)")

    config = PORTFOLIO_CONFIG.copy()

    if FAST_MODE:
        config["_fast_mode"] = True
        config['start_date'] = '2024-01-01'
        config['end_date'] = '2024-06-30'
        config['use_market_regime'] = False
        config['target_tickers'] = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'TSLA']

    if config is None:
        raise ValueError("config must be provided")

    run_backtest_with_config(config, verbose=True)

if __name__ == "__main__":
    run_portfolio_simulation()