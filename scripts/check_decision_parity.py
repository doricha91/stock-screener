import argparse
import sys
from typing import Any, Optional

import pandas as pd

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import config
import market_analyzer
from core.config_factory import get_regime_config, make_config
from core.daily_plan_generator import (
    calculate_candidate_rs_val,
    compute_holding_score_for_switching,
    load_market_index_series,
)
from core.decision_core import compute_candidate_score
from screener import data_manager, indicator, strategy


ACTIVE_WEIGHT_KEYS = [
    "turtle",
    "rsi",
    "sma",
    "bbands",
    "macd",
    "bbs",
    "dema",
    "obv",
    "mfi",
    "vol_spike",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare backtest-like and fronttest-like score/rs/signal outputs.")
    parser.add_argument("--date", required=True, help="Plan date used to resolve data_date")
    parser.add_argument("--symbol", required=True, help="Ticker symbol")
    parser.add_argument("--tolerance", type=float, default=0.001, help="Numeric tolerance for parity checks")
    return parser.parse_args()


def resolve_runtime_context(plan_date: str) -> tuple[str, str, dict]:
    m_state = market_analyzer.get_market_state(target_date=plan_date, write_log=False)
    data_date = m_state["date"]
    regime = m_state["regime"]
    base_config = make_config({}, data_date, data_date, fast_mode=False, runtime_overrides=None)
    merged_config = get_regime_config(regime, base_config)
    return data_date, regime, merged_config


def build_active_weights(merged_config: dict) -> dict[str, float]:
    return {
        "turtle": merged_config.get("turtle_weight", 1.0),
        "rsi": merged_config.get("rsi_weight", 1.0),
        "sma": merged_config.get("sma_weight", 1.0),
        "bbands": merged_config.get("bbands_weight", 1.0),
        "macd": merged_config.get("macd_weight", 1.0),
        "bbs": merged_config.get("bbs_weight", 1.0),
        "dema": merged_config.get("dema_weight", 1.0),
        "obv": merged_config.get("obv_weight", 0.5),
        "mfi": merged_config.get("mfi_weight", 0.5),
        "vol_spike": merged_config.get("vol_spike_weight", 0.5),
    }


def build_benchmark_series(merged_config: dict, data_date: str) -> tuple[pd.Series, int]:
    rs_lookback = int(merged_config.get("rs_lookback", 120))
    asof_date = pd.to_datetime(data_date)
    history_days = max(rs_lookback * 3, rs_lookback + 30)
    start_date = (asof_date - pd.Timedelta(days=history_days)).strftime("%Y-%m-%d")
    benchmark_symbol = merged_config.get("MARKET_BENCHMARK_SYMBOL", "SPY")
    benchmark_close = load_market_index_series(benchmark_symbol, end_date=data_date, start_date=start_date)
    return benchmark_close, rs_lookback


def compute_backtest_like_decision(
    symbol: str,
    data_date: str,
    merged_config: dict,
    active_weights: dict[str, float],
    benchmark_close: pd.Series,
    rs_lookback: int,
) -> dict[str, Any]:
    asof_date = pd.to_datetime(data_date)
    history_days = max(400, rs_lookback * 3)
    start_date = (asof_date - pd.Timedelta(days=history_days)).strftime("%Y-%m-%d")
    df = data_manager.get_price_data(symbol, start_date=start_date, end_date=data_date)
    if df is None or df.empty:
        return {"status": "SKIP", "reason": "symbol price data missing"}

    df = df.sort_index()
    df = df[df.index <= asof_date]
    if len(df) < 130:
        return {"status": "INCONCLUSIVE", "reason": "insufficient indicator history"}

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
        return {"status": "FAIL", "reason": f"pipeline_error: {type(exc).__name__}: {exc}"}

    if df.empty:
        return {"status": "INCONCLUSIVE", "reason": "empty dataframe after indicator pipeline"}

    latest_row = df.iloc[-1]
    score, reasons = compute_candidate_score(latest_row, active_weights)
    rs_val = calculate_candidate_rs_val(symbol, asof_date, benchmark_close, rs_lookback)
    if rs_val is None:
        return {"status": "INCONCLUSIVE", "reason": "benchmark/common-index insufficient for rs calculation"}

    reasons = list(reasons)
    rs_weight = merged_config.get("rs_weight", getattr(config, "RS_WEIGHT", 1.0))
    if rs_val > 0:
        score += rs_weight
        reasons.append("rs_bonus")

    score_threshold = merged_config.get("score_threshold", getattr(config, "SCORE_THRESHOLD", 1.5))
    buy_signal = bool((score >= score_threshold) and (rs_val > 0))
    return {
        "status": "PASS",
        "score": float(score),
        "rs_val": float(rs_val),
        "signal": buy_signal,
        "reasons": reasons,
        "signal_name": "buy_signal",
        "signal_source": "backtest_like_reconstructed",
        "note": "RS uses shared front-test helper for parity comparison.",
    }


def compute_fronttest_like_decision(
    symbol: str,
    data_date: str,
    merged_config: dict,
    active_weights: dict[str, float],
    benchmark_close: pd.Series,
    rs_lookback: int,
) -> dict[str, Any]:
    rs_weight = merged_config.get("rs_weight", getattr(config, "RS_WEIGHT", 1.0))
    score, rs_val, reasons = compute_holding_score_for_switching(
        symbol,
        data_date,
        active_weights,
        benchmark_close,
        rs_lookback,
        rs_weight,
        merged_config,
    )
    if score is None:
        exists = data_manager.get_price_data(symbol, start_date=data_date, end_date=data_date)
        if exists is None or exists.empty:
            return {"status": "SKIP", "reason": "symbol price data missing"}
        return {"status": "INCONCLUSIVE", "reason": "fronttest-like helper could not compute score"}

    score_threshold = merged_config.get("score_threshold", getattr(config, "SCORE_THRESHOLD", 1.5))
    entry_signal = bool((score >= score_threshold) and (rs_val is not None and rs_val > 0))
    reasons = list(reasons)
    if rs_val is not None and rs_val > 0 and "rs_bonus" not in reasons:
        reasons.append("rs_bonus")
    return {
        "status": "PASS",
        "score": float(score),
        "rs_val": None if rs_val is None else float(rs_val),
        "signal": entry_signal,
        "reasons": reasons,
        "signal_name": "entry_signal",
        "signal_source": "reconstructed_from_score_rs",
    }


def print_side(label: str, result: dict[str, Any]) -> None:
    print(f"{label}:")
    if result["status"] != "PASS":
        print(f"- status: {result['status']}")
        print(f"- reason: {result['reason']}")
        return
    print(f"- score: {result['score']:.4f}")
    if result["rs_val"] is None:
        print("- rs_val: N/A")
    else:
        print(f"- rs_val: {result['rs_val']:.4f}")
    print(f"- {result['signal_name']}: {bool(result['signal'])}")
    print(f"- reasons: {', '.join(result['reasons']) if result['reasons'] else 'none'}")
    if result.get("signal_source"):
        print(f"- {result['signal_name']}_source: {result['signal_source']}")
    if result.get("note"):
        print(f"- note: {result['note']}")


def compare_results(bt: dict[str, Any], ft: dict[str, Any], tolerance: float) -> tuple[str, Optional[dict[str, Any]]]:
    if bt["status"] == "SKIP" or ft["status"] == "SKIP":
        return "SKIP", None
    if bt["status"] != "PASS" and ft["status"] != "PASS":
        return "INCONCLUSIVE", None
    if bt["status"] != "PASS" or ft["status"] != "PASS":
        return "FAIL", None

    score_diff = abs(bt["score"] - ft["score"])
    rs_diff = abs(bt["rs_val"] - ft["rs_val"])
    signal_match = bool(bt["signal"]) == bool(ft["signal"])

    diff = {
        "score_diff": score_diff,
        "rs_diff": rs_diff,
        "signal_match": signal_match,
    }
    if score_diff < tolerance and rs_diff < tolerance and signal_match:
        return "PASS", diff
    return "FAIL", diff


def main() -> int:
    args = parse_args()
    symbol = args.symbol.strip().upper()
    data_date, regime, merged_config = resolve_runtime_context(args.date)
    active_weights = build_active_weights(merged_config)
    benchmark_close, rs_lookback = build_benchmark_series(merged_config, data_date)

    bt = compute_backtest_like_decision(
        symbol, data_date, merged_config, active_weights, benchmark_close, rs_lookback
    )
    ft = compute_fronttest_like_decision(
        symbol, data_date, merged_config, active_weights, benchmark_close, rs_lookback
    )
    result, diff = compare_results(bt, ft, args.tolerance)

    print("Decision Parity Check")
    print(f"- plan_date: {args.date}")
    print(f"- data_date: {data_date}")
    print(f"- regime: {regime}")
    print(f"- symbol: {symbol}")
    print(f"- tolerance: {args.tolerance}")
    print()
    print_side("Backtest-like", bt)
    print()
    print_side("Fronttest-like", ft)
    print()

    if diff is not None:
        print("Diff:")
        print(f"- score_diff: {diff['score_diff']:.4f}")
        print(f"- rs_diff: {diff['rs_diff']:.4f}")
        print(f"- signal_match: {diff['signal_match']}")
        print()

    print(f"RESULT: {result}")
    return 1 if result == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
