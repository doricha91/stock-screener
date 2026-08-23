import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pandas as pd
import pytest

import core.daily_plan_generator as daily_plan_generator
import scripts.run_paper_daily_plan as run_paper_daily_plan
from core.paper_account_paths import build_paper_account_paths
from core.paper_account_state import build_paper_state_from_trades
from core.paper_config_snapshot import save_paper_config_snapshot
from core.stage_a_asof_contract import StageAAsOfContext, StageAAsOfContractError
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


def _write_account_snapshot(
    account_paths,
    *,
    initial_cash: str,
    cash: str,
    snapshot_date: str = "2026-06-05",
) -> None:
    account_paths.account_snapshot_path.write_text(
        "snapshot_date,initial_cash,cash,currency\n"
        f"{snapshot_date},{initial_cash},{cash},USD\n",
        encoding="utf-8",
    )


def _capture_non_default_provider_seed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    initial_cash: str,
    cash: str,
) -> dict:
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )
    account_paths.execution_log_path.write_text(
        "trade_id,date,symbol,side,shares,price,gross_amount\n",
        encoding="utf-8",
    )
    _write_account_snapshot(
        account_paths,
        initial_cash=initial_cash,
        cash=cash,
    )
    provider_calls: dict = {}

    def _fake_provider(date_str: str, **kwargs):
        provider_calls.update({"date_str": date_str, **kwargs})
        return _empty_state(cash=kwargs["initial_cash"])

    monkeypatch.setattr(
        run_paper_daily_plan,
        "load_official_paper_state_for_daily_plan",
        _fake_provider,
    )
    monkeypatch.setattr(
        run_paper_daily_plan,
        "generate_daily_plan",
        lambda **kwargs: str(kwargs["output_path"]),
    )

    run_paper_daily_plan.run_paper_daily_plan(
        "2026-06-05",
        account_paths=account_paths,
    )
    return provider_calls


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


def test_run_paper_daily_plan_default_account_keeps_default_state_loader(monkeypatch: pytest.MonkeyPatch):
    paper_state = _empty_state(cash=100000.0)
    provider_calls: dict = {}

    def _fake_provider(date_str: str):
        provider_calls["date_str"] = date_str
        return paper_state

    monkeypatch.setattr(
        run_paper_daily_plan,
        "load_official_paper_state_for_daily_plan",
        _fake_provider,
    )
    monkeypatch.setattr(
        run_paper_daily_plan,
        "generate_daily_plan",
        lambda **kwargs: str(kwargs["output_path"]),
    )
    monkeypatch.setattr(
        run_paper_daily_plan,
        "_read_account_initial_snapshot",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("paper_default must not read an account snapshot seed")
        ),
    )

    run_paper_daily_plan.run_paper_daily_plan("20260509")

    assert provider_calls == {"date_str": "2026-05-09"}


def test_read_account_initial_snapshot_uses_initial_cash_not_post_trade_cash(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )
    _write_account_snapshot(
        account_paths,
        initial_cash="100000.00",
        cash="80160.55",
    )

    starting_cash, currency = run_paper_daily_plan._read_account_initial_snapshot(account_paths)

    assert starting_cash == 100000.0
    assert starting_cash != 80160.55
    assert currency == "USD"


def test_non_default_daily_plan_passes_initial_cash_to_full_ledger_provider(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    provider_calls = _capture_non_default_provider_seed(
        monkeypatch,
        tmp_path,
        initial_cash="100000.00",
        cash="80160.55",
    )

    assert provider_calls["initial_cash"] == 100000.0


def test_non_default_daily_plan_preserves_custom_initial_cash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    provider_calls = _capture_non_default_provider_seed(
        monkeypatch,
        tmp_path,
        initial_cash="250000.00",
        cash="210000.00",
    )

    assert provider_calls["initial_cash"] == 250000.0


def test_initial_cash_full_ledger_replay_matches_expected_snapshot_and_current_state(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )
    _write_account_snapshot(
        account_paths,
        initial_cash="1000.00",
        cash="400.00",
    )
    account_paths.execution_log_path.write_text(
        "trade_id,date,symbol,side,shares,price,gross_amount\n"
        "t1,2026-06-05,AAA,BUY,6,100.00,600.00\n"
        "t2,2026-06-08,BBB,BUY,5,80.00,400.00\n",
        encoding="utf-8",
    )
    with account_paths.execution_log_path.open("r", encoding="utf-8-sig", newline="") as handle:
        trade_rows = list(csv.DictReader(handle))

    starting_cash, currency = run_paper_daily_plan._read_account_initial_snapshot(account_paths)
    state = build_paper_state_from_trades(
        trade_rows,
        initial_cash=starting_cash,
        currency=currency,
    )

    assert state.cash == 0.0
    assert sorted(state.positions) == ["AAA", "BBB"]
    assert {symbol: position.shares for symbol, position in state.positions.items()} == {
        "AAA": 6,
        "BBB": 5,
    }
    assert len(state.applied_trade_ids) == 2
    with pytest.raises(ValueError, match="insufficient cash for BUY"):
        build_paper_state_from_trades(trade_rows, initial_cash=400.0, currency="USD")


def test_non_default_snapshot_missing_initial_cash_fails_closed(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )
    account_paths.account_snapshot_path.write_text(
        "snapshot_date,cash,currency\n"
        "2026-06-05,80160.55,USD\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as exc_info:
        run_paper_daily_plan._read_account_initial_snapshot(account_paths)

    message = str(exc_info.value)
    assert "paper_pilot_test" in message
    assert "paper_account_snapshot.csv" in message
    assert "initial_cash" in message
    assert "missing" in message


def test_non_default_snapshot_file_missing_fails_closed(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )

    with pytest.raises(ValueError) as exc_info:
        run_paper_daily_plan._read_account_initial_snapshot(account_paths)

    message = str(exc_info.value)
    assert "paper_pilot_test" in message
    assert "paper_account_snapshot.csv" in message
    assert "initial_cash" in message
    assert "missing" in message


@pytest.mark.parametrize("initial_cash", ["", "not-a-number", "0", "-1", "nan", "inf"])
def test_non_default_snapshot_invalid_initial_cash_fails_closed(
    tmp_path: Path,
    initial_cash: str,
):
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / f"paper_pilot_test_{initial_cash or 'blank'}",
        create=True,
    )
    _write_account_snapshot(
        account_paths,
        initial_cash=initial_cash,
        cash="80160.55",
    )

    with pytest.raises(ValueError) as exc_info:
        run_paper_daily_plan._read_account_initial_snapshot(account_paths)

    message = str(exc_info.value)
    assert "paper_pilot_test" in message
    assert "paper_account_snapshot.csv" in message
    assert "initial_cash" in message
    assert "missing" in message or "invalid" in message


def test_run_paper_daily_plan_non_default_uses_account_execution_log(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )
    account_paths.execution_log_path.write_text(
        "trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at\n",
        encoding="utf-8",
    )
    account_paths.account_snapshot_path.write_text(
        "snapshot_date,initial_cash,cash,total_equity_market_value,unrealized_pnl,position_count,symbols,currency\n"
        "2026-06-05,100000.00,100000.00,100000.00,0.00,0,,USD\n",
        encoding="utf-8",
    )
    account_paths.current_state_snapshot_path("20260605").write_text(
        '{"current_symbols":[],"current_cash_ratio":1.0,"current_hedge_ratio":0.0,'
        '"absolute_cash":100000.0,"shares":{},"avg_price":{},"highest_prices":{}}\n',
        encoding="utf-8",
    )

    provider_calls: dict = {}
    captured: dict = {}

    def _fake_provider(date_str: str, **kwargs):
        provider_calls.update({"date_str": date_str, **kwargs})
        return _empty_state(cash=kwargs["initial_cash"])

    def _fake_generate_daily_plan(**kwargs):
        captured.update(kwargs)
        assert kwargs["current_state"].current_symbols == []
        assert not {"AAPL", "BRK-B", "F", "GEN"} & set(kwargs["current_state"].current_symbols)
        return str(kwargs["output_path"])

    monkeypatch.setattr(
        run_paper_daily_plan,
        "load_official_paper_state_for_daily_plan",
        _fake_provider,
    )
    monkeypatch.setattr(run_paper_daily_plan, "generate_daily_plan", _fake_generate_daily_plan)

    report_path = run_paper_daily_plan.run_paper_daily_plan(
        "2026-06-05",
        account_paths=account_paths,
    )

    assert report_path == str(account_paths.daily_action_plan_path("2026-06-05"))
    assert provider_calls["date_str"] == "2026-06-05"
    assert provider_calls["log_path"] == account_paths.execution_log_path
    assert provider_calls["initial_cash"] == 100000.0
    assert provider_calls["currency"] == "USD"
    assert captured["account_id"] == "paper_pilot_test"
    assert captured["state_snapshot_path"] == account_paths.current_state_snapshot_path("20260605")


def test_run_paper_daily_plan_explicit_dates_use_trade_date_artifacts_and_data_date_signals(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )
    account_paths.execution_log_path.write_text(
        "trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at\n",
        encoding="utf-8",
    )
    account_paths.account_snapshot_path.write_text(
        "snapshot_date,initial_cash,cash,total_equity_market_value,unrealized_pnl,position_count,symbols,currency\n"
        "2026-06-05,100000.00,100000.00,100000.00,0.00,0,,USD\n",
        encoding="utf-8",
    )
    account_paths.current_state_snapshot_path("20260605").write_text(
        '{"current_symbols":[],"absolute_cash":100000.0}\n',
        encoding="utf-8",
    )
    account_paths.current_state_snapshot_path("20260608").write_text(
        '{"current_symbols":["FUTURE"],"absolute_cash":1.0}\n',
        encoding="utf-8",
    )

    provider_calls: dict = {}
    captured: dict = {}

    def _fake_provider(date_str: str, **kwargs):
        provider_calls.update({"date_str": date_str, **kwargs})
        return _empty_state(cash=100000.0)

    def _fake_generate_daily_plan(**kwargs):
        captured.update(kwargs)
        return str(kwargs["output_path"])

    monkeypatch.setattr(run_paper_daily_plan, "load_official_paper_state_for_daily_plan", _fake_provider)
    monkeypatch.setattr(run_paper_daily_plan, "generate_daily_plan", _fake_generate_daily_plan)

    report_path = run_paper_daily_plan.run_paper_daily_plan(
        data_date="2026-06-05",
        trade_date="2026-06-08",
        account_paths=account_paths,
    )

    assert report_path == str(account_paths.daily_action_plan_path("20260608"))
    assert provider_calls["date_str"] == "2026-06-05"
    assert captured["date_str"] == "2026-06-08"
    assert captured["data_date"] == "2026-06-05"
    assert captured["output_path"] == account_paths.daily_action_plan_path("20260608")
    assert captured["config_snapshot_path"] == account_paths.config_snapshot_path("20260608")
    assert captured["state_snapshot_path"] == account_paths.current_state_snapshot_path("20260605")


def test_historical_official_plan_blocks_when_config_snapshot_is_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )
    account_paths.execution_log_path.write_text(
        "trade_id,date,symbol,side,shares,price,gross_amount\n",
        encoding="utf-8",
    )
    _write_account_snapshot(account_paths, initial_cash="100000", cash="100000")
    monkeypatch.setattr(
        run_paper_daily_plan,
        "load_official_paper_state_for_daily_plan",
        lambda *args, **kwargs: _empty_state(),
    )

    with pytest.raises(StageAAsOfContractError) as exc_info:
        run_paper_daily_plan.run_paper_daily_plan(
            data_date="2026-06-05",
            trade_date="2026-06-08",
            account_paths=account_paths,
            enforce_asof_contract=True,
            observed_at="2026-06-09T08:00:00+09:00",
        )

    assert exc_info.value.reason == "historical_config_snapshot_missing"


def test_historical_official_plan_reuses_valid_config_and_data_date_account_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )
    account_paths.execution_log_path.write_text(
        "trade_id,date,symbol,side,shares,price,gross_amount\n",
        encoding="utf-8",
    )
    _write_account_snapshot(account_paths, initial_cash="100000", cash="100000")
    data_state = account_paths.current_state_snapshot_path("20260605")
    data_state.write_text('{"current_symbols":[],"absolute_cash":100000.0}\n', encoding="utf-8")
    account_paths.current_state_snapshot_path("20260608").write_text(
        '{"current_symbols":["FUTURE"],"absolute_cash":1.0}\n',
        encoding="utf-8",
    )
    capture_context = StageAAsOfContext.build(
        account_id=account_paths.account_id,
        data_date="2026-06-05",
        trade_date="2026-06-08",
        observed_at="2026-06-08T08:00:00+09:00",
    )
    save_paper_config_snapshot(
        plan_date="2026-06-08",
        data_date="2026-06-05",
        trade_date="2026-06-08",
        market_state={"date": "2026-06-05", "regime": "BULL"},
        final_config={"max_positions": 10},
        output_path=account_paths.config_snapshot_path("20260608"),
        archive_dir=account_paths.config_snapshot_archive_dir,
        asof_context=capture_context,
        immutable=True,
    )
    captured: dict = {}
    monkeypatch.setattr(
        run_paper_daily_plan,
        "load_official_paper_state_for_daily_plan",
        lambda *args, **kwargs: _empty_state(),
    )
    monkeypatch.setattr(
        run_paper_daily_plan,
        "generate_daily_plan",
        lambda **kwargs: captured.update(kwargs) or str(kwargs["output_path"]),
    )

    run_paper_daily_plan.run_paper_daily_plan(
        data_date="2026-06-05",
        trade_date="2026-06-08",
        account_paths=account_paths,
        enforce_asof_contract=True,
        observed_at="2026-06-09T08:00:00+09:00",
    )

    assert captured["pinned_config_snapshot"]["full_config"] == {"max_positions": 10}
    assert captured["state_snapshot_path"] == data_state
    assert captured["account_lineage"]["selected_max_date"] == "2026-06-05"


def test_run_paper_daily_plan_non_default_rejects_plan_before_account_inception(
    tmp_path: Path,
):
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )
    account_paths.execution_log_path.write_text(
        "trade_id,date,regime,symbol,side,shares,price,gross_amount,source,status,reason,notes,rec_shares,rec_price,created_at\n",
        encoding="utf-8",
    )
    account_paths.account_snapshot_path.write_text(
        "snapshot_date,cash,total_equity_market_value,unrealized_pnl,position_count,symbols,currency\n"
        "2026-06-05,100000.00,100000.00,0.00,0,,USD\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="before account inception date"):
        run_paper_daily_plan.run_paper_daily_plan("2026-06-04", account_paths=account_paths)


def test_run_paper_daily_plan_explicit_dates_reject_before_account_inception(
    tmp_path: Path,
):
    account_paths = build_paper_account_paths(
        "paper_pilot_test",
        account_root=tmp_path / "paper_pilot_test",
        create=True,
    )
    account_paths.account_snapshot_path.write_text(
        "snapshot_date,cash,total_equity_market_value,unrealized_pnl,position_count,symbols,currency\n"
        "2026-06-05,100000.00,100000.00,0.00,0,,USD\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="before account inception date"):
        run_paper_daily_plan.run_paper_daily_plan(
            data_date="2026-06-03",
            trade_date="2026-06-04",
            account_paths=account_paths,
        )


def test_run_paper_daily_plan_explicit_dates_reject_trade_not_after_data():
    with pytest.raises(ValueError, match="must be after data_date"):
        run_paper_daily_plan.run_paper_daily_plan(
            data_date="2026-06-05",
            trade_date="2026-06-05",
        )


def test_run_paper_daily_plan_explicit_dates_reject_weekend_trade_date():
    with pytest.raises(ValueError, match="must not be a weekend"):
        run_paper_daily_plan.run_paper_daily_plan(
            data_date="2026-06-05",
            trade_date="2026-06-06",
        )


def test_run_paper_daily_plan_requires_data_and_trade_dates_together():
    with pytest.raises(ValueError, match="must be provided together"):
        run_paper_daily_plan.run_paper_daily_plan(data_date="2026-06-05")


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
