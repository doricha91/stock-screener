import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

import core.daily_plan_generator as daily_plan_generator
import scripts.run_paper_daily_plan as run_paper_daily_plan
from core.paths import (
    front_daily_action_plan_path,
    paper_config_snapshot_archive_dir,
    paper_config_snapshot_path,
    paper_daily_action_plan_path,
)
from core.target_portfolio_state import (
    CurrentPortfolioState,
    RebalanceDecision,
    TargetPortfolioState,
)


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_daily_plan_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _empty_state(cash: float = 100000.0) -> CurrentPortfolioState:
    return CurrentPortfolioState(
        current_symbols=[],
        current_cash_ratio=1.0,
        current_hedge_ratio=0.0,
        absolute_cash=cash,
        shares={},
        avg_price={},
        highest_prices={},
        highest_price_meta={},
        hedge_symbols=[],
    )


def test_resolve_daily_plan_output_path_defaults_to_front_path():
    path = daily_plan_generator.resolve_daily_plan_output_path("2026-05-09")
    assert path == front_daily_action_plan_path("2026-05-09")


def test_generate_daily_plan_uses_injected_state_and_output_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    output_path = tmp_path / "paper_daily_plan.md"
    injected_state = _empty_state(cash=54321.0)

    monkeypatch.setattr(
        daily_plan_generator,
        "load_current_state",
        lambda: (_ for _ in ()).throw(AssertionError("load_current_state should not be called")),
    )
    monkeypatch.setattr(
        daily_plan_generator.market_analyzer,
        "get_market_state",
        lambda target_date=None, write_log=True: {
            "date": "2026-05-09",
            "regime": "BULL",
            "vix_value": 20.0,
            "triggers": {},
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
            "target_cash_ratio": 0.2,
        },
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "load_market_index_series",
        lambda *args, **kwargs: pd.Series(dtype="float64"),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "load_universe_snapshot_as_of_quarter",
        lambda plan_date: {
            "snapshot": {"removed": []},
            "metadata": {
                "policy": "quarterly_as_of",
                "snapshot_path": "outputs/universe/universe_snapshot_20260501.json",
                "snapshot_date": "2026-05-01",
                "snapshot_quarter": "2026Q2",
                "fallback_used": False,
                "warning": None,
            },
        },
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "build_screener_results",
        lambda market_state=None, end_date=None: pd.DataFrame(),
    )
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
    monkeypatch.setattr(
        daily_plan_generator,
        "format_markdown_report",
        lambda *args, **kwargs: "# injected paper plan\n",
    )

    report_path = daily_plan_generator.generate_daily_plan(
        date_str="2026-05-09",
        current_state=injected_state,
        output_path=output_path,
    )

    assert report_path == str(output_path)
    assert output_path.read_text(encoding="utf-8") == "# injected paper plan\n"


def test_run_paper_daily_plan_uses_paper_output_path(monkeypatch: pytest.MonkeyPatch):
    paper_state = _empty_state(cash=70245.95)
    captured: dict = {}
    provider_calls: dict = {}

    def _fake_provider(date_str: str):
        provider_calls["date_str"] = date_str
        return paper_state

    monkeypatch.setattr(
        run_paper_daily_plan,
        "load_official_paper_state_for_daily_plan",
        _fake_provider,
    )

    def _fake_generate_daily_plan(**kwargs):
        captured.update(kwargs)
        return str(kwargs["output_path"])

    monkeypatch.setattr(run_paper_daily_plan, "generate_daily_plan", _fake_generate_daily_plan)

    report_path = run_paper_daily_plan.run_paper_daily_plan("20260509")

    assert report_path == str(paper_daily_action_plan_path("20260509"))
    assert provider_calls["date_str"] == "2026-05-09"
    assert captured["current_state"] is paper_state
    assert captured["current_state"].absolute_cash == 70245.95
    assert captured["output_path"] == paper_daily_action_plan_path("20260509")
    assert captured["date_str"] == "2026-05-09"
    assert captured["market_state_write_log"] is False
    assert captured["config_snapshot_path"] == paper_config_snapshot_path("20260509")
    assert captured["config_snapshot_archive_dir"] == paper_config_snapshot_archive_dir()
    assert captured["config_snapshot_source"] == "run_paper_daily_plan"


def test_run_paper_daily_plan_accepts_dashed_date(monkeypatch: pytest.MonkeyPatch):
    paper_state = _empty_state(cash=11111.0)
    provider_calls: dict = {}
    captured: dict = {}

    def _fake_provider(date_str: str):
        provider_calls["date_str"] = date_str
        return paper_state

    monkeypatch.setattr(
        run_paper_daily_plan,
        "load_official_paper_state_for_daily_plan",
        _fake_provider,
    )

    def _fake_generate_daily_plan(**kwargs):
        captured.update(kwargs)
        return str(kwargs["output_path"])

    monkeypatch.setattr(run_paper_daily_plan, "generate_daily_plan", _fake_generate_daily_plan)

    report_path = run_paper_daily_plan.run_paper_daily_plan("2026-05-09")

    assert report_path == str(paper_daily_action_plan_path("2026-05-09"))
    assert provider_calls["date_str"] == "2026-05-09"
    assert captured["date_str"] == "2026-05-09"
    assert captured["market_state_write_log"] is False
    assert captured["config_snapshot_path"] == paper_config_snapshot_path("2026-05-09")
    assert captured["config_snapshot_archive_dir"] == paper_config_snapshot_archive_dir()
    assert captured["config_snapshot_source"] == "run_paper_daily_plan"


def test_run_paper_daily_plan_rejects_invalid_date():
    with pytest.raises(ValueError, match="Invalid date format"):
        run_paper_daily_plan.run_paper_daily_plan("2026/05/09")
