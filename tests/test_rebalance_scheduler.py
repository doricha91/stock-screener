import pandas as pd
import pytest
from core.backtest_engine import is_rebalance_day

def test_is_rebalance_day_daily():
    # Daily인 경우 매일 True여야 함
    dates = pd.date_range("2023-01-01", "2023-01-10")
    for d in dates:
        assert is_rebalance_day(d, 'D') is True

def test_is_rebalance_day_weekly():
    # Weekly인 경우 금요일(weekday == 4)에만 True여야 함
    # 2023-01-06은 금요일
    assert is_rebalance_day(pd.Timestamp("2023-01-06"), 'W') is True
    # 2023-01-05는 목요일
    assert is_rebalance_day(pd.Timestamp("2023-01-05"), 'W') is False
    # 2023-01-07은 토요일
    assert is_rebalance_day(pd.Timestamp("2023-01-07"), 'W') is False

def test_is_rebalance_day_monthly():
    # Monthly인 경우 월말에만 True여야 함
    assert is_rebalance_day(pd.Timestamp("2023-01-31"), 'M') is True
    assert is_rebalance_day(pd.Timestamp("2023-01-30"), 'M') is False
    assert is_rebalance_day(pd.Timestamp("2023-02-28"), 'M') is True

def test_is_rebalance_day_quarterly():
    # Quarterly인 경우 분기말에만 True여야 함
    assert is_rebalance_day(pd.Timestamp("2023-03-31"), 'Q') is True
    assert is_rebalance_day(pd.Timestamp("2023-06-30"), 'Q') is True
    assert is_rebalance_day(pd.Timestamp("2023-01-31"), 'Q') is False

if __name__ == "__main__":
    pytest.main([__file__])
