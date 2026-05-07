import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import market_analyzer
from core.config_factory import get_regime_config, make_config


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

SIGNAL_COLUMN_CONTRACT = {
    "turtle": ["turtle_signal", "signal_turtle"],
    "rsi": ["rsi_signal", "signal_rsi"],
    "sma": ["sma_signal", "signal_sma"],
    "bbands": ["bbands_signal", "signal_bbands"],
    "macd": ["macd_signal", "signal_macd"],
    "bbs": ["bbs_signal", "signal_bbs"],
    "dema": ["dema_signal", "signal_dema"],
    "obv": ["signal_obv"],
    "mfi": ["signal_mfi"],
    "vol_spike": ["signal_vol_spike"],
}

INDICATOR_FUNCTION_CONTRACT = {
    "turtle": ["add_turtle_indicators"],
    "rsi": ["add_rsi_indicators"],
    "sma": ["add_sma_indicators"],
    "bbands": ["add_bollinger_band_indicators"],
    "macd": ["add_macd_indicators"],
    "bbs": ["add_bbs_indicators"],
    "dema": ["add_dema_indicators"],
    "obv": ["add_volume_indicators"],
    "mfi": ["add_volume_indicators"],
    "vol_spike": ["add_volume_indicators"],
}

FILES_TO_SCAN = {
    "indicator": Path("screener/indicator.py"),
    "strategy": Path("screener/strategy.py"),
    "backtest": Path("core/backtest_engine.py"),
    "fronttest": Path("core/daily_plan_generator.py"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate strategy-weight and signal-column sync.")
    parser.add_argument("--date", default="2026-05-04", help="Plan date used to resolve regime/data_date")
    return parser.parse_args()


def resolve_runtime_context(plan_date: str) -> tuple[str, str, dict]:
    m_state = market_analyzer.get_market_state(target_date=plan_date, write_log=False)
    data_date = m_state["date"]
    regime = m_state["regime"]
    base_config = make_config({}, data_date, data_date, fast_mode=False, runtime_overrides=None)
    merged_config = get_regime_config(regime, base_config)
    return data_date, regime, merged_config


def read_file_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def main() -> int:
    args = parse_args()
    data_date, regime, merged_config = resolve_runtime_context(args.date)

    failures: list[str] = []
    warnings: list[str] = []

    file_texts = {name: read_file_text(path) for name, path in FILES_TO_SCAN.items()}
    strategy_dynamic_signal_supported = 'col_name = f"signal_{name}"' in file_texts["strategy"]

    configured_weights: dict[str, float] = {}
    for key in ACTIVE_WEIGHT_KEYS:
        weight_key = f"{key}_weight"
        if weight_key not in merged_config:
            failures.append(f"missing weight mapping: {weight_key}")
            continue
        configured_weights[key] = merged_config[weight_key]

    for key in configured_weights:
        if key not in SIGNAL_COLUMN_CONTRACT:
            failures.append(f"missing signal contract: {key}")
            continue
        aliases = SIGNAL_COLUMN_CONTRACT[key]
        if not aliases:
            failures.append(f"empty signal contract: {key}")

    for key in configured_weights:
        aliases = SIGNAL_COLUMN_CONTRACT.get(key, [])
        indicator_funcs = INDICATOR_FUNCTION_CONTRACT.get(key, [])
        signal_found = any(alias in file_texts["strategy"] for alias in aliases) or (
            strategy_dynamic_signal_supported and f"'{key}'" in file_texts["strategy"]
        )
        indicator_found = any(func in file_texts["indicator"] for func in indicator_funcs)
        backtest_found = any(alias in file_texts["backtest"] for alias in aliases)
        fronttest_found = any(alias in file_texts["fronttest"] for alias in aliases)

        if not indicator_found:
            failures.append(f"missing indicator/strategy mapping: {key} -> {indicator_funcs}")
        if not signal_found:
            failures.append(f"missing strategy signal alias: {key} -> {aliases}")
        if not backtest_found:
            warnings.append(f"signal alias not found in backtest_engine.py for {key}: {aliases}")
        if not fronttest_found:
            warnings.append(f"signal alias not found in daily_plan_generator.py for {key}: {aliases}")

    if "apply_ensemble_strategy" not in file_texts["strategy"]:
        failures.append("missing strategy pipeline entrypoint: apply_ensemble_strategy")
    if "compute_candidate_score" not in file_texts["backtest"] or "compute_candidate_score" not in file_texts["fronttest"]:
        failures.append("compute_candidate_score reference missing in backtest/fronttest pipeline")

    active_summary = ", ".join(f"{key}={configured_weights[key]}" for key in ACTIVE_WEIGHT_KEYS if key in configured_weights)

    if failures:
        print("FAIL validate_strategy_sync")
        print(f"- data_date: {data_date}")
        print(f"- regime: {regime}")
        print(f"- active weights: {active_summary}")
        for item in failures:
            print(f"- {item}")
        for item in warnings:
            print(f"- warning: {item}")
        return 1

    print("PASS validate_strategy_sync")
    print(f"- data_date: {data_date}")
    print(f"- regime: {regime}")
    print(f"- active weights: {active_summary}")
    print("- signal contract: OK")
    print("- indicator/strategy mapping: OK")
    for item in warnings:
        print(f"- warning: {item}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
