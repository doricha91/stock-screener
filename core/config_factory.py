from core.portfolio_config import PORTFOLIO_CONFIG

def make_config(params: dict, start_date: str, end_date: str, fast_mode: bool = False):
    cfg = PORTFOLIO_CONFIG.copy()
    cfg.update(params)
    cfg["start_date"] = start_date
    cfg["end_date"] = end_date

    if fast_mode:
        cfg["_fast_mode"] = True
        cfg["use_market_regime"] = False
        cfg["target_tickers"] = ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA"]

    return cfg