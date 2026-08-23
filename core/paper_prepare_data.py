from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from core.paths import market_db_path
from core.stage_a_asof_contract import (
    StageAAsOfContext,
    StageAAsOfContractError,
    sha256_payload,
    validate_universe_snapshot,
)
from core.universe_manager import (
    compare_universe,
    fetch_live_basket_symbols,
    load_universe_snapshot_as_of_quarter,
    save_universe_snapshot,
)
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


def _load_official_universe_symbols(
    snapshot_path: Path,
    *,
    context: StageAAsOfContext,
) -> list[str]:
    try:
        payload = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise StageAAsOfContractError(
            "asof_provenance_invalid",
            f"Unable to read official universe snapshot: {snapshot_path}: {exc}",
            source="universe",
        ) from exc

    validate_universe_snapshot(payload, context=context, artifact_path=snapshot_path)
    symbols = sorted(
        {
            str(symbol).strip().upper()
            for symbol in payload["active_symbols"]
            if str(symbol).strip()
        }
    )
    if not symbols:
        raise StageAAsOfContractError(
            "asof_provenance_invalid",
            "Official universe snapshot has no canonical active_symbols",
            source="universe",
        )
    return symbols


def refresh_universe_snapshot_for_date(
    date_str: str,
    *,
    trade_date: str | None = None,
    account_id: str = "paper_default",
    observed_at: str | None = None,
) -> Path:
    if trade_date is not None:
        context = StageAAsOfContext.build(
            account_id=account_id,
            data_date=date_str,
            trade_date=trade_date,
            observed_at=observed_at,
        )
        selection = load_universe_snapshot_as_of_quarter(date_str)
        selected_path_raw = selection.get("metadata", {}).get("snapshot_path")
        selected_path = Path(str(selected_path_raw)) if selected_path_raw else None
        if selected_path is not None and selected_path.is_file():
            try:
                payload = json.loads(selected_path.read_text(encoding="utf-8"))
                validate_universe_snapshot(payload, context=context, artifact_path=selected_path)
                return selected_path
            except (OSError, UnicodeError, json.JSONDecodeError, StageAAsOfContractError) as exc:
                if context.historical:
                    detail = exc.detail if isinstance(exc, StageAAsOfContractError) else str(exc)
                    raise StageAAsOfContractError(
                        "historical_universe_snapshot_missing",
                        f"No valid immutable universe snapshot exists for {date_str}: {detail}",
                        source="universe",
                    ) from exc
        if context.historical:
            raise StageAAsOfContractError(
                "historical_universe_snapshot_missing",
                f"No valid immutable universe snapshot exists on or before {date_str}",
                source="universe",
            )

    local_symbols = set(data_manager.get_ticker_list())
    live_symbols = fetch_live_basket_symbols()
    delta = compare_universe(live_symbols, local_symbols)
    snapshot_data = {
        "as_of": date_str,
        "effective_as_of": date_str,
        "observed_at": context.observed_at if trade_date is not None else datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": "wikipedia_sp500_nasdaq100",
        "source_revision": sha256_payload(sorted(live_symbols)),
        "capture_mode": "current_day_live_capture" if trade_date is not None else "legacy_live_capture",
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
    trade_date: str | None = None,
    account_id: str = "paper_default",
    observed_at: str | None = None,
) -> dict:
    normalized_date = normalize_prepare_date(date_str)
    snapshot_path: Path | None = None
    if include_universe and trade_date is not None:
        context = StageAAsOfContext.build(
            account_id=account_id,
            data_date=normalized_date,
            trade_date=trade_date,
            observed_at=observed_at,
        )
        snapshot_path = refresh_universe_snapshot_for_date(
            normalized_date,
            trade_date=trade_date,
            account_id=account_id,
            observed_at=observed_at,
        )
        tickers = _load_official_universe_symbols(snapshot_path, context=context)
    else:
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
            if snapshot_path is None:
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
