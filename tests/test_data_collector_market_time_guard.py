import inspect

import screener.data_collector as dc


def test_update_market_indices_uses_market_time_helper():
    source = inspect.getsource(dc.update_market_indices)
    assert "should_skip_download_start_date" in source
    assert 'region="US"' in source
    assert "datetime.today().strftime" not in source
    assert 'ZoneInfo("US/Eastern")' not in source


def test_update_stock_data_uses_market_time_helper():
    source = inspect.getsource(dc.update_stock_data)
    assert "should_skip_download_start_date" in source
    assert 'region="US"' in source
    assert "datetime.today().strftime" not in source
    assert 'ZoneInfo("US/Eastern")' not in source
