import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

import core.daily_plan_generator as daily_plan_generator
import scripts.run_paper_daily_plan as run_paper_daily_plan
from core.target_portfolio_state import CurrentPortfolioState, RebalanceDecision, TargetPortfolioState


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_daily_plan_cutoff_{uuid4().hex}"
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


def test_run_paper_daily_plan_passes_normalized_date_to_screener(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    captured: dict = {}

    monkeypatch.setattr(run_paper_daily_plan, "load_official_paper_state_for_daily_plan", lambda date_str: _empty_state())

    def _fake_generate_daily_plan(**kwargs):
        captured.update(kwargs)
        return str(tmp_path / "report.md")

    monkeypatch.setattr(run_paper_daily_plan, "generate_daily_plan", _fake_generate_daily_plan)

    run_paper_daily_plan.run_paper_daily_plan("20260512")

    assert captured["date_str"] == "2026-05-12"


def test_generate_daily_plan_uses_plan_date_for_screener_cutoff_and_stale_days(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    captured: dict = {}

    monkeypatch.setattr(daily_plan_generator, "load_current_state", lambda: _empty_state())
    monkeypatch.setattr(
        daily_plan_generator.market_analyzer,
        "get_market_state",
        lambda target_date=None, write_log=True: {
            "date": "2026-05-11",
            "regime": "BULL",
            "vix_value": 20.0,
            "triggers": {},
            "plan": {},
        },
    )
    monkeypatch.setattr(daily_plan_generator, "make_config", lambda *args, **kwargs: {"max_positions": 10})
    monkeypatch.setattr(
        daily_plan_generator,
        "get_regime_config",
        lambda regime, base_config: {
            **base_config,
            "MARKET_BENCHMARK_SYMBOL": "SPY",
            "max_positions": 10,
            "stale_candidate_max_days": 7,
            "score_threshold": 1.5,
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

    def _fake_build_screener_results(**kwargs):
        captured["screener_end_date"] = kwargs.get("end_date")
        return pd.DataFrame(
            [
                {
                    "Symbol": "AAPL",
                    "Date": "2026-05-12",
                    "Price": 100.0,
                    "Score": 2.0,
                    "rs_val": 1.0,
                    "rs_calc_success": True,
                }
            ]
        )

    monkeypatch.setattr(daily_plan_generator, "build_screener_results", _fake_build_screener_results)
    monkeypatch.setattr(
        daily_plan_generator,
        "build_target_portfolio_state",
        lambda *args, **kwargs: TargetPortfolioState(
            market_state="BULL",
            target_cash_ratio=0.2,
            target_hedge_ratio=0.0,
            target_long_slots=1,
            target_symbols=["AAPL"],
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
        captured["candidate_diagnostics"] = kwargs["candidate_diagnostics"]
        return "# test\n"

    monkeypatch.setattr(daily_plan_generator, "format_markdown_report", _fake_format_markdown_report)

    daily_plan_generator.generate_daily_plan(
        date_str="2026-05-13",
        current_state=_empty_state(),
        output_path=tmp_path / "paper_daily_plan.md",
    )

    assert captured["screener_end_date"] == "2026-05-13"
    assert captured["candidate_diagnostics"][0]["latest_price_date"] == "2026-05-12"
    assert captured["candidate_diagnostics"][0]["stale_days"] == 1
