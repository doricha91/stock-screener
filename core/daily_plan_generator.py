# core/daily_plan_generator.py
import json
import os
import sqlite3
import sys
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

import config
import market_analyzer
from screener.screener import build_screener_results
from core.portfolio_state_manager import load_current_state
from core.target_portfolio_state import (
    build_target_portfolio_state, 
    evaluate_rebalance_need,
    get_cash_policy_status,
    calculate_available_buying_power,
    CurrentPortfolioState,
    TargetPortfolioState,
    RebalanceDecision
)
from core.paths import front_daily_action_plan_path, market_db_path
from core.backtest_engine import evaluate_switching_opportunity
from core.config_factory import make_config, get_regime_config
from core.decision_core import compute_candidate_score
from core.paper_config_snapshot import save_paper_config_snapshot
from core.paper_config_hash import PAPER_CONFIG_HASH_POLICY, compute_paper_config_hash_from_file
from core.position_sizing import calculate_entry_shares
from core.universe_manager import load_universe_snapshot_as_of_quarter

ACTION_BUY = "BUY"
ACTION_SELL = "SELL"

REVIEW_EXIT = "REVIEW_EXIT"

WARNING_STALE_HOLDING = "WARNING_STALE_HOLDING"
WARNING_UNIVERSE_REMOVED_HOLDING = "WARNING_UNIVERSE_REMOVED_HOLDING"
WARNING_STALE_CANDIDATE = "WARNING_STALE_CANDIDATE"
WARNING_RS_CALC_FAILED = "WARNING_RS_CALC_FAILED"
WARNING_DATA_INSUFFICIENT = "WARNING_DATA_INSUFFICIENT"
WARNING_LOW_BUYING_POWER = "WARNING_LOW_BUYING_POWER"
WARNING_HIGHEST_PRICE_MISSING = "WARNING_HIGHEST_PRICE_MISSING"
WARNING_HIGHEST_PRICE_INVALID = "WARNING_HIGHEST_PRICE_INVALID"
WARNING_HIGHEST_PRICE_META_MISSING = "WARNING_HIGHEST_PRICE_META_MISSING"
WARNING_HIGHEST_PRICE_STALE = "WARNING_HIGHEST_PRICE_STALE"
WARNING_HIGHEST_PRICE_INCONSISTENT = "WARNING_HIGHEST_PRICE_INCONSISTENT"

SEVERITY_LOW = "LOW"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_HIGH = "HIGH"

DAILY_PLAN_JSON_SCHEMA_VERSION = "paper_daily_plan.v1"


def _configure_console_encoding() -> None:
    """Best-effort UTF-8 console setup for Windows terminals."""
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def load_market_index_series(symbol: str, end_date: str, start_date: str | None = None) -> pd.Series:
    """Load benchmark/index close series from market_index up to end_date."""
    conn = sqlite3.connect(market_db_path())
    try:
        params: list[str] = [symbol, end_date]
        query = """
            SELECT date, close
            FROM market_index
            WHERE symbol = ? AND date <= ?
        """
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
        query += " ORDER BY date ASC"
        df = pd.read_sql(query, conn, params=params)
    finally:
        conn.close()

    if df.empty:
        return pd.Series(dtype="float64")

    df["date"] = pd.to_datetime(df["date"])
    df["close"] = pd.to_numeric(df["close"], errors="coerce")
    return df.set_index("date")["close"].dropna()


def load_price_history_until(symbol: str, end_date: str, lookback_days: int = 10) -> pd.DataFrame:
    """Load stock price history ending on or before end_date without look-ahead."""
    end_ts = pd.to_datetime(end_date)
    start_date = (end_ts - pd.Timedelta(days=lookback_days)).strftime("%Y-%m-%d")
    df = data_manager.get_price_data(symbol, start_date=start_date, end_date=end_date)
    if df is None or df.empty:
        return pd.DataFrame()
    return df.sort_index()[df.index <= end_ts]


def calculate_candidate_rs_val(
    symbol: str,
    asof_date: pd.Timestamp,
    benchmark_close: pd.Series,
    rs_lookback: int,
) -> Optional[float]:
    """Calculate candidate relative strength using only history up to asof_date."""
    if benchmark_close is None or benchmark_close.empty:
        return None

    history_days = max(rs_lookback * 3, rs_lookback + 30)
    start_date = (asof_date - pd.Timedelta(days=history_days)).strftime("%Y-%m-%d")
    end_date = asof_date.strftime("%Y-%m-%d")

    stock_df = data_manager.get_price_data(symbol, start_date=start_date, end_date=end_date)
    if stock_df is None or stock_df.empty or 'close' not in stock_df.columns:
        return None

    stock_close = stock_df.sort_index()['close']
    stock_close = stock_close[stock_close.index <= asof_date]
    bench_close = benchmark_close[benchmark_close.index <= asof_date]

    common_index = stock_close.index.intersection(bench_close.index)
    if len(common_index) <= rs_lookback:
        return None

    stock_common = stock_close.loc[common_index]
    bench_common = bench_close.loc[common_index]

    stock_ret = stock_common.pct_change(rs_lookback).iloc[-1]
    bench_ret = bench_common.pct_change(rs_lookback).iloc[-1]
    if pd.isna(stock_ret) or pd.isna(bench_ret):
        return None

    return float(stock_ret - bench_ret)


def _parse_state_date(value: Any) -> Optional[pd.Timestamp]:
    """Parse front-test state dates supporting both YYYYMMDD and YYYY-MM-DD."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return pd.Timestamp(datetime.strptime(text, fmt))
        except ValueError:
            continue

    try:
        parsed = pd.to_datetime(text, errors="coerce")
        if pd.isna(parsed):
            return None
        return pd.Timestamp(parsed)
    except Exception:
        return None


def diagnose_highest_price_state(
    symbol: str,
    data_date: str,
    current_state: CurrentPortfolioState,
    close: Optional[float],
    high: Optional[float] = None,
) -> tuple[Optional[float], str, List[Dict[str, Any]], List[str]]:
    """Diagnose highest_price state and return a safe front-test highest value."""
    warning_entries: List[Dict[str, Any]] = []
    notes: List[str] = []
    highest_source = "unavailable"
    highest_price: Optional[float] = None
    asof_date = pd.to_datetime(data_date)

    has_snapshot_key = symbol in current_state.highest_prices
    snapshot_highest_raw = current_state.highest_prices.get(symbol)
    snapshot_highest: Optional[float] = None

    if not has_snapshot_key:
        warning_entries.append({
            "symbol": symbol,
            "reason": WARNING_HIGHEST_PRICE_MISSING,
            "severity": SEVERITY_HIGH,
            "note": "current_state.highest_prices에 값이 없어 current price fallback을 사용합니다.",
        })
        notes.append("highest_price missing")
    else:
        try:
            snapshot_highest = float(snapshot_highest_raw)
            if snapshot_highest <= 0:
                raise ValueError("highest_price must be > 0")
        except (TypeError, ValueError):
            snapshot_highest = None
            warning_entries.append({
                "symbol": symbol,
                "reason": WARNING_HIGHEST_PRICE_INVALID,
                "severity": SEVERITY_HIGH,
                "note": f"snapshot highest_price 값이 유효하지 않습니다: {snapshot_highest_raw}",
            })
            notes.append("highest_price invalid")

    meta = current_state.highest_price_meta.get(symbol)
    if meta is None:
        warning_entries.append({
            "symbol": symbol,
            "reason": WARNING_HIGHEST_PRICE_META_MISSING,
            "severity": SEVERITY_MEDIUM,
            "note": "highest_price_meta가 없어 마지막 highest update 시점을 확인할 수 없습니다.",
        })
        notes.append("highest_price_meta missing")
    else:
        updated_at = _parse_state_date(meta.get("updated_at"))
        if updated_at is None:
            warning_entries.append({
                "symbol": symbol,
                "reason": WARNING_HIGHEST_PRICE_META_MISSING,
                "severity": SEVERITY_MEDIUM,
                "note": "highest_price_meta.updated_at를 파싱할 수 없습니다.",
            })
            notes.append("highest_price_meta updated_at unreadable")
        else:
            stale_days = max((asof_date - updated_at).days, 0)
            if stale_days > 0:
                warning_entries.append({
                    "symbol": symbol,
                    "reason": WARNING_HIGHEST_PRICE_STALE,
                    "severity": SEVERITY_MEDIUM,
                    "note": f"highest_price metadata가 {stale_days}일 오래되었습니다. updated_at={meta.get('updated_at')}",
                })
                notes.append(f"highest_price stale ({stale_days}d)")

    observed_reference = None
    if high is not None:
        observed_reference = float(high)
    elif close is not None:
        observed_reference = float(close)

    if (
        snapshot_highest is not None
        and observed_reference is not None
        and snapshot_highest < observed_reference
    ):
        warning_entries.append({
            "symbol": symbol,
            "reason": WARNING_HIGHEST_PRICE_INCONSISTENT,
            "severity": SEVERITY_HIGH,
            "note": (
                f"snapshot highest_price({snapshot_highest:.2f})가 최근 관측값({observed_reference:.2f})보다 낮아 "
                "max(snapshot,current)를 사용합니다."
            ),
        })
        notes.append("highest_price below latest observed value")

    if close is not None:
        if snapshot_highest is None:
            highest_price = float(close)
            highest_source = "current_only"
        else:
            highest_price = max(float(snapshot_highest), float(close))
            highest_source = "snapshot" if float(snapshot_highest) >= float(close) else "max(snapshot,current)"
    elif snapshot_highest is not None:
        highest_price = float(snapshot_highest)
        highest_source = "snapshot"

    return highest_price, highest_source, warning_entries, notes


def compute_holding_score_for_switching(
    symbol: str,
    data_date: str,
    active_weights: dict,
    benchmark_close: pd.Series,
    rs_lookback: int,
    rs_weight: float,
    merged_config: dict,
) -> tuple[float | None, float | None, list[str]]:
    """Recompute a holding score from latest data for switching evaluation only."""
    asof_date = pd.to_datetime(data_date)
    history_days = max(400, rs_lookback * 3)
    start_date = (asof_date - pd.Timedelta(days=history_days)).strftime("%Y-%m-%d")
    df = data_manager.get_price_data(symbol, start_date=start_date, end_date=data_date)
    if df is None or df.empty:
        return None, None, []

    df = df.sort_index()
    df = df[df.index <= asof_date]
    if len(df) < 130:
        return None, None, []

    context = merged_config.copy()
    context["symbol"] = symbol

    try:
        df = indicator.add_turtle_indicators(df, context)
        df = indicator.add_atr_indicators(df, context)
        df = indicator.add_rsi_indicators(df, context)
        df = indicator.add_sma_indicators(df, context)
        df = indicator.add_bollinger_band_indicators(df, context)
        df = indicator.add_macd_indicators(df, context)
        df = indicator.add_bbs_indicators(df, context)
        df = indicator.add_dema_indicators(df, context)
        df = indicator.add_volume_indicators(df, context)
        df = strategy.apply_ensemble_strategy(df, context)
    except Exception:
        return None, None, []

    if df.empty:
        return None, None, []

    latest_row = df.iloc[-1]
    score, reasons = compute_candidate_score(latest_row, active_weights)
    rs_val = calculate_candidate_rs_val(symbol, asof_date, benchmark_close, rs_lookback)
    if rs_val is not None and rs_val > 0:
        score += rs_weight

    return float(score), rs_val, reasons


def build_holding_sell_diagnostic(
    symbol: str,
    data_date: str,
    current_state: CurrentPortfolioState,
    merged_config: dict,
) -> Dict[str, Any]:
    """Build read-only SELL diagnostics for a current holding without affecting actions."""
    asof_date = pd.to_datetime(data_date)
    history_days = 400
    start_date = (asof_date - pd.Timedelta(days=history_days)).strftime("%Y-%m-%d")
    notes: List[str] = []
    close = None
    exit_low = None
    sell_signal = None
    atr = None
    atr_source = "unavailable"
    high = None
    highest_price = None
    highest_source = "unavailable"
    stop_price = None
    trailing_triggered = None
    highest_warnings: List[Dict[str, Any]] = []
    highest_meta = current_state.highest_price_meta.get(symbol, {})
    if highest_meta:
        meta_parts = []
        if highest_meta.get("updated_at"):
            meta_parts.append(f"highest_meta updated_at={highest_meta.get('updated_at')}")
        if highest_meta.get("basis"):
            meta_parts.append(f"basis={highest_meta.get('basis')}")
        if highest_meta.get("source"):
            meta_parts.append(f"source={highest_meta.get('source')}")
        if meta_parts:
            notes.append(" ".join(meta_parts))

    df = data_manager.get_price_data(symbol, start_date=start_date, end_date=data_date)
    if df is None or df.empty:
        notes.append("price history unavailable")
    else:
        df = df.sort_index()
        df = df[df.index <= asof_date]
        if df.empty:
            notes.append("no rows on or before data_date")
        else:
            context = merged_config.copy()
            context["symbol"] = symbol
            try:
                df = indicator.add_turtle_indicators(df, context)
                df = indicator.add_atr_indicators(df, context)
                df = indicator.add_rsi_indicators(df, context)
                df = indicator.add_sma_indicators(df, context)
                df = indicator.add_bollinger_band_indicators(df, context)
                df = indicator.add_macd_indicators(df, context)
                df = indicator.add_bbs_indicators(df, context)
                df = indicator.add_dema_indicators(df, context)
                df = indicator.add_volume_indicators(df, context)
                df = strategy.apply_ensemble_strategy(df, context)
            except Exception as exc:
                notes.append(f"indicator/strategy pipeline failed: {exc}")

            if not df.empty:
                latest_row = df.iloc[-1]
                close_val = latest_row.get("close")
                if pd.notna(close_val):
                    close = float(close_val)

                high_val = latest_row.get("high")
                if pd.notna(high_val):
                    high = float(high_val)

                exit_low_val = latest_row.get("exit_low")
                if pd.notna(exit_low_val):
                    exit_low = float(exit_low_val)
                    if close is not None:
                        sell_signal = close < exit_low
                else:
                    notes.append("exit_low unavailable")

                atr_val = latest_row.get("atr")
                if pd.notna(atr_val) and float(atr_val) > 0:
                    atr = float(atr_val)
                    atr_source = "indicator"
                elif close is not None:
                    atr = close * 0.02
                    atr_source = "fallback_close_2pct"
                    notes.append("ATR fallback used")
                else:
                    notes.append("ATR unavailable")

    highest_price, highest_source, highest_warnings, highest_notes = diagnose_highest_price_state(
        symbol,
        data_date,
        current_state,
        close,
        high=high,
    )
    notes.extend(highest_notes)

    if close is not None and atr is not None and highest_price is not None:
        trailing_triggered, stop_price = check_trailing_stop_manual(
            symbol,
            float(close),
            float(highest_price),
            float(atr),
            merged_config.get('trailing_stop_multiplier', getattr(config, 'TRAILING_STOP_MULTIPLIER', 2.5)),
        )

    return {
        "symbol": symbol,
        "high": high,
        "close": close,
        "exit_low": exit_low,
        "sell_signal": sell_signal,
        "atr": atr,
        "atr_source": atr_source,
        "highest_price": highest_price,
        "highest_source": highest_source,
        "highest_meta_updated_at": highest_meta.get("updated_at"),
        "highest_meta_basis": highest_meta.get("basis"),
        "highest_meta_source": highest_meta.get("source"),
        "highest_warning_reasons": [str(item.get("reason", "")) for item in highest_warnings],
        "stop_price": stop_price,
        "trailing_triggered": trailing_triggered,
        "review_status": "-",
        "warning_status": "-",
        "warning_items": highest_warnings,
        "notes": "; ".join(notes) if notes else "",
    }


def build_candidate_filter_diagnostics(
    formatted_candidates: List[Dict[str, Any]],
    score_threshold: float,
    data_date: str,
) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Build read-only diagnostics that mirror current candidate filters."""
    diagnostics: List[Dict[str, Any]] = []
    summary = {
        "total": 0,
        "pass": 0,
        "failed_score": 0,
        "failed_rs": 0,
        "failed_rs_calc": 0,
        "failed_entry": 0,
        "stale": 0,
    }
    data_ts = pd.to_datetime(data_date)

    for candidate in formatted_candidates:
        summary["total"] += 1
        symbol = candidate.get("symbol", "N/A")
        latest_price_date = candidate.get("latest_price_date")
        latest_ts = pd.to_datetime(latest_price_date) if latest_price_date else None
        stale_days = max((data_ts - latest_ts).days, 0) if latest_ts is not None else None

        score = candidate.get("score")
        rs_val = candidate.get("rs_val")
        entry_signal = bool(candidate.get("entry_signal", False))
        score_ok = pd.notna(score) and float(score) >= float(score_threshold)
        rs_ok = pd.notna(rs_val) and float(rs_val) > 0

        fail_reason = "pass"
        if not entry_signal:
            fail_reason = "entry_signal_false"
            summary["failed_entry"] += 1
        elif pd.isna(score):
            fail_reason = "missing_score"
            summary["failed_score"] += 1
        elif float(score) < float(score_threshold):
            fail_reason = "score_below_threshold"
            summary["failed_score"] += 1
        elif not candidate.get("rs_calc_success", True):
            fail_reason = "rs_calc_failed"
            summary["failed_rs_calc"] += 1
        elif pd.isna(rs_val):
            fail_reason = "missing_rs_val"
            summary["failed_rs_calc"] += 1
        elif float(rs_val) <= 0:
            fail_reason = "rs_lte_0"
            summary["failed_rs"] += 1

        passed = fail_reason == "pass"
        if passed:
            summary["pass"] += 1

        stale_flag = stale_days is not None and stale_days > 0
        if stale_flag:
            summary["stale"] += 1

        display_reason = "stale_data" if stale_flag else fail_reason

        diagnostics.append({
            "symbol": symbol,
            "latest_price_date": latest_price_date or "N/A",
            "data_date": data_date,
            "stale_days": stale_days if stale_days is not None else "N/A",
            "score": score if pd.notna(score) else None,
            "score_threshold": score_threshold,
            "rs_val": rs_val if pd.notna(rs_val) else None,
            "entry_signal": entry_signal,
            "score_ok": score_ok,
            "rs_ok": rs_ok,
            "pass": passed,
            "fail_reason": display_reason,
        })

    return diagnostics, summary


def is_stale_candidate(
    latest_price_date: Optional[str],
    data_date: str,
    max_days: int = 7,
) -> tuple[bool, Optional[int]]:
    """Return whether a candidate is stale relative to data_date."""
    try:
        if not latest_price_date:
            return True, None
        latest_ts = pd.to_datetime(latest_price_date)
        data_ts = pd.to_datetime(data_date)
        stale_days = max((data_ts - latest_ts).days, 0)
        return stale_days > max_days, stale_days
    except Exception:
        return True, None

def check_trailing_stop_manual(
    symbol: str, 
    current_price: float, 
    highest_price_so_far: float, 
    atr: float, 
    multiplier: float = 2.5
) -> tuple[bool, float]:
    """
    JSON 스냅샷 데이터를 기반으로 트레일링 스탑 여부를 판단합니다.
    - 반환값: (is_triggered, stop_price)
    """
    # 최고가 갱신
    new_highest = max(highest_price_so_far, current_price)
    
    # ATR이 유효하지 않으면 보수적으로 현재가의 2% 사용
    safe_atr = atr if atr > 0 else (current_price * 0.02)
    stop_price = new_highest - (safe_atr * multiplier)
    
    is_triggered = current_price < stop_price
    return is_triggered, stop_price

from screener import data_manager, indicator, strategy


def resolve_daily_plan_output_path(
    plan_date: str,
    output_path: str | Path | None = None,
) -> Path:
    if output_path is None:
        return front_daily_action_plan_path(plan_date)
    return Path(output_path)


def resolve_daily_plan_json_sidecar_path(
    markdown_output_path: str | Path,
    json_sidecar_path: str | Path | None = None,
) -> Path:
    if json_sidecar_path is not None:
        return Path(json_sidecar_path)
    return Path(markdown_output_path).with_suffix(".json")


def _json_scalar(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return str(value)


def normalize_daily_plan_item(item: Dict[str, Any]) -> Dict[str, Any]:
    normalized = {
        "symbol": _json_scalar(item.get("symbol")),
        "action": _json_scalar(item.get("type", item.get("action"))),
        "quantity": _json_scalar(item.get("shares", item.get("quantity"))),
        "price": _json_scalar(item.get("price")),
        "warning": _json_scalar(item.get("warning")),
        "reason": _json_scalar(item.get("reason")),
        "note": _json_scalar(item.get("note")),
    }
    return normalized


def build_daily_plan_json_payload(
    *,
    account_id: str,
    plan_date: str,
    data_date: str | None = None,
    trade_date: str | None = None,
    run_mode: str,
    official_run: bool,
    action_items: List[Dict[str, Any]],
    generated_at: str | None = None,
    fingerprints: Dict[str, Any] | None = None,
    config_snapshot_path: str | Path | None = None,
    state_snapshot_path: str | Path | None = None,
) -> Dict[str, Any]:
    resolved_fingerprints = build_daily_plan_fingerprints(
        fingerprints=fingerprints,
        config_snapshot_path=config_snapshot_path,
        state_snapshot_path=state_snapshot_path,
    )
    return {
        "schema_version": DAILY_PLAN_JSON_SCHEMA_VERSION,
        "account_id": account_id,
        "data_date": data_date or plan_date,
        "trade_date": trade_date or plan_date,
        "plan_date": plan_date,
        "run_mode": run_mode,
        "official_run": bool(official_run),
        "generated_at": generated_at or datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "items": [normalize_daily_plan_item(item) for item in action_items],
        "fingerprints": resolved_fingerprints,
    }


def build_daily_plan_fingerprints(
    *,
    fingerprints: Dict[str, Any] | None = None,
    config_snapshot_path: str | Path | None = None,
    state_snapshot_path: str | Path | None = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {"generator_version": DAILY_PLAN_JSON_SCHEMA_VERSION}
    if config_snapshot_path is not None:
        result["config_snapshot_path"] = str(config_snapshot_path)
        config_hash = compute_paper_config_hash_from_file(config_snapshot_path)
        if config_hash:
            result["config_hash"] = config_hash
            result["config_hash_policy"] = PAPER_CONFIG_HASH_POLICY
    if state_snapshot_path is not None:
        result["state_snapshot_path"] = str(state_snapshot_path)
    if fingerprints:
        result.update({key: _json_scalar(value) for key, value in fingerprints.items()})
    return result


def write_daily_plan_json_sidecar(
    *,
    path: str | Path,
    payload: Dict[str, Any],
) -> Path:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def is_buy_signal_candidate(candidate: Dict[str, Any], score_threshold: float) -> bool:
    """Match the backtest buy_signal gate: score >= threshold and rs_val > 0."""
    score = candidate.get("score")
    rs_val = candidate.get("rs_val")

    try:
        score = float(score)
        rs_val = float(rs_val)
    except (TypeError, ValueError):
        return False

    if pd.isna(score) or pd.isna(rs_val):
        return False

    return bool(score >= float(score_threshold) and rs_val > 0)


def filter_switch_candidates_for_daily_plan(
    df_candidates: pd.DataFrame,
    score_threshold: float,
) -> pd.DataFrame:
    """Restrict switching candidates to backtest-like buy_signal candidates only."""
    if df_candidates.empty:
        return df_candidates.copy()

    switch_candidates = df_candidates.copy()
    if "rs_val" not in switch_candidates.columns:
        switch_candidates["rs_val"] = 0.0

    mask = switch_candidates.apply(
        lambda row: is_buy_signal_candidate(row, score_threshold),
        axis=1,
    )
    return switch_candidates.loc[mask].copy()


def build_switch_action_items(
    switch_pairs: List[Dict[str, Any]],
    current_state: CurrentPortfolioState,
    current_prices: Dict[str, float],
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    """Build switch SELL/BUY actions and track symbols already consumed for the day."""
    action_items: list[dict[str, Any]] = []
    processed_sell_symbols: set[str] = set()
    planned_buy_symbols: set[str] = set()

    for pair in switch_pairs:
        s_sell = pair["sell_symbol"]
        s_buy = pair["buy_symbol"]
        b_row = pair["buy_row"]

        shares_to_sell = current_state.shares[s_sell]
        sell_price = current_prices.get(s_sell, 0)
        action_items.append({
            "type": ACTION_SELL,
            "symbol": s_sell,
            "shares": shares_to_sell,
            "price": sell_price,
            "reason": f"SWITCH_OUT (to {s_buy}, Score Gap: {pair['score_gap']:.1f})"
        })

        if s_buy in planned_buy_symbols:
            processed_sell_symbols.add(s_sell)
            continue

        price_buy = b_row["close"]
        shares_to_buy = int((shares_to_sell * sell_price) / price_buy)
        if shares_to_buy > 0:
            action_items.append({
                "type": ACTION_BUY,
                "symbol": s_buy,
                "shares": shares_to_buy,
                "price": price_buy,
                "reason": f"SWITCH_IN (from {s_sell})"
            })
            planned_buy_symbols.add(s_buy)

        processed_sell_symbols.add(s_sell)

    return action_items, processed_sell_symbols, planned_buy_symbols


def build_strategy_entry_action_items(
    rebalance_symbol_diff_added: List[str],
    current_state: CurrentPortfolioState,
    formatted_candidates: List[Dict[str, Any]],
    cp_status: Dict[str, Any],
    target_cash_ratio: float,
    max_positions: int,
    planned_buy_symbols: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Build non-switch BUY actions while preventing same-day duplicate BUY symbols."""
    existing_buy_symbols = set(planned_buy_symbols or set())
    action_items: list[dict[str, Any]] = []

    buying_power = calculate_available_buying_power(
        current_state.absolute_cash,
        cp_status["total_equity"],
        target_cash_ratio,
        buffer_ratio=0.02,
    )

    for symbol in rebalance_symbol_diff_added:
        if symbol in current_state.current_symbols or symbol in existing_buy_symbols:
            continue

        price = 0
        for candidate in formatted_candidates:
            if candidate["symbol"] == symbol:
                price = candidate["price"]
                break

        if price <= 0:
            continue

        shares_to_buy = calculate_entry_shares(
            total_equity=cp_status["total_equity"],
            available_buying_power=buying_power,
            price=price,
            max_positions=max_positions,
        )
        if shares_to_buy <= 0:
            continue

        action_items.append({
            "type": ACTION_BUY,
            "symbol": symbol,
            "shares": shares_to_buy,
            "price": price,
            "reason": "STRATEGY_ENTRY"
        })
        existing_buy_symbols.add(symbol)
        buying_power -= (shares_to_buy * price)

    return action_items


def generate_daily_plan(
    date_str: str = None,
    data_date: str | None = None,
    current_state: CurrentPortfolioState | None = None,
    output_path: str | Path | None = None,
    market_state_write_log: bool = True,
    config_snapshot_path: str | Path | None = None,
    config_snapshot_archive_dir: str | Path | None = None,
    config_snapshot_source: str = "daily_plan_generator",
    account_id: str = "paper_default",
    run_mode: str = "exploratory",
    official_run: bool = False,
    json_sidecar_path: str | Path | None = None,
    write_json_sidecar: bool = True,
    sidecar_fingerprints: Dict[str, Any] | None = None,
    state_snapshot_path: str | Path | None = None,
) -> str:
    """
    일일 판단 산출물(Action Plan)을 생성하고 파일로 저장합니다.
    """
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    plan_date = date_str
    explicit_data_date = data_date is not None
    requested_data_date = data_date or plan_date

    _configure_console_encoding()
        
    print(f"[START] Generating Daily Action Plan for {plan_date}...")

    # 1. 현재 상태 로드 (FT3)
    if current_state is None:
        try:
            current_state = load_current_state()
        except Exception as e:
            print(f"[ERROR] Failed to load current state: {e}")
            return ""

    # 2. 시장 국면 판단
    m_state = market_analyzer.get_market_state(
        target_date=requested_data_date,
        write_log=market_state_write_log,
    )
    data_date = m_state["date"]
    trade_date = plan_date
    signal_date = data_date if explicit_data_date else plan_date
    regime = m_state["regime"]
    print(f"[INFO] plan_date={plan_date}, data_date={data_date}, trade_date={trade_date}")
    base_config = make_config({}, data_date, data_date)
    merged_config = get_regime_config(regime, base_config)
    rs_lookback = int(merged_config.get('rs_lookback', 120))
    benchmark_symbol = merged_config.get('MARKET_BENCHMARK_SYMBOL', 'SPY')
    asof_date = pd.to_datetime(data_date)
    bench_start = (asof_date - pd.Timedelta(days=max(rs_lookback * 3, rs_lookback + 30))).strftime("%Y-%m-%d")
    benchmark_close = load_market_index_series(
        benchmark_symbol,
        end_date=data_date,
        start_date=bench_start,
    )
    universe_selection = load_universe_snapshot_as_of_quarter(signal_date)
    universe_snapshot = universe_selection.get("snapshot", {})
    universe_metadata = universe_selection.get("metadata", {})
    removed_universe_symbols = {
        str(symbol).strip().upper()
        for symbol in universe_snapshot.get("removed", [])
        if str(symbol).strip()
    }
    removed_candidate_exclusions: List[Dict[str, Any]] = []
    stale_holdings_alert: List[str] = []
    
    # 3. 신규 매수 후보 스크리닝 (Raw Signals)
    df_candidates = build_screener_results(market_state=m_state, end_date=signal_date)
    if not df_candidates.empty and removed_universe_symbols:
        symbol_col = "Symbol" if "Symbol" in df_candidates.columns else "symbol" if "symbol" in df_candidates.columns else None
        if symbol_col:
            excluded_candidates = sorted(
                {
                    str(symbol).strip().upper()
                    for symbol in df_candidates[symbol_col].tolist()
                    if str(symbol).strip().upper() in removed_universe_symbols
                }
            )
            if excluded_candidates:
                removed_candidate_exclusions = [
                    {"symbol": symbol, "reason": "universe_removed"}
                    for symbol in excluded_candidates
                ]
                df_candidates = df_candidates[
                    ~df_candidates[symbol_col].astype(str).str.strip().str.upper().isin(removed_universe_symbols)
                ].copy()
                print(
                    "⚠️ [Freshness Guard] Excluded stale/removed candidates: "
                    + ", ".join(excluded_candidates)
                )
    if not df_candidates.empty:
        df_candidates = df_candidates.rename(columns={
            'Symbol': 'symbol',
            'Price': 'close',
            'Score': 'score',
        }).copy()
        if 'rs_val' not in df_candidates.columns:
            rs_values: List[float] = []
            rs_calc_success: List[bool] = []
            rs_success = 0
            rs_positive = 0
            for symbol in df_candidates['symbol'].tolist():
                rs_val = calculate_candidate_rs_val(symbol, asof_date, benchmark_close, rs_lookback)
                if rs_val is None:
                    rs_values.append(0.0)
                    rs_calc_success.append(False)
                    continue
                rs_values.append(rs_val)
                rs_calc_success.append(True)
                rs_success += 1
                if rs_val > 0:
                    rs_positive += 1

            df_candidates['rs_val'] = rs_values
            df_candidates['rs_calc_success'] = rs_calc_success
            rs_failed = len(df_candidates) - rs_success
            print(
                f"RS calc: candidates={len(df_candidates)}, success={rs_success}, "
                f"failed={rs_failed}, positive={rs_positive}"
            )
            if rs_success == 0:
                print("[WARN] RS calc failed for all candidates; target selection may remain empty.")
    
    # [MFU 6-4] Phase 4: 실시간 국면 가중치 적용 (백테스트 엔진과 동일 로직)
    # 현재 국면 가중치 구성 (config.REGIME_RULES 및 전역 기본값 병합)
    active_weights = {
        'turtle': merged_config.get('turtle_weight', 1.0),
        'rsi': merged_config.get('rsi_weight', 1.0),
        'sma': merged_config.get('sma_weight', 1.0),
        'bbands': merged_config.get('bbands_weight', 1.0),
        'macd': merged_config.get('macd_weight', 1.0),
        'bbs': merged_config.get('bbs_weight', 1.0),
        'dema': merged_config.get('dema_weight', 1.0),
        'obv': merged_config.get('obv_weight', 0.5),
        'mfi': merged_config.get('mfi_weight', 0.5),
        'vol_spike': merged_config.get('vol_spike_weight', 0.5),
    }

    if not df_candidates.empty:
        # 모든 후보에 대해 실시간 점수 계산 (백테스트와 100% 동일 가중치)
        # build_screener_results에서 온 컬럼명(Signal_*)을 compute_candidate_score가 이해하는 형식으로 매핑
        signal_cols = [f"signal_{name}" for name in active_weights.keys()]
        if any(col in df_candidates.columns for col in signal_cols):
            df_candidates['score'], _ = compute_candidate_score(df_candidates, active_weights)
        
        # RS 가중치 합산
        rs_weight = merged_config.get('rs_weight', getattr(config, 'RS_WEIGHT', 1.0))
        if rs_weight > 0:
            rs_series = df_candidates['rs_val'] if 'rs_val' in df_candidates.columns else pd.Series(0.0, index=df_candidates.index)
            df_candidates['score'] += (rs_series > 0).astype(float) * rs_weight
        
        # 실시간 기준에 따른 최종 필터링 및 정렬
        score_threshold = merged_config.get('score_threshold', getattr(config, 'SCORE_THRESHOLD', 1.5))
        sort_col = 'rs_val' if 'rs_val' in df_candidates.columns else 'score'
        df_candidates = df_candidates[df_candidates['score'] >= score_threshold].sort_values(by=sort_col, ascending=False)

    stale_candidate_max_days = int(merged_config.get('stale_candidate_max_days', 7))
    candidate_rows = df_candidates.to_dict(orient='records') if not df_candidates.empty else []
    stale_exclusions: List[Dict[str, Any]] = []
    formatted_candidates = []
    for c in candidate_rows:
        latest_price_date = c.get('Date', c.get('date'))
        stale_flag, stale_days = is_stale_candidate(latest_price_date, signal_date, stale_candidate_max_days)
        if stale_flag:
            stale_exclusions.append({
                'symbol': c['symbol'],
                'latest_price_date': latest_price_date or "N/A",
                'stale_days': stale_days if stale_days is not None else "N/A",
            })
            continue

        formatted_candidates.append({
            'symbol': c['symbol'],
            'score': c['score'],
            'rs_val': c.get('rs_val', 0.0),
            'rs_calc_success': c.get('rs_calc_success', True),
            'latest_price_date': latest_price_date,
            'entry_signal': is_buy_signal_candidate(c, score_threshold),
            'price': c['close']
        })
    print(
        f"Stale candidate filter: excluded={len(stale_exclusions)}, "
        f"kept={len(formatted_candidates)}, threshold={stale_candidate_max_days}d"
    )

    # 4. 목표 상태 빌드 및 리밸런싱 판단
    score_threshold = merged_config.get('score_threshold', getattr(config, 'SCORE_THRESHOLD', 1.5))
    candidate_diagnostics, candidate_diag_summary = build_candidate_filter_diagnostics(
        formatted_candidates,
        score_threshold,
        signal_date,
    )
    print(
        "Candidate filter summary: "
        f"total={candidate_diag_summary['total']}, "
        f"pass={candidate_diag_summary['pass']}, "
        f"failed_score={candidate_diag_summary['failed_score']}, "
        f"failed_rs={candidate_diag_summary['failed_rs']}, "
        f"failed_rs_calc={candidate_diag_summary['failed_rs_calc']}, "
        f"failed_entry={candidate_diag_summary['failed_entry']}, "
        f"stale={candidate_diag_summary['stale']}"
    )
    target_state = build_target_portfolio_state(regime, formatted_candidates, merged_config)
    rebalance = evaluate_rebalance_need(current_state, target_state, merged_config)
    
    # 총 자산 계산을 위해 현재 보유 종목의 최신가 필요
    # ... (생략된 기존 가격 수집 로직)
    total_stock_value = 0
    current_prices = {}
    for s in current_state.current_symbols:
        if s in removed_universe_symbols:
            stale_holdings_alert.append(s)
            print(
                f"⚠️ [Freshness Guard] Holding {s} is listed in latest universe snapshot removed list. Review manually."
            )
        try:
            df = load_price_history_until(s, data_date, lookback_days=10)
            price = df.iloc[-1]['close'] if not df.empty else current_state.avg_price[s]
            current_prices[s] = price
            total_stock_value += (current_state.shares[s] * price)
        except:
            current_prices[s] = current_state.avg_price[s]
            total_stock_value += (current_state.shares[s] * current_state.avg_price[s])

    cp_status = get_cash_policy_status(
        current_state.absolute_cash, 
        current_state.absolute_cash + total_stock_value,
        target_state.target_cash_ratio
    )

    # [MFU 5] 능동적 스위칭 (Active Switching) 판단
    switch_pairs = []
    if not df_candidates.empty and current_state.current_symbols:
        # 1. 현재 보유 종목 점수 재계산 (백테스트와 동일 로직)
        current_pos_scores = []
        # 국면별 가중치 가져오기 (config.REGIME_RULES 참조)
        candidates_by_symbol = df_candidates.set_index('symbol', drop=False) if 'symbol' in df_candidates.columns else pd.DataFrame()
        
        from core.decision_core import compute_candidate_score
        
        for s in current_state.current_symbols:
            try:
                # 최신 지표가 포함된 데이터 필요 (screener/indicator.py 활용 권장하나, 여기서는 후보군 생성 시 계산된 값 참조가 어려우므로 단순화된 비교 수행)
                # 실전에서는 build_screener_results()가 이미 모든 종목(보유주 포함)의 점수를 계산하도록 설계되어 있어야 함.
                # 현재 build_screener_results는 후보만 반환하므로, 보유주가 후보에 포함되지 않았을 경우를 대비해 기본 점수 획득 로직 필요.
                
                # 보유 종목이 후보군(df_candidates)에 있다면 그 점수를 사용
                if not candidates_by_symbol.empty and s in candidates_by_symbol.index:
                    score = candidates_by_symbol.loc[s, 'score']
                    holding_rs = candidates_by_symbol.loc[s, 'rs_val'] if 'rs_val' in candidates_by_symbol.columns else None
                    print(
                        f"Holding switching score: {s} score={float(score):.2f} "
                        f"rs={'N/A' if pd.isna(holding_rs) else f'{float(holding_rs):.4f}'} reasons=candidate_reuse"
                    )
                else:
                    rs_weight = merged_config.get('rs_weight', getattr(config, 'RS_WEIGHT', 1.0))
                    score, holding_rs, holding_reasons = compute_holding_score_for_switching(
                        s,
                        data_date,
                        active_weights,
                        benchmark_close,
                        rs_lookback,
                        rs_weight,
                        merged_config,
                    )
                    if score is None:
                        print(f"[WARN] Skipping switching score for {s}: unable to compute holding score")
                        continue
                    reason_text = ",".join(holding_reasons) if holding_reasons else "none"
                    print(
                        f"Holding switching score: {s} score={float(score):.2f} "
                        f"rs={'N/A' if holding_rs is None or pd.isna(holding_rs) else f'{float(holding_rs):.4f}'} "
                        f"reasons={reason_text}"
                    )
                
                p_ret = (current_prices[s] - current_state.avg_price[s]) / current_state.avg_price[s] if current_state.avg_price[s] > 0 else 0
                current_pos_scores.append({
                    'symbol': s, 'score': score, 'return': p_ret, 
                    'shares': current_state.shares[s], 'price': current_prices[s]
                })
            except Exception as e:
                print(f"[WARN] Failed to re-evaluate score for {s}: {e}")

        current_pos_scores.sort(key=lambda x: x['score'])

        # 2. 교체 기회 평가
        # backtest parity: switch-in candidates must satisfy buy_signal-like gate
        c_df = filter_switch_candidates_for_daily_plan(df_candidates, score_threshold)

        if current_pos_scores:
            switch_pairs = evaluate_switching_opportunity(c_df, current_pos_scores, merged_config)
        else:
            print("[WARN] Skipping active switching: no holding scores could be computed.")

    # 5. 상세 행동 산출 (매도/매수 수량)
    action_items = []
    rebalance_review_items = []
    warning_items = []
    if universe_metadata.get("warning"):
        warning_items.append({
            "type": "UNIVERSE_SNAPSHOT_WARNING",
            "note": universe_metadata["warning"],
        })
    holding_sell_diagnostics: List[Dict[str, Any]] = []
    processed_symbols = set()
    stop_alerts = [] # 트레일링 스탑 감시 목록
    
    # [MFU 5] 5-0. 교체 매매 액션 추가 (최우선 순위 - 슬롯 확보용)
    switch_action_items, processed_symbols, switch_buy_symbols = build_switch_action_items(
        switch_pairs,
        current_state,
        current_prices,
    )
    action_items.extend(switch_action_items)

    for symbol in current_state.current_symbols:
        if symbol in processed_symbols:
            continue
        shares = current_state.shares.get(symbol, 0)
        if shares <= 0:
            continue

    # 5-1. 매도 판단 (Trailing Stop 및 일반 리밸런싱 매도)
        try:
            diag = build_holding_sell_diagnostic(symbol, data_date, current_state, merged_config)
            holding_sell_diagnostics.append(diag)
            for warning in diag.get("warning_items", []):
                warning_items.append(warning)

            if diag["atr_source"] in {"fallback_close_2pct", "unavailable"}:
                note = "보유 종목 trailing stop ATR이 indicator 기반으로 계산되지 않아 fallback/unavailable 상태입니다."
                if diag["notes"]:
                    note = f"{note} ({diag['notes']})"
                warning_items.append({
                    "symbol": symbol,
                    "reason": WARNING_DATA_INSUFFICIENT,
                    "severity": SEVERITY_MEDIUM,
                    "note": note,
                })

            if (
                diag["trailing_triggered"] is True
                and diag["close"] is not None
                and diag["stop_price"] is not None
            ):
                action_items.append({
                    "type": ACTION_SELL,
                    "symbol": symbol,
                    "shares": shares,
                    "price": diag["close"],
                    "reason": f"TRAILING_STOP (Triggered at ${float(diag['stop_price']):.2f})"
                })
                processed_symbols.add(symbol)
                continue

            if (
                diag["trailing_triggered"] is False
                and diag["close"] is not None
                and diag["stop_price"] is not None
            ):
                stop_alerts.append({
                    "symbol": symbol,
                    "stop_price": diag["stop_price"],
                    "current_price": diag["close"],
                    "distance": ((diag["close"] - diag["stop_price"]) / diag["close"]) * 100
                })
        except Exception as e:
            print(f"[WARN] Trailing stop check failed for {symbol}: {e}")
            holding_sell_diagnostics.append({
                "symbol": symbol,
                "close": None,
                "exit_low": None,
                "sell_signal": None,
                "atr": None,
                "atr_source": "unavailable",
                "highest_price": None,
                "highest_source": "unavailable",
                "highest_meta_updated_at": None,
                "highest_meta_basis": None,
                "highest_meta_source": None,
                "highest_warning_reasons": [],
                "stop_price": None,
                "trailing_triggered": None,
                "review_status": "-",
                "warning_status": "-",
                "warning_items": [],
                "notes": f"trailing stop diagnostic failed: {e}",
            })
            warning_items.append({
                "symbol": symbol,
                "reason": WARNING_DATA_INSUFFICIENT,
                "severity": SEVERITY_MEDIUM,
                "note": f"trailing stop diagnostic failed: {e}",
            })

        # (B) 리밸런싱 매도 체크 (전략적 제외)
        if symbol in rebalance.symbol_diff_removed and symbol not in processed_symbols:
            rebalance_review_items.append({
                "symbol": symbol,
                "shares": shares,
                "price": current_prices.get(symbol, 0),
                "reason": REVIEW_EXIT,
                "note": "Target portfolio에서 제외됨. 즉시 매도 지시가 아니라 수동 검토 대상."
            })

    # 5-2. 매수 판단
    buying_power = calculate_available_buying_power(
        current_state.absolute_cash,
        cp_status['total_equity'],
        target_state.target_cash_ratio,
        buffer_ratio=0.02
    )
    if rebalance.symbol_diff_added and buying_power <= 0:
        warning_items.append({
            "symbol": "-",
            "reason": WARNING_LOW_BUYING_POWER,
            "severity": SEVERITY_MEDIUM,
            "note": "매수 후보가 있으나 현재 가용 Buying Power가 부족하거나 0입니다.",
        })
    
    action_items.extend(
        build_strategy_entry_action_items(
            rebalance.symbol_diff_added,
            current_state,
            formatted_candidates,
            cp_status,
            target_state.target_cash_ratio,
            merged_config["max_positions"],
            planned_buy_symbols=switch_buy_symbols,
        )
    )

    for symbol in sorted(set(stale_holdings_alert)):
        warning_items.append({
            "symbol": symbol,
            "reason": WARNING_UNIVERSE_REMOVED_HOLDING,
            "severity": SEVERITY_MEDIUM,
            "note": "latest universe snapshot removed list에 포함되어 수동 확인 필요",
        })

    review_symbols = {item["symbol"]: item["reason"] for item in rebalance_review_items}
    warning_by_symbol: Dict[str, List[str]] = {}
    for item in warning_items:
        warning_symbol = str(item.get("symbol", "")).strip()
        if not warning_symbol or warning_symbol == "-":
            continue
        warning_by_symbol.setdefault(warning_symbol, []).append(str(item.get("reason", "")))

    incomplete_holding_diag = 0
    atr_source_counts = {"indicator": 0, "fallback_close_2pct": 0, "unavailable": 0}
    for diag in holding_sell_diagnostics:
        symbol = diag["symbol"]
        diag["review_status"] = review_symbols.get(symbol, "-")
        diag["warning_status"] = ",".join(warning_by_symbol.get(symbol, [])) or "-"
        atr_source = str(diag.get("atr_source", "unavailable"))
        if atr_source in atr_source_counts:
            atr_source_counts[atr_source] += 1
        if (
            diag["close"] is None
            or diag["exit_low"] is None
            or diag["atr_source"] == "unavailable"
            or diag["trailing_triggered"] is None
        ):
            incomplete_holding_diag += 1

    # 6. 마크다운 리포트 생성
    report_path = resolve_daily_plan_output_path(plan_date, output_path)
    
    # 기록용 사전 기입 데이터 준비 (MFU-FT2 긴급 수정 반영)
    journal_rows = []
    for item in action_items:
        reason = str(item.get("reason", ""))
        if reason.startswith("REVIEW") or reason.startswith("WARNING"):
            print(f"[WARN] Skipping non-action item from journal: {item.get('symbol')} {reason}")
            continue
        journal_rows.append({
            "date": plan_date,
            "regime": regime,
            "symbol": item['symbol'],
            "type": item['type'],
            "rec_shares": item['shares'],
            "rec_price": f"{item['price']:.2f}"
        })

    if rebalance_review_items:
        print(
            f"Rebalance review items: {len(rebalance_review_items)} moved from immediate SELL to review-only"
        )
    if warning_items:
        print(f"Warning items: {len(warning_items)} review-only warnings recorded")
    print(
        f"Holding sell diagnostics: {len(holding_sell_diagnostics)} analyzed, "
        f"{incomplete_holding_diag} incomplete"
    )
    print(
        "Trailing stop ATR source: "
        f"indicator={atr_source_counts['indicator']}, "
        f"fallback={atr_source_counts['fallback_close_2pct']}, "
        f"unavailable={atr_source_counts['unavailable']}"
    )

    report_content = format_markdown_report(
        plan_date,
        m_state,
        cp_status,
        action_items,
        stop_alerts,
        journal_rows,
        holding_sell_diagnostics=holding_sell_diagnostics,
        rebalance_review_items=rebalance_review_items,
        warning_items=warning_items,
        candidate_diagnostics=candidate_diagnostics,
        stale_exclusions=stale_exclusions,
        stale_candidate_max_days=stale_candidate_max_days,
        removed_candidate_exclusions=removed_candidate_exclusions,
        stale_holdings_alert=stale_holdings_alert,
        data_date=data_date,
        trade_date=trade_date,
    )
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_content)

    if config_snapshot_path is not None and config_snapshot_archive_dir is not None:
        save_paper_config_snapshot(
            plan_date=plan_date,
            data_date=data_date,
            trade_date=trade_date,
            market_state=m_state,
            final_config=merged_config,
            output_path=Path(config_snapshot_path),
            archive_dir=Path(config_snapshot_archive_dir),
            source=config_snapshot_source,
            market_state_write_log=market_state_write_log,
            universe_metadata=universe_metadata,
        )

    if write_json_sidecar:
        sidecar_path = resolve_daily_plan_json_sidecar_path(report_path, json_sidecar_path)
        sidecar_payload = build_daily_plan_json_payload(
            account_id=account_id,
            plan_date=plan_date,
            data_date=data_date,
            trade_date=trade_date,
            run_mode=run_mode,
            official_run=official_run,
            action_items=action_items,
            fingerprints=sidecar_fingerprints,
            config_snapshot_path=config_snapshot_path,
            state_snapshot_path=state_snapshot_path,
        )
        write_daily_plan_json_sidecar(path=sidecar_path, payload=sidecar_payload)
        
    print(f"[OK] Action Plan saved to: {report_path}")
    return str(report_path)

def format_markdown_report(
    date_str: str,
    m_state: dict,
    cp_status: dict,
    action_items: List[dict],
    stop_alerts: List[dict],
    journal_rows: List[dict],
    holding_sell_diagnostics: Optional[List[Dict[str, Any]]] = None,
    rebalance_review_items: Optional[List[Dict[str, Any]]] = None,
    warning_items: Optional[List[Dict[str, Any]]] = None,
    candidate_diagnostics: Optional[List[Dict[str, Any]]] = None,
    stale_exclusions: Optional[List[Dict[str, Any]]] = None,
    stale_candidate_max_days: int = 7,
    removed_candidate_exclusions: Optional[List[Dict[str, Any]]] = None,
    stale_holdings_alert: Optional[List[str]] = None,
    data_date: str | None = None,
    trade_date: str | None = None,
) -> str:
    """마크다운 리포트 템플릿을 작성합니다."""
    # ... (상단 로직 유지)
    regime = m_state['regime']
    vix = m_state['vix_value']
    
    summary_action = "관망 (Wait)"
    if any(item['type'] == ACTION_SELL for item in action_items):
        summary_action = "매도 및 리밸런싱 (Sell/Rebalance)"
    elif any(item['type'] == ACTION_BUY for item in action_items):
        summary_action = "신규 매수 (Buy)"
    
    if regime == "PANIC":
        summary_action = "패닉 모드: 매수 금지 / 현금 확보 (PANIC: No Buy)"

    stale_holdings_notice = ""
    if stale_holdings_alert:
        joined = ", ".join(sorted(set(stale_holdings_alert)))
        stale_holdings_notice = (
            f"\n> ⚠️ 주의: 보유 종목 중 `{joined}` 이(가) 유니버스(지수)에서 편출되었거나 "
            "데이터가 정지되었을 수 있습니다. 확인 요망!\n"
        )

    display_data_date = data_date or date_str
    display_trade_date = trade_date or date_str
    report = f"""# 📈 Daily Action Plan [{date_str}]
Data Date: {display_data_date}
Trade Date: {display_trade_date}
Plan Date: {date_str}

> **중요 공지**: 본 리포트의 수량은 전일 종가 기준입니다. 장 개장 후 갭상승/하락이 클 경우 실제 가용 현금 내에서 수량을 미세 조절하십시오.
{stale_holdings_notice}

## 1. 오늘의 시장 국면 및 정책
- **현재 국면**: `{regime}` (VIX: `{vix:.2f}`)
- **현금 정책**: 목표 현금 `{cp_status['target_cash_ratio']*100:.0f}%` 유지
- **특이사항**: {m_state.get('triggers', {})}

## 2. 자산 현황
- **총 자산**: `${cp_status['total_equity']:,.2f}`
- **가용 현금 (Buying Power)**: **`${cp_status['available_buying_power']:,.2f}`** (2% 예비 버퍼 제외됨)

## 3. 실시간 조건부 매도 감시 (Trailing Stop)
> 장중 아래 가격(Stop Price)에 도달하면 전략적 판단과 관계없이 **즉시 전량 매도**하십시오.

| 종목 | 현재가 | 손절/익절가 (Stop) | 거리(%) | 지시 |
| :--- | :--- | :--- | :--- | :--- |
"""
    if not stop_alerts:
        report += "| - | - | - | - | 감시 종목 없음 |\n"
    else:
        for a in stop_alerts:
            report += f"| **{a['symbol']}** | ${a['current_price']:,.2f} | **${a['stop_price']:,.2f}** | {a['distance']:.2f}% | 이탈 시 즉시 매도 |\n"

    report += f"""
## 3-1. 보유 종목 SELL 진단 (Holding Sell Diagnostics)
> 이 섹션은 보유 종목의 매도 관련 진단 정보입니다.
> `Sell Signal=True`가 표시되더라도 이번 단계에서는 확정 매도 지시가 아닙니다.

| Symbol | Close | Exit Low | Sell Signal | ATR | ATR Source | Highest | Highest Source | Stop Price | Trail Trigger | Review | Warning | Notes |
| :--- | ---: | ---: | :--- | ---: | :--- | ---: | :--- | ---: | :--- | :--- | :--- | :--- |
"""
    if not holding_sell_diagnostics:
        report += "| - | - | - | - | - | - | - | - | - | - | - | - | 보유 종목 없음 |\n"
    else:
        for diag in holding_sell_diagnostics:
            close_display = "N/A" if diag["close"] is None else f"${float(diag['close']):,.2f}"
            exit_low_display = "N/A" if diag["exit_low"] is None else f"${float(diag['exit_low']):,.2f}"
            sell_signal_display = "N/A" if diag["sell_signal"] is None else ("True" if diag["sell_signal"] else "False")
            atr_display = "N/A" if diag["atr"] is None else f"{float(diag['atr']):,.4f}"
            highest_display = "N/A" if diag["highest_price"] is None else f"${float(diag['highest_price']):,.2f}"
            stop_display = "N/A" if diag["stop_price"] is None else f"${float(diag['stop_price']):,.2f}"
            trigger_display = "N/A" if diag["trailing_triggered"] is None else ("True" if diag["trailing_triggered"] else "False")
            report += (
                f"| {diag['symbol']} | {close_display} | {exit_low_display} | {sell_signal_display} | "
                f"{atr_display} | {diag['atr_source']} | {highest_display} | {diag['highest_source']} | "
                f"{stop_display} | {trigger_display} | {diag['review_status']} | {diag['warning_status']} | "
                f"{diag['notes'] or '-'} |\n"
            )

    report += f"""
## 4. 확정 매매 지시 (장 시작 즉시 실행)
| 타입 | 종목 | 수량 | 예상단가 | 매매 사유 |
| :--- | :--- | :--- | :--- | :--- |
"""
    if not action_items:
        report += "| - | - | - | - | 오늘 실행할 확정 매매 없음 |\n"
    else:
        for item in action_items:
            report += f"| {item['type']} | **{item['symbol']}** | {item['shares']}주 | ${item['price']:,.2f} | {item['reason']} |\n"

    report += """
## 4-0. 리밸런싱 검토 필요 (Not an Immediate Sell)
> 아래 종목은 목표 포트폴리오에서는 제외되었지만, 백테스트의 실제 매도 실행 경로와 직접 일치하지 않을 수 있습니다.
> 즉시 매도 지시가 아니라 수동 검토 대상입니다.

| Symbol | Shares | Ref Price | Reason | Note |
| :--- | ---: | ---: | :--- | :--- |
"""
    if not rebalance_review_items:
        report += "| - | - | - | - | 검토 대상 없음 |\n"
    else:
        for item in rebalance_review_items:
            report += (
                f"| **{item['symbol']}** | {item['shares']} | ${item['price']:,.2f} | "
                f"{item['reason']} | {item['note']} |\n"
            )

    report += """
## 4-0-1. 경고 및 주의 항목 (Warnings)
> 아래 항목은 데이터/운영/해석상의 주의사항입니다.
> 매매 지시가 아니며, journal 기록 대상도 아닙니다.

| Symbol | Severity | Reason | Note |
| :--- | :--- | :--- | :--- |
"""
    if not warning_items:
        report += "| - | - | - | 경고 없음 |\n"
    else:
        for item in warning_items:
            report += (
                f"| {item.get('symbol', '-')} | {item.get('severity', SEVERITY_LOW)} | "
                f"{item.get('reason', '-')} | {item.get('note', '')} |\n"
            )

    # MFU-FT2: 기록용 템플릿 섹션 (세분화 및 빈칸 강제)
    report += """
## 4-1. 후보 필터 진단 (Candidate Filter Diagnostics)
| Symbol | Latest Date | Stale Days | Score | RS | Entry | Result | Reason |
| :--- | :--- | :---: | ---: | ---: | :---: | :--- | :--- |
"""
    if removed_candidate_exclusions:
        report += "Freshness Guard exclusions (latest universe snapshot removed list):\n"
        for item in removed_candidate_exclusions:
            report += f"- {item['symbol']}: {item['reason']}\n"
        report += "\n"

    if stale_exclusions:
        report += (
            f"Stale candidate filter: excluded={len(stale_exclusions)}, "
            f"kept={len(candidate_diagnostics or [])}, threshold={stale_candidate_max_days}d\n\n"
        )
        report += "Excluded stale candidates:\n"
        for item in stale_exclusions:
            report += (
                f"- {item['symbol']}: latest={item['latest_price_date']}, "
                f"stale_days={item['stale_days']}\n"
            )
        report += "\n"

    if not candidate_diagnostics:
        report += "| - | - | - | - | - | - | no_candidates | 후보 종목이 없습니다. |\n"
    else:
        for diag in candidate_diagnostics:
            score_display = "N/A" if diag["score"] is None else f"{float(diag['score']):.2f}"
            rs_display = "N/A" if diag["rs_val"] is None else f"{float(diag['rs_val']):.6f}"
            entry_display = "Y" if diag["entry_signal"] else "N"
            result_display = "pass" if diag["pass"] else "fail"
            report += (
                f"| {diag['symbol']} | {diag['latest_price_date']} | {diag['stale_days']} | "
                f"{score_display} | {rs_display} | {entry_display} | {result_display} | {diag['fail_reason']} |\n"
            )

    report += f"""
## 5. 📝 프론트테스트 실행 기록 (Copy & Paste to Journal)
> 아래 표를 복사하여 기록 도구에 붙여넣으십시오. **Actual** 필드와 **Reason**은 직접 기입해야 합니다.

| Date | Regime | Symbol | Type | Rec_Shares | Rec_Price | Act_Shares | Act_Price | Reason | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
"""
    if not journal_rows:
        report += f"| {date_str} | {regime} | - | WAIT | 0 | 0.00 | [ ] | [ ] | MATCH | 특이사항 없음 |\n"
    else:
        for j in journal_rows:
            report += f"| {j['date']} | {j['regime']} | **{j['symbol']}** | {j['type']} | {j['rec_shares']} | {j['rec_price']} | [ ] | [ ] | [ ] | | \n"

    report += """
---
**입력 가이드**:
- `Act_Shares / Act_Price`: 실제 체결된 수량과 가격을 **숫자만** 입력하십시오.
- `Reason Codes`: `MATCH`(일치), `INSUFFICIENT_BP`(현금부족), `PRICE_GAP`(가격변동), `MANUAL_SKIP`(거부)
"""
    return report

if __name__ == "__main__":
    generate_daily_plan()
