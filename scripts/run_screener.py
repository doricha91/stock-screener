from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from screener import data_collector
from screener.screener import run_screener
import market_analyzer


def _collect_daily_tickers() -> list[str]:
    sp500 = data_collector.get_sp500_tickers()
    nasdaq100 = data_collector.get_nasdaq100_tickers()
    return sorted(set(sp500 + nasdaq100))


def main() -> None:
    print("[Step 1] Updating market data...")
    tickers = _collect_daily_tickers()
    data_collector.update_market_indices()
    data_collector.update_tickers_info(tickers)
    data_collector.update_stock_data(tickers)

    print("\n[Step 2] Evaluating market state...")
    market_state = market_analyzer.get_market_state()
    print(
        f"  Regime={market_state['regime']}, "
        f"TradeHalted={market_state['trade_halted']}"
    )

    print("\n[Step 3] Running screener...")
    results = run_screener(tickers=tickers, market_state=market_state, save=True)

    if results.empty:
        print("\nDaily screener finished with no candidates.")
    else:
        print(f"\nDaily screener finished with {len(results)} candidates.")


if __name__ == "__main__":
    main()
