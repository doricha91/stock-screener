from __future__ import annotations

from pathlib import Path
import sqlite3

import pandas as pd
from tqdm import tqdm

import config
import market_analyzer
from core.decision_core import compute_candidate_score, is_enterable_candidate
from core.paths import OUTPUTS, market_db_path
from screener import data_manager, indicator, strategy


STRATEGY_WEIGHTS = {
    "turtle": 2.0,
    "rsi": 1.0,
    "sma": 1.0,
    "bbands": 1.0,
    "macd": 1.0,
    "bbs": 1.5,
    "dema": 1.0,
}

DEFAULT_PARAMS = {
    "entry_period": 20,
    "exit_period": 10,
    "atr_period": 20,
    "rsi_period": 14,
    "rsi_oversold": 30,
    "rsi_overbought": 70,
    "sma_short_period": 50,
    "sma_long_period": 200,
    "bbands_period": 20,
    "bbands_std_dev": 2.0,
    "macd_fast_period": 12,
    "macd_slow_period": 26,
    "macd_signal_period": 9,
    "bbs_period": 20,
    "bbs_std_dev": 2.0,
    "bbs_squeeze_period": 120,
    "dema_short_period": 20,
    "dema_long_period": 50,
}

SCORE_THRESHOLD = getattr(config, "SCORE_THRESHOLD", 2.0)
DEFAULT_SCREEN_START_DATE = "2023-01-01"
DEFAULT_RESULTS_CSV = OUTPUTS / "screener_results.csv"


def _prepare_data_for_ensemble(df: pd.DataFrame) -> pd.DataFrame | None:
    if df is None or df.empty:
        return None

    try:
        df = indicator.add_turtle_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_rsi_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_sma_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_bollinger_band_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_macd_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_bbs_indicators(df, DEFAULT_PARAMS)
        df = indicator.add_dema_indicators(df, DEFAULT_PARAMS)
    except Exception:
        return None

    return df


def _resolve_market_state(market_state: dict | None = None) -> dict:
    if market_state is not None:
        return market_state
    return market_analyzer.get_market_state()


def build_screener_results(
    tickers: list[str] | None = None,
    market_state: dict | None = None,
    start_date: str = DEFAULT_SCREEN_START_DATE,
) -> pd.DataFrame:
    state = _resolve_market_state(market_state)
    regime = state["regime"]
    description = state["plan"].get("description", "")

    print("\n" + "=" * 50)
    print("STOCK SCREENER v5.3")
    print("=" * 50)
    print(f"\n[Step 1] Market: {regime} | {description}")

    if regime.upper() == "BEAR":
        print("\nBEAR regime. Continue screening with conservative interpretation.")

    if tickers is None:
        print("\n[Step 2] Loading tickers...")
        tickers = data_manager.get_ticker_list()
    else:
        print("\n[Step 2] Using provided tickers...")

    print(f"  Total tickers: {len(tickers)}")
    recommendations: list[dict] = []

    print("\n[Step 3] Screening...")
    for symbol in tqdm(tickers):
        try:
            df = data_manager.get_price_data(symbol, start_date=start_date)
            if df is None or len(df) < 200:
                continue

            df = _prepare_data_for_ensemble(df)
            if df is None:
                continue

            df = strategy.apply_ensemble_strategy(df, DEFAULT_PARAMS)

            latest_row = df.iloc[-1]
            score, reasons = compute_candidate_score(latest_row, STRATEGY_WEIGHTS)

            if is_enterable_candidate(score, SCORE_THRESHOLD, regime):
                recommendations.append(
                    {
                        "Symbol": symbol,
                        "Date": latest_row.name.strftime("%Y-%m-%d"),
                        "Price": latest_row["close"],
                        "Score": score,
                        "Strategies": ", ".join(reasons),
                        "Market": regime,
                    }
                )
        except Exception:
            continue

    print("\n[Step 4] Aggregating results...")
    if not recommendations:
        print("\nNo matching symbols found.")
        return pd.DataFrame()

    df_result = pd.DataFrame(recommendations)
    df_result = df_result.sort_values(by="Score", ascending=False).reset_index(drop=True)

    print(f"\nFound {len(df_result)} candidates.\n")
    print(df_result[["Symbol", "Price", "Score", "Strategies"]].to_string(index=False))
    return df_result


def save_results_to_db(df_result: pd.DataFrame, db_path: str | None = None) -> int:
    if df_result is None or df_result.empty:
        return 0

    target_db_path = db_path or market_db_path()
    conn = sqlite3.connect(target_db_path)
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS screener_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                symbol TEXT,
                price REAL,
                score REAL,
                strategies TEXT,
                market_regime TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date, symbol)
            )
            """
        )

        saved_count = 0
        for _, row in df_result.iterrows():
            cursor.execute(
                """
                INSERT OR REPLACE INTO screener_history
                (date, symbol, price, score, strategies, market_regime)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    row["Date"],
                    row["Symbol"],
                    float(row["Price"]),
                    float(row["Score"]),
                    row["Strategies"],
                    row["Market"],
                ),
            )
            saved_count += 1

        conn.commit()
        print(f"\nSaved {saved_count} screener rows to DB: {target_db_path}")
        return saved_count
    finally:
        conn.close()


def save_results_to_csv(df_result: pd.DataFrame, output_path: str | Path | None = None) -> Path | None:
    if df_result is None or df_result.empty:
        return None

    target_path = Path(output_path) if output_path is not None else DEFAULT_RESULTS_CSV
    target_path.parent.mkdir(parents=True, exist_ok=True)
    df_result.to_csv(target_path, index=False)
    print(f"Saved screener CSV: {target_path}")
    return target_path


def run_screener(
    tickers: list[str] | None = None,
    market_state: dict | None = None,
    start_date: str = DEFAULT_SCREEN_START_DATE,
    save: bool = True,
    db_path: str | None = None,
    csv_output_path: str | Path | None = None,
) -> pd.DataFrame:
    df_result = build_screener_results(
        tickers=tickers,
        market_state=market_state,
        start_date=start_date,
    )

    if save and not df_result.empty:
        save_results_to_db(df_result, db_path=db_path)
        save_results_to_csv(df_result, output_path=csv_output_path)

    return df_result
