import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

import screener.screener as screener_module
from screener import data_manager


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"screener_asof_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _sample_price_df() -> pd.DataFrame:
    dates = pd.date_range("2025-11-01", periods=220, freq="D")
    df = pd.DataFrame(
        {
            "open": range(220),
            "high": range(1, 221),
            "low": range(220),
            "close": range(220),
            "adj_close": range(220),
            "volume": [1000] * 220,
        },
        index=dates,
    )
    return df


def _long_fake_df() -> pd.DataFrame:
    dates = pd.date_range("2025-10-06", periods=220, freq="D")
    df = pd.DataFrame(
        {
            "open": [99.0] * 220,
            "high": [101.0] * 220,
            "low": [98.0] * 220,
            "close": [100.0] * 220,
            "adj_close": [100.0] * 220,
            "volume": [1000] * 220,
        },
        index=dates,
    )
    df.iloc[-2, df.columns.get_loc("close")] = 100.0
    df.iloc[-1, df.columns.get_loc("close")] = 200.0
    return df


def _long_fake_df_with_target_tail() -> pd.DataFrame:
    df = _long_fake_df()
    df.index = list(df.index[:-2]) + [pd.Timestamp("2026-05-12"), pd.Timestamp("2026-05-13")]
    return df


def test_get_price_data_end_date_excludes_future_rows(tmp_path: Path):
    db_path = tmp_path / "market_data.db"
    source_df = _sample_price_df().reset_index().rename(columns={"index": "date"})
    source_df["date"] = pd.to_datetime(source_df["date"]).dt.strftime("%Y-%m-%d")
    source_df["symbol"] = "AAPL"

    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        source_df.to_sql("daily_price", conn, index=False, if_exists="replace")
        pd.DataFrame({"symbol": ["AAPL"]}).to_sql("tickers", conn, index=False, if_exists="replace")
    finally:
        conn.close()

    manager = data_manager.DataManager(str(db_path))
    result = manager.get_price_data("AAPL", start_date="2026-05-10", end_date="2026-05-12")

    assert not result.empty
    assert result.index.max() == pd.Timestamp("2026-05-12")
    assert pd.Timestamp("2026-05-13") not in result.index


def test_build_screener_results_uses_end_date_cutoff(monkeypatch: pytest.MonkeyPatch):
    observed: dict = {}

    def _fake_get_price_data(symbol, start_date=None, end_date=None):
        observed["end_date"] = end_date
        return _long_fake_df_with_target_tail()

    monkeypatch.setattr(screener_module.data_manager, "get_price_data", _fake_get_price_data)
    monkeypatch.setattr(screener_module, "_prepare_data_for_ensemble", lambda df: df)
    monkeypatch.setattr(screener_module.strategy, "apply_ensemble_strategy", lambda df, context: df)
    monkeypatch.setattr(screener_module, "compute_candidate_score", lambda row, weights: (3.0, ["mock"]))
    monkeypatch.setattr(screener_module, "is_enterable_candidate", lambda score, threshold, regime: True)

    result = screener_module.build_screener_results(
        tickers=["AAPL"],
        market_state={"regime": "BULL", "plan": {"description": "test"}},
        start_date="2026-01-01",
        end_date="2026-05-12",
    )

    assert observed["end_date"] == "2026-05-12"
    assert result.iloc[0]["Date"] == "2026-05-12"
    assert result.iloc[0]["Price"] == 100.0


def test_build_screener_results_keeps_existing_behavior_without_end_date(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        screener_module.data_manager,
        "get_price_data",
        lambda symbol, start_date=None, end_date=None: _long_fake_df_with_target_tail(),
    )
    monkeypatch.setattr(screener_module, "_prepare_data_for_ensemble", lambda df: df)
    monkeypatch.setattr(screener_module.strategy, "apply_ensemble_strategy", lambda df, context: df)
    monkeypatch.setattr(screener_module, "compute_candidate_score", lambda row, weights: (3.0, ["mock"]))
    monkeypatch.setattr(screener_module, "is_enterable_candidate", lambda score, threshold, regime: True)

    result = screener_module.build_screener_results(
        tickers=["AAPL"],
        market_state={"regime": "BULL", "plan": {"description": "test"}},
        start_date="2026-01-01",
    )

    assert result.iloc[0]["Date"] == "2026-05-13"
    assert result.iloc[0]["Price"] == 200.0
