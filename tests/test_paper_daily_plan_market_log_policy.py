import sqlite3
from pathlib import Path
from uuid import uuid4
import shutil

import pandas as pd
import pytest

import core.daily_plan_generator as daily_plan_generator
import market_analyzer
import scripts.run_paper_daily_plan as run_paper_daily_plan
from core.target_portfolio_state import CurrentPortfolioState, RebalanceDecision, TargetPortfolioState


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_daily_plan_market_log_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _empty_state() -> CurrentPortfolioState:
    return CurrentPortfolioState(
        current_symbols=[],
        current_cash_ratio=1.0,
        current_hedge_ratio=0.0,
        absolute_cash=100000.0,
        shares={},
        avg_price={},
        highest_prices={},
        highest_price_meta={},
        hedge_symbols=[],
    )


def test_run_paper_daily_plan_disables_market_log_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    captured: dict = {}

    monkeypatch.setattr(
        run_paper_daily_plan,
        "load_official_paper_state_for_daily_plan",
        lambda date_str: _empty_state(),
    )

    def _fake_generate_daily_plan(**kwargs):
        captured.update(kwargs)
        return str(tmp_path / "report.md")

    monkeypatch.setattr(run_paper_daily_plan, "generate_daily_plan", _fake_generate_daily_plan)

    run_paper_daily_plan.run_paper_daily_plan("20260512")

    assert captured["date_str"] == "2026-05-12"
    assert captured["market_state_write_log"] is False


def test_generate_daily_plan_passes_write_log_false_and_uses_market_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    captured: dict = {}

    monkeypatch.setattr(daily_plan_generator, "load_current_state", lambda: _empty_state())

    def _fake_get_market_state(target_date=None, write_log=True):
        captured["target_date"] = target_date
        captured["write_log"] = write_log
        return {
            "date": "2026-05-12",
            "regime": "BULL",
            "vix_value": 19.5,
            "trade_halted": False,
            "triggers": {"trend_bull": True},
            "plan": {"target_cash_ratio": 0.2},
        }

    monkeypatch.setattr(daily_plan_generator.market_analyzer, "get_market_state", _fake_get_market_state)
    monkeypatch.setattr(daily_plan_generator, "make_config", lambda *args, **kwargs: {"max_positions": 10})
    monkeypatch.setattr(
        daily_plan_generator,
        "get_regime_config",
        lambda regime, base_config: {
            **base_config,
            "MARKET_BENCHMARK_SYMBOL": "SPY",
            "max_positions": 10,
            "stale_candidate_max_days": 7,
            "target_cash_ratio": 0.2,
        },
    )
    monkeypatch.setattr(daily_plan_generator, "load_market_index_series", lambda *args, **kwargs: pd.Series(dtype="float64"))
    monkeypatch.setattr(
        daily_plan_generator,
        "load_universe_snapshot_as_of_quarter",
        lambda plan_date: {
            "snapshot": {"removed": []},
            "metadata": {
                "policy": "quarterly_as_of",
                "snapshot_path": "outputs/universe/universe_snapshot_20260401.json",
                "snapshot_date": "2026-04-01",
                "snapshot_quarter": "2026Q2",
                "fallback_used": False,
                "warning": None,
            },
        },
    )
    monkeypatch.setattr(daily_plan_generator, "build_screener_results", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(
        daily_plan_generator,
        "build_target_portfolio_state",
        lambda *args, **kwargs: TargetPortfolioState(
            market_state="BULL",
            target_cash_ratio=0.2,
            target_hedge_ratio=0.0,
            target_long_slots=0,
            target_symbols=[],
        ),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "evaluate_rebalance_need",
        lambda *args, **kwargs: RebalanceDecision(
            rebalance_needed=False,
            rebalance_reason=[],
            symbol_diff_added=[],
            symbol_diff_removed=[],
            cash_ratio_diff=0.0,
            hedge_ratio_diff=0.0,
        ),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "get_cash_policy_status",
        lambda current_cash, total_equity, target_cash_ratio: {
            "total_equity": total_equity,
            "current_cash": current_cash,
            "current_cash_ratio": 1.0,
            "target_cash_ratio": target_cash_ratio,
            "required_cash_buffer": total_equity * target_cash_ratio,
            "available_buying_power": current_cash * 0.8,
            "is_violating_buffer": False,
        },
    )

    def _fake_format_markdown_report(*args, **kwargs):
        captured["m_state"] = args[1]
        return "# market-state-test\n"

    monkeypatch.setattr(daily_plan_generator, "format_markdown_report", _fake_format_markdown_report)

    report_path = daily_plan_generator.generate_daily_plan(
        date_str="2026-05-12",
        current_state=_empty_state(),
        output_path=tmp_path / "report.md",
        market_state_write_log=False,
    )

    assert report_path == str(tmp_path / "report.md")
    assert captured["target_date"] == "2026-05-12"
    assert captured["write_log"] is False
    assert captured["m_state"]["regime"] == "BULL"
    assert captured["m_state"]["trade_halted"] is False
    assert captured["m_state"]["plan"]["target_cash_ratio"] == 0.2
    assert captured["m_state"]["triggers"]["trend_bull"] is True


def test_get_market_state_write_log_false_does_not_increase_market_status_log_count(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    db_path = tmp_path / "market_data.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE market_status_log (
            date TEXT PRIMARY KEY,
            status TEXT,
            vix_value REAL,
            trade_halted INTEGER,
            cb_trigger INTEGER,
            cb_halt INTEGER,
            ma_cross_bearish INTEGER,
            breadth_low INTEGER,
            drawdown INTEGER,
            vix_breakout INTEGER,
            trend_bull INTEGER,
            trend_bear INTEGER,
            triggers TEXT,
            description TEXT,
            created_at TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE daily_indicators (
            symbol TEXT,
            date TEXT,
            sma_20 REAL,
            sma_50 REAL,
            sma_200 REAL,
            atr_20 REAL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE daily_price (
            symbol TEXT,
            date TEXT,
            close REAL
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE market_index (
            symbol TEXT,
            date TEXT,
            close REAL
        )
        """
    )

    dates = pd.date_range("2025-10-05", periods=220, freq="D")
    for i, ts in enumerate(dates):
        date_str = ts.strftime("%Y-%m-%d")
        close = 100.0 + i
        cur.execute(
            "INSERT INTO daily_price (symbol, date, close) VALUES (?, ?, ?)",
            ("AAA", date_str, close),
        )
        cur.execute(
            "INSERT INTO daily_indicators (symbol, date, sma_20, sma_50, sma_200, atr_20) VALUES (?, ?, ?, ?, ?, ?)",
            ("AAA", date_str, close - 1.0, close - 2.0, close - 3.0, 2.0),
        )
        for symbol, multiplier in (("SPY", 1.0), ("QQQ", 1.2), ("^VIX", 0.2)):
            cur.execute(
                "INSERT INTO market_index (symbol, date, close) VALUES (?, ?, ?)",
                (symbol, date_str, 50.0 + (i * multiplier)),
            )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        market_analyzer,
        "get_db_connection",
        lambda: sqlite3.connect(db_path),
    )

    before_conn = sqlite3.connect(db_path)
    before_cur = before_conn.cursor()
    before_cur.execute("SELECT COUNT(*) FROM market_status_log")
    before_count = before_cur.fetchone()[0]
    before_conn.close()

    state = market_analyzer.get_market_state(target_date="2026-05-12", write_log=False)

    after_conn = sqlite3.connect(db_path)
    after_cur = after_conn.cursor()
    after_cur.execute("SELECT COUNT(*) FROM market_status_log")
    after_count = after_cur.fetchone()[0]
    after_conn.close()

    assert state["date"] == "2026-05-12"
    assert before_count == 0
    assert after_count == before_count
