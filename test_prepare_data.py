import sys
from pathlib import Path

# 프로젝트 루트 경로 설정
ROOT = Path(__file__).resolve().parents[0]
sys.path.insert(0, str(ROOT))

import config as global_config
from core.config_factory import make_config
from core.backtest_engine import prepare_market_data

def test_prepare():
    start_date = "2024-01-01"
    end_date = "2026-03-01"
    
    config = make_config({}, start_date, end_date, fast_mode=False)
    print(f"Testing prepare_market_data with range: {start_date} ~ {end_date}")
    
    market_data, date_list = prepare_market_data(config)
    
    if not market_data:
        print("❌ market_data is empty!")
    else:
        print(f"✅ market_data found: {len(market_data)} dates")
        print(f"✅ sample data from {date_list[0]}: {len(market_data[date_list[0]])} tickers")

if __name__ == "__main__":
    test_prepare()
