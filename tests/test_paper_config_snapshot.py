import json
import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

import core.daily_plan_generator as daily_plan_generator
from core.paper_config_snapshot import save_paper_config_snapshot
from core.target_portfolio_state import CurrentPortfolioState, RebalanceDecision, TargetPortfolioState


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_config_snapshot_{uuid4().hex}"
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


def test_save_paper_config_snapshot_writes_expected_fields(tmp_path: Path):
    output_path = tmp_path / "config_snapshots" / "paper_config_snapshot_20260512.json"
    archive_dir = tmp_path / "archive" / "config_snapshots"

    snapshot_path = save_paper_config_snapshot(
        plan_date="2026-05-12",
        market_state={
            "date": "2026-05-12",
            "regime": "BULL",
            "trade_halted": False,
            "triggers": {"trend_bull": True},
            "plan": {"target_cash_ratio": 0.05},
        },
        final_config={
            "max_positions": 10,
            "score_threshold": 1.5,
            "entry_period": 12,
            "exit_period": 20,
            "rs_lookback": 30,
            "trailing_stop_multiplier": 3.25,
            "risk_per_trade": 0.05,
            "target_cash_ratio": 0.05,
            "SWITCHING_PREMIUM": 1.5,
            "ALLOW_PROFIT_SWITCH": False,
            "SWITCHING_MAX_COUNT": 2,
            "turtle_weight": 1.5,
            "rs_weight": 3.0,
            "rsi_weight": 0.5,
            "sma_weight": 1.0,
            "bbands_weight": 1.0,
            "macd_weight": 1.0,
            "bbs_weight": 1.0,
            "dema_weight": 1.2,
            "obv_weight": 0.5,
            "mfi_weight": 0.5,
            "vol_spike_weight": 0.5,
        },
        output_path=output_path,
        archive_dir=archive_dir,
        source="run_paper_daily_plan",
        market_state_write_log=False,
    )

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert snapshot_path == output_path
    assert payload["plan_date"] == "2026-05-12"
    assert payload["producer_source"] == "run_paper_daily_plan"
    assert "source" not in payload
    assert payload["market_state_write_log"] is False
    assert payload["market_state"]["regime"] == "BULL"
    assert payload["market_status_summary"]["target_cash_ratio"] == 0.05
    assert payload["market_status_summary"]["trailing_stop_multiplier"] == 3.25
    assert payload["market_status_summary"]["SWITCHING_PREMIUM"] == 1.5
    assert payload["final_config"]["target_cash_ratio"] == 0.05
    assert payload["final_config"]["trailing_stop_multiplier"] == 3.25
    assert payload["final_config"]["SWITCHING_PREMIUM"] == 1.5
    assert payload["final_config"]["strategy_weights"]["turtle"] == 1.5


def test_save_paper_config_snapshot_archives_existing_file_before_replace(tmp_path: Path):
    output_path = tmp_path / "config_snapshots" / "paper_config_snapshot_20260512.json"
    archive_dir = tmp_path / "archive" / "config_snapshots"

    first = save_paper_config_snapshot(
        plan_date="2026-05-12",
        market_state={"date": "2026-05-12", "regime": "BULL", "trade_halted": False, "triggers": {}, "plan": {}},
        final_config={"target_cash_ratio": 0.05},
        output_path=output_path,
        archive_dir=archive_dir,
        market_state_write_log=False,
    )
    first_payload = json.loads(first.read_text(encoding="utf-8"))

    second = save_paper_config_snapshot(
        plan_date="2026-05-12",
        market_state={"date": "2026-05-12", "regime": "BEAR", "trade_halted": True, "triggers": {}, "plan": {}},
        final_config={"target_cash_ratio": 0.7},
        output_path=output_path,
        archive_dir=archive_dir,
        market_state_write_log=False,
    )

    archive_files = list(archive_dir.glob("paper_config_snapshot_20260512_archived_*.json"))
    second_payload = json.loads(second.read_text(encoding="utf-8"))

    assert len(archive_files) == 1
    assert json.loads(archive_files[0].read_text(encoding="utf-8"))["market_state"]["regime"] == first_payload["market_state"]["regime"]
    assert second_payload["market_state"]["regime"] == "BEAR"


def test_generate_daily_plan_saves_regime_applied_config_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    output_path = tmp_path / "paper_daily_plan.md"
    snapshot_path = tmp_path / "config_snapshots" / "paper_config_snapshot_20260512.json"
    archive_dir = tmp_path / "archive" / "config_snapshots"

    monkeypatch.setattr(daily_plan_generator, "load_current_state", lambda: _empty_state())
    monkeypatch.setattr(
        daily_plan_generator.market_analyzer,
        "get_market_state",
        lambda target_date=None, write_log=True: {
            "date": "2026-05-12",
            "regime": "BULL",
            "vix_value": 19.0,
            "trade_halted": False,
            "triggers": {"trend_bull": True},
            "plan": {"target_cash_ratio": 0.05},
        },
    )
    monkeypatch.setattr(daily_plan_generator, "make_config", lambda *args, **kwargs: {"max_positions": 10})
    monkeypatch.setattr(
        daily_plan_generator,
        "get_regime_config",
        lambda regime, base_config: {
            **base_config,
            "score_threshold": 1.5,
            "entry_period": 12,
            "exit_period": 20,
            "rs_lookback": 30,
            "risk_per_trade": 0.05,
            "target_cash_ratio": 0.05,
            "trailing_stop_multiplier": 3.25,
            "SWITCHING_PREMIUM": 1.5,
            "ALLOW_PROFIT_SWITCH": False,
            "SWITCHING_MAX_COUNT": 2,
            "turtle_weight": 1.5,
            "rs_weight": 3.0,
            "rsi_weight": 0.5,
            "sma_weight": 1.0,
            "bbands_weight": 1.0,
            "macd_weight": 1.0,
            "bbs_weight": 1.0,
            "dema_weight": 1.2,
            "obv_weight": 0.5,
            "mfi_weight": 0.5,
            "vol_spike_weight": 0.5,
            "MARKET_BENCHMARK_SYMBOL": "SPY",
            "stale_candidate_max_days": 7,
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
            target_cash_ratio=0.05,
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
        lambda *args, **kwargs: "# snapshot-test\n",
    )

    daily_plan_generator.generate_daily_plan(
        date_str="2026-05-12",
        current_state=_empty_state(),
        output_path=output_path,
        market_state_write_log=False,
        config_snapshot_path=snapshot_path,
        config_snapshot_archive_dir=archive_dir,
        config_snapshot_source="run_paper_daily_plan",
    )

    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["market_state_write_log"] is False
    assert payload["market_state"]["regime"] == "BULL"
    assert payload["market_status_summary"]["target_cash_ratio"] == 0.05
    assert payload["market_status_summary"]["trailing_stop_multiplier"] == 3.25
    assert payload["market_status_summary"]["SWITCHING_PREMIUM"] == 1.5
    assert payload["final_config"]["target_cash_ratio"] == 0.05
    assert payload["final_config"]["trailing_stop_multiplier"] == 3.25
    assert payload["final_config"]["SWITCHING_PREMIUM"] == 1.5
    assert payload["universe"]["policy"] == "quarterly_as_of"
    assert payload["universe"]["snapshot_date"] == "2026-04-01"
