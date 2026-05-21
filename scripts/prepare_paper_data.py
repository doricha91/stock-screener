from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.paper_prepare_data import (  # noqa: E402
    format_paper_prepare_data_summary,
    run_paper_prepare_data,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare minimal market-data inputs for paper daily plan. "
            "This command may update market_data.db and optional universe snapshot files."
        )
    )
    parser.add_argument("--date", required=True, help="Target date (YYYYMMDD or YYYY-MM-DD)")
    parser.add_argument("--universe", action="store_true", help="Refresh universe snapshot for the requested date")
    parser.add_argument("--skip-prices", action="store_true", help="Skip market index / tickers / daily price refresh")
    parser.add_argument("--skip-indicators", action="store_true", help="Skip daily_indicators refresh")
    args = parser.parse_args()

    summary = run_paper_prepare_data(
        args.date,
        skip_prices=args.skip_prices,
        skip_indicators=args.skip_indicators,
        include_universe=args.universe,
    )
    print(format_paper_prepare_data_summary(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
