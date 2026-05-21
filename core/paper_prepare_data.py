from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.paths import market_db_path
from core.universe_manager import compare_universe, fetch_live_basket_symbols, save_universe_snapshot
import data_processor
from screener import data_collector, data_manager


def normalize_prepare_date(date_str: str) -> str:
    clean_date = str(date_str).replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return datetime.strptime(clean_date, "%Y%m%d").strftime("%Y-%m-%d")


def collect_daily_tickers() -> list[str]:
    sp500 = data_collector.get_sp500_tickers()
    nasdaq100 = data_collector.get_nasdaq100_tickers()
    return sorted(set(sp500 + nasdaq100))


def refresh_universe_snapshot_for_date(date_str: str) -> Path:
    local_symbols = set(data_manager.get_ticker_list())
    live_symbols = fetch_live_basket_symbols()
    delta = compare_universe(live_symbols, local_symbols)
    snapshot_data = {
        "as_of": date_str,
        "active_symbols": sorted(live_symbols),
        "added": sorted(delta["added"]),
        "removed": sorted(delta["removed"]),
        "kept": sorted(delta["kept"]),
    }
    return save_universe_snapshot(snapshot_data, date_str)


def run_paper_prepare_data(
    date_str: str,
    *,
    skip_prices: bool = False,
    skip_indicators: bool = False,
    include_universe: bool = False,
) -> dict:
    normalized_date = normalize_prepare_date(date_str)
    tickers = collect_daily_tickers()

    summary = {
        "date": normalized_date,
        "ticker_count": len(tickers),
        "market_db_path": market_db_path(),
        "price_update_status": "skipped" if skip_prices else "pending",
        "indicators_update_status": "skipped" if skip_indicators else "pending",
        "universe_update_status": "skipped" if not include_universe else "pending",
        "universe_snapshot_path": None,
        "warnings": [],
        "errors": [],
    }

    if not skip_prices:
        try:
            data_collector.update_market_indices()
            data_collector.update_tickers_info(tickers)
            data_collector.update_stock_data(tickers)
            summary["price_update_status"] = "success"
        except Exception as exc:
            summary["price_update_status"] = "failed"
            summary["errors"].append(f"price/index/ticker refresh failed: {exc}")
            raise

    if not skip_indicators:
        try:
            data_processor.update_technical_indicators()
            summary["indicators_update_status"] = "success"
        except Exception as exc:
            summary["indicators_update_status"] = "failed"
            summary["errors"].append(f"daily_indicators refresh failed: {exc}")
            raise

    if include_universe:
        try:
            snapshot_path = refresh_universe_snapshot_for_date(normalized_date)
            summary["universe_update_status"] = "success"
            summary["universe_snapshot_path"] = str(snapshot_path)
        except Exception as exc:
            summary["universe_update_status"] = "failed"
            summary["errors"].append(f"universe snapshot refresh failed: {exc}")
            raise

    return summary


def format_paper_prepare_data_summary(summary: dict) -> str:
    lines = [
        "PAPER PREPARE DATA",
        f"  date: {summary['date']}",
        f"  ticker_count: {summary['ticker_count']}",
        f"  market_db_path: {summary['market_db_path']}",
        f"  prices/index/tickers: {summary['price_update_status']}",
        f"  daily_indicators: {summary['indicators_update_status']}",
        f"  universe: {summary['universe_update_status']}",
    ]
    if summary.get("universe_snapshot_path"):
        lines.append(f"  universe_snapshot_path: {summary['universe_snapshot_path']}")
    if summary["warnings"]:
        lines.append("  warnings:")
        lines.extend([f"    - {warning}" for warning in summary["warnings"]])
    else:
        lines.append("  warnings: none")
    if summary["errors"]:
        lines.append("  errors:")
        lines.extend([f"    - {error}" for error in summary["errors"]])
    else:
        lines.append("  errors: none")
    return "\n".join(lines)
