from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import pytest

from core import daily_plan_generator as daily_plan
from core import paper_account_binding as binding
from core import paper_account_profile as profiles
from core import paper_runtime_binding as runtime
from core.paper_config_snapshot import build_paper_config_snapshot_payload
from core.target_portfolio_state import CurrentPortfolioState, RebalanceDecision, TargetPortfolioState
from screener import screener
from scripts import run_paper_daily_plan, runbook_command_registry, runbook_stage_runner, runbook_state
from tests.paper_account_test_support import create_initialized_account_paths


RUNTIME_SIGNAL_NAMES = (
    "turtle", "rsi", "sma", "bbands", "macd", "bbs", "dema", "obv", "mfi", "vol_spike",
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def binding_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    account_path = tmp_path / "profiles.json"
    registry_path = tmp_path / "registry.json"
    account_payload = {
        "schema_version": profiles.VERSIONED_ACCOUNT_PROFILE_SCHEMA,
        "default_account_id": "synthetic_a",
        "accounts": [
            {
                "account_id": "synthetic_a", "display_name": "A", "currency": "USD",
                "initial_cash": 100000, "account_type": "paper", "is_default": True,
                "strategy_profile": "strategy_a", "strategy_version": "v1",
                "universe_profile": "universe_a", "universe_version": "v1",
            },
            {
                "account_id": "synthetic_b", "display_name": "B", "currency": "USD",
                "initial_cash": 100000, "account_type": "paper", "is_default": False,
                "strategy_profile": "strategy_b", "strategy_version": "v1",
                "universe_profile": "universe_b", "universe_version": "v1",
            },
        ],
    }
    registry_payload = {
        "schema_version": binding.REGISTRY_SCHEMA,
        "strategy": [
            {"id": "strategy_a", "version": "v1", "content": {"parameters": {
                "entry_period": 12, "score_threshold": 1.25,
            }}},
            {"id": "strategy_b", "version": "v1", "content": {"parameters": {
                "entry_period": 33, "score_threshold": 4.5,
            }}},
        ],
        "universe": [
            {"id": "universe_a", "version": "v1", "content": {
                "kind": "symbols", "symbols": ["BBB", "AAA"],
            }},
            {"id": "universe_b", "version": "v1", "content": {
                "kind": "shared_snapshot",
            }},
        ],
    }
    _write_json(account_path, account_payload)
    _write_json(registry_path, registry_payload)
    monkeypatch.setattr(profiles, "_default_settings_path", lambda: account_path)
    monkeypatch.setattr(binding, "paper_binding_registry_path", lambda: registry_path)
    return {
        "accounts": account_payload,
        "account_path": account_path,
        "registry": registry_payload,
        "registry_path": registry_path,
    }


def _empty_state(*, holdings: list[str] | None = None) -> CurrentPortfolioState:
    symbols = holdings or []
    return CurrentPortfolioState(
        current_symbols=symbols,
        current_cash_ratio=1.0,
        current_hedge_ratio=0.0,
        absolute_cash=100000.0,
        shares={symbol: 1 for symbol in symbols},
        avg_price={symbol: 10.0 for symbol in symbols},
        highest_prices={symbol: 10.0 for symbol in symbols},
        highest_price_meta={},
        hedge_symbols=[],
    )


def test_strategy_regime_and_shared_policy_derive_only_from_binding(binding_environment):
    frozen = runtime.resolve_runtime_binding("synthetic_a")
    config, evidence = runtime.build_runtime_config(
        frozen, active_regime="BULL", start_date="2026-10-01", end_date="2026-10-01"
    )

    assert config["entry_period"] == 12
    assert config["score_threshold"] == 1.25
    assert evidence["effective_strategy_base"] == frozen["semantics"]["effective_strategy_base"]
    assert evidence["applied_regime_overlay"] == frozen["semantics"]["regime_policy"]["REGIME_RULES"]["BULL"]
    assert evidence["shared_policy"] == frozen["semantics"]["shared_policy"]
    for key, value in evidence["shared_policy"].items():
        assert config[key] == value


@pytest.mark.parametrize("regime", ["BULL", "BEAR"])
def test_active_regime_overlay_is_account_local(binding_environment, regime):
    frozen = runtime.resolve_runtime_binding("synthetic_a")
    _, evidence = runtime.build_runtime_config(
        frozen, active_regime=regime, start_date="2026-10-01", end_date="2026-10-01"
    )
    assert evidence["applied_regime"] == regime
    assert evidence["applied_regime_overlay"] == frozen["semantics"]["regime_policy"]["REGIME_RULES"][regime]


def test_account_a_b_are_order_independent_without_global_contamination(binding_environment):
    frozen_a = runtime.resolve_runtime_binding("synthetic_a")
    frozen_b = runtime.resolve_runtime_binding("synthetic_b")

    a_first = runtime.build_runtime_config(frozen_a, active_regime="BULL", start_date="x", end_date="x")
    b_second = runtime.build_runtime_config(frozen_b, active_regime="BEAR", start_date="x", end_date="x")
    b_first = runtime.build_runtime_config(frozen_b, active_regime="BEAR", start_date="x", end_date="x")
    a_second = runtime.build_runtime_config(frozen_a, active_regime="BULL", start_date="x", end_date="x")

    assert a_first == a_second
    assert b_first == b_second
    assert a_first[0]["entry_period"] == 12
    assert b_first[0]["entry_period"] == 33
    assert a_first[1]["entry_universe_definition"]["symbols"] == ["AAA", "BBB"]
    assert b_first[1]["entry_universe_definition"] == {"kind": "shared_snapshot"}


def test_frozen_current_drift_fails_before_runtime(binding_environment):
    frozen = runtime.resolve_runtime_binding("synthetic_a")
    binding_environment["registry"]["strategy"][0]["content"]["parameters"]["entry_period"] = 13
    _write_json(binding_environment["registry_path"], binding_environment["registry"])
    with pytest.raises(binding.BindingError, match="drift"):
        runtime.resolve_runtime_binding("synthetic_a", frozen_binding=frozen)


def test_runtime_consumption_tamper_fails_closed(binding_environment):
    frozen = runtime.resolve_runtime_binding("synthetic_a")
    config, evidence = runtime.build_runtime_config(
        frozen, active_regime="BULL", start_date="x", end_date="x"
    )
    config["entry_period"] = 999
    with pytest.raises(binding.BindingError, match="runtime strategy mismatch"):
        runtime.validate_runtime_consumption(config, evidence)


def test_pinned_regime_or_shared_policy_drift_fails_closed(binding_environment):
    frozen = runtime.resolve_runtime_binding("synthetic_a")
    config, evidence = runtime.build_runtime_config(
        frozen, active_regime="BULL", start_date="x", end_date="x"
    )
    for key in ("REGIME_ADX_THRESHOLD", "max_long_positions"):
        changed = copy.deepcopy(config)
        changed[key] = changed[key] + 1
        with pytest.raises(binding.BindingError, match="runtime (regime|shared) policy mismatch"):
            runtime.validate_runtime_consumption(changed, evidence)


def test_pinned_runtime_evidence_drift_fails_closed_without_migrating_legacy(binding_environment):
    frozen = runtime.resolve_runtime_binding("synthetic_a")
    _, evidence = runtime.build_runtime_config(
        frozen, active_regime="BULL", start_date="x", end_date="x"
    )
    runtime.validate_pinned_runtime_evidence(None, evidence, include_materialization=False)
    changed = copy.deepcopy(evidence)
    changed["effective_strategy_base"]["entry_period"] = 999
    with pytest.raises(binding.BindingError, match="pinned runtime binding mismatch"):
        runtime.validate_pinned_runtime_evidence(changed, evidence, include_materialization=False)


def test_explicit_universe_materialization_records_missing_data(monkeypatch):
    monkeypatch.setattr(
        daily_plan.data_manager,
        "get_price_data",
        lambda symbol, **kwargs: pd.DataFrame(index=range(210 if symbol != "BBB" else 10)),
    )
    materialized, excluded = daily_plan.materialize_explicit_entry_universe(
        ["BBB", "AAA", "CCC"], end_date="2026-10-01"
    )
    assert materialized == ["AAA", "CCC"]
    assert excluded == [{"symbol": "BBB", "reason": "missing_market_data"}]


@pytest.mark.parametrize(
    "frame",
    [None, pd.DataFrame(), pd.DataFrame(index=range(199))],
    ids=["none", "empty", "below-minimum"],
)
def test_explicit_universe_normal_data_insufficiency_is_missing_market_data(monkeypatch, frame):
    monkeypatch.setattr(daily_plan.data_manager, "get_price_data", lambda *args, **kwargs: frame)

    materialized, excluded = daily_plan.materialize_explicit_entry_universe(
        ["AAA"], end_date="2026-10-01"
    )

    assert materialized == []
    assert excluded == [{"symbol": "AAA", "reason": "missing_market_data"}]


def test_explicit_universe_unexpected_market_data_exception_propagates(monkeypatch):
    failure = RuntimeError("market store unavailable")

    def fail(*args, **kwargs):
        raise failure

    monkeypatch.setattr(daily_plan.data_manager, "get_price_data", fail)

    with pytest.raises(RuntimeError, match="market store unavailable") as exc_info:
        daily_plan.materialize_explicit_entry_universe(["AAA"], end_date="2026-10-01")

    assert exc_info.value is failure


def test_existing_holdings_are_preserved_outside_entry_universe(binding_environment):
    frozen = runtime.resolve_runtime_binding("synthetic_a")
    _, evidence = runtime.build_runtime_config(
        frozen, active_regime="BULL", start_date="x", end_date="x"
    )
    recorded = runtime.record_runtime_universe(
        evidence,
        requested=["AAA", "BBB"],
        materialized=["AAA"],
        excluded=[{"symbol": "BBB", "reason": "missing_market_data"}],
        existing_holdings=["ZZZ"],
        managed_symbols=["AAA", "ZZZ", "SPY"],
    )
    assert recorded["materialized_entry_universe"] == ["AAA"]
    assert recorded["existing_holdings_preserved"] == ["ZZZ"]
    assert recorded["managed_symbols"] == ["AAA", "SPY", "ZZZ"]


def test_screener_consumes_per_call_runtime_config(monkeypatch):
    index = pd.date_range("2026-01-01", periods=210)
    frame = pd.DataFrame({"close": range(210)}, index=index)
    captured: dict = {}
    monkeypatch.setattr(screener.data_manager, "get_price_data", lambda *args, **kwargs: frame.copy())
    def prepare(df, params):
        captured["params"] = params
        return df

    def apply_strategy(df, params):
        captured["strategy_params"] = params
        return df

    def score(row, weights):
        captured["weights"] = weights
        return 9.0, ["x"]

    def enterable(score_value, threshold, regime):
        captured["threshold"] = threshold
        return True

    monkeypatch.setattr(screener, "_prepare_data_for_ensemble", prepare)
    monkeypatch.setattr(screener.strategy, "apply_ensemble_strategy", apply_strategy)
    monkeypatch.setattr(screener, "compute_candidate_score", score)
    monkeypatch.setattr(screener, "is_enterable_candidate", enterable)

    config = {
        "entry_period": 7,
        "turtle_weight": 8.0,
        "obv_weight": 2.0,
        "mfi_weight": 3.0,
        "vol_spike_weight": 4.0,
        "score_threshold": 6.0,
    }
    result = screener.build_screener_results(
        tickers=["AAA"], market_state={"regime": "BULL", "plan": {}}, runtime_config=config
    )
    assert not result.empty
    assert captured["params"]["entry_period"] == 7
    assert captured["strategy_params"]["entry_period"] == 7
    assert captured["weights"]["turtle"] == 8.0
    assert captured["weights"]["obv"] == 2.0
    assert captured["weights"]["mfi"] == 3.0
    assert captured["weights"]["vol_spike"] == 4.0
    assert captured["threshold"] == 6.0


def _patch_screener_signals(monkeypatch, active_signals: set[str]) -> None:
    index = pd.date_range("2026-01-01", periods=210)
    frame = pd.DataFrame({"close": range(210)}, index=index)
    monkeypatch.setattr(screener.data_manager, "get_price_data", lambda *args, **kwargs: frame.copy())
    monkeypatch.setattr(screener, "_prepare_data_for_ensemble", lambda df, params=None: df)

    def apply_strategy(df, params):
        result = df.copy()
        for name in RUNTIME_SIGNAL_NAMES:
            result[f"signal_{name}"] = int(name in active_signals)
        return result

    monkeypatch.setattr(screener.strategy, "apply_ensemble_strategy", apply_strategy)


def test_bound_screener_actual_score_uses_all_runtime_weights_without_cross_call_contamination(
    binding_environment, monkeypatch,
):
    _patch_screener_signals(monkeypatch, set(RUNTIME_SIGNAL_NAMES))
    frozen_a = runtime.resolve_runtime_binding("synthetic_a")
    frozen_b = runtime.resolve_runtime_binding("synthetic_b")
    config_a, _ = runtime.build_runtime_config(
        frozen_a, active_regime="BULL", start_date="x", end_date="x"
    )
    config_b, _ = runtime.build_runtime_config(
        frozen_b, active_regime="BEAR", start_date="x", end_date="x"
    )

    a_first = screener.build_screener_results(
        tickers=["AAA"], market_state={"regime": "BULL", "plan": {}},
        runtime_config=config_a, apply_entry_filter=False,
    )
    b_result = screener.build_screener_results(
        tickers=["AAA"], market_state={"regime": "BEAR", "plan": {}},
        runtime_config=config_b, apply_entry_filter=False,
    )
    a_second = screener.build_screener_results(
        tickers=["AAA"], market_state={"regime": "BULL", "plan": {}},
        runtime_config=config_a, apply_entry_filter=False,
    )

    expected_a = sum(config_a[f"{name}_weight"] for name in RUNTIME_SIGNAL_NAMES)
    expected_b = sum(config_b[f"{name}_weight"] for name in RUNTIME_SIGNAL_NAMES)
    assert a_first.iloc[0]["Score"] == expected_a
    assert b_result.iloc[0]["Score"] == expected_b
    assert expected_a != expected_b
    assert a_second.iloc[0]["Score"] == a_first.iloc[0]["Score"]
    for name in RUNTIME_SIGNAL_NAMES:
        assert a_first.iloc[0][f"signal_{name}"] == 1


def test_bound_screener_can_defer_premature_threshold_for_final_daily_plan_scoring(monkeypatch):
    _patch_screener_signals(monkeypatch, {"obv"})
    config = {
        **{f"{name}_weight": 0.0 for name in RUNTIME_SIGNAL_NAMES},
        "obv_weight": 1.0,
        "score_threshold": 2.0,
    }

    filtered = screener.build_screener_results(
        tickers=["AAA"], market_state={"regime": "BULL", "plan": {}}, runtime_config=config,
    )
    deferred = screener.build_screener_results(
        tickers=["AAA"], market_state={"regime": "BULL", "plan": {}},
        runtime_config=config, apply_entry_filter=False,
    )

    assert filtered.empty
    assert deferred.iloc[0]["Score"] == 1.0
    assert deferred.iloc[0]["signal_obv"] == 1


def test_unbound_screener_preserves_legacy_seven_weight_scoring(monkeypatch):
    _patch_screener_signals(monkeypatch, set(RUNTIME_SIGNAL_NAMES))

    result = screener.build_screener_results(
        tickers=["AAA"], market_state={"regime": "BULL", "plan": {}},
    )

    assert result.iloc[0]["Score"] == sum(screener.STRATEGY_WEIGHTS.values())
    assert "signal_obv" not in result.columns


def test_bound_indicator_preparation_adds_volume_indicators_without_changing_legacy(monkeypatch):
    calls: list[str] = []
    for name in (
        "add_turtle_indicators", "add_rsi_indicators", "add_sma_indicators",
        "add_bollinger_band_indicators", "add_macd_indicators", "add_bbs_indicators",
        "add_dema_indicators",
    ):
        monkeypatch.setattr(screener.indicator, name, lambda df, params: df)

    def add_volume(df, params):
        calls.append("volume")
        return df

    monkeypatch.setattr(screener.indicator, "add_volume_indicators", add_volume)
    frame = pd.DataFrame({"close": [1.0]})

    assert screener._prepare_data_for_ensemble(frame, {"obv_weight": 0.5}) is not None
    assert calls == ["volume"]
    assert screener._prepare_data_for_ensemble(frame) is not None
    assert calls == ["volume"]


def _patch_daily_plan_dependencies(monkeypatch: pytest.MonkeyPatch, captured: dict) -> None:
    monkeypatch.setattr(daily_plan.market_analyzer, "get_market_state", lambda **kwargs: {
        "date": "2026-10-01", "regime": "BULL", "trade_halted": False,
        "vix_value": 10.0, "triggers": {}, "plan": {},
    })
    monkeypatch.setattr(daily_plan, "load_market_index_series", lambda *args, **kwargs: pd.Series(dtype="float64"))
    monkeypatch.setattr(daily_plan.data_manager, "get_price_data", lambda symbol, **kwargs: pd.DataFrame(index=range(210 if symbol == "AAA" else 0)))
    monkeypatch.setattr(daily_plan, "build_screener_results", lambda **kwargs: captured.update(screener=kwargs) or pd.DataFrame())
    monkeypatch.setattr(daily_plan, "build_target_portfolio_state", lambda *args, **kwargs: TargetPortfolioState(
        market_state="BULL", target_cash_ratio=0.05, target_hedge_ratio=0.0,
        target_long_slots=0, target_symbols=[],
    ))
    monkeypatch.setattr(daily_plan, "evaluate_rebalance_need", lambda *args, **kwargs: RebalanceDecision(
        rebalance_needed=False, rebalance_reason=[], symbol_diff_added=[], symbol_diff_removed=[],
        cash_ratio_diff=0.0, hedge_ratio_diff=0.0,
    ))
    monkeypatch.setattr(daily_plan, "get_cash_policy_status", lambda *args, **kwargs: {
        "total_equity": 100000, "current_cash": 100000, "current_cash_ratio": 1.0,
        "target_cash_ratio": 0.05, "required_cash_buffer": 5000,
        "available_buying_power": 95000, "is_violating_buffer": False,
    })
    monkeypatch.setattr(daily_plan, "format_markdown_report", lambda *args, **kwargs: "# plan\n")


def test_daily_plan_explicit_binding_controls_entry_stream_and_evidence(
    binding_environment, monkeypatch, tmp_path,
):
    captured: dict = {}
    _patch_daily_plan_dependencies(monkeypatch, captured)
    frozen = runtime.resolve_runtime_binding("synthetic_a")
    output = tmp_path / "plan.md"
    daily_plan.generate_daily_plan(
        date_str="2026-10-02", data_date="2026-10-01", current_state=_empty_state(),
        output_path=output, account_id="synthetic_a", account_binding=frozen,
    )
    payload = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
    assert captured["screener"]["tickers"] == ["AAA"]
    assert captured["screener"]["runtime_config"]["entry_period"] == 12
    assert captured["screener"]["apply_entry_filter"] is False
    assert payload["runtime_binding"]["requested_entry_universe"] == ["AAA", "BBB"]
    assert payload["runtime_binding"]["account_id"] == "synthetic_a"
    assert payload["runtime_binding"]["materialized_entry_universe"] == ["AAA"]
    assert payload["runtime_binding"]["excluded_symbols"] == [
        {"symbol": "BBB", "reason": "missing_market_data"}
    ]


def test_daily_plan_shared_snapshot_binding_controls_entry_stream(
    binding_environment, monkeypatch, tmp_path,
):
    captured: dict = {}
    _patch_daily_plan_dependencies(monkeypatch, captured)
    monkeypatch.setattr(daily_plan, "load_universe_snapshot_as_of_quarter", lambda date: {
        "snapshot": {"active_symbols": ["ZZZ", "CCC"], "removed": []},
        "metadata": {"policy": "quarterly_as_of", "warning": None},
    })
    frozen = runtime.resolve_runtime_binding("synthetic_b")
    output = tmp_path / "shared.md"
    daily_plan.generate_daily_plan(
        date_str="2026-10-02", data_date="2026-10-01", current_state=_empty_state(),
        output_path=output, account_id="synthetic_b", account_binding=frozen,
    )
    payload = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
    assert captured["screener"]["tickers"] == ["CCC", "ZZZ"]
    assert payload["runtime_binding"]["requested_entry_universe"] == ["CCC", "ZZZ"]
    assert payload["runtime_binding"]["materialized_entry_universe"] == ["CCC", "ZZZ"]
    assert payload["runtime_binding"]["excluded_symbols"] == []


def test_bound_daily_plan_applies_threshold_after_complete_score_and_rs(
    binding_environment, monkeypatch, tmp_path,
):
    captured: dict = {}
    real_build_target = daily_plan.build_target_portfolio_state
    _patch_daily_plan_dependencies(monkeypatch, captured)

    def build_candidates(**kwargs):
        captured["screener"] = kwargs
        row = {
            "Symbol": "AAA", "Date": "2026-10-01", "Price": 100.0, "Score": 0.5,
            **{f"signal_{name}": 0 for name in RUNTIME_SIGNAL_NAMES},
        }
        row["signal_obv"] = 1
        return pd.DataFrame([row])

    def capture_target(regime, candidates, config):
        captured["final_candidates"] = copy.deepcopy(candidates)
        captured["final_config"] = config
        target = real_build_target(regime, candidates, config)
        captured["target"] = target
        return target

    monkeypatch.setattr(daily_plan, "build_screener_results", build_candidates)
    monkeypatch.setattr(daily_plan, "calculate_candidate_rs_val", lambda *args, **kwargs: 0.1)
    monkeypatch.setattr(daily_plan, "build_target_portfolio_state", capture_target)
    frozen = runtime.resolve_runtime_binding("synthetic_a")

    daily_plan.generate_daily_plan(
        date_str="2026-10-02", data_date="2026-10-01", current_state=_empty_state(),
        output_path=tmp_path / "final-score.md", account_id="synthetic_a", account_binding=frozen,
    )

    assert captured["screener"]["apply_entry_filter"] is False
    assert captured["final_candidates"][0]["score"] >= captured["final_config"]["score_threshold"]
    assert captured["final_candidates"][0]["entry_signal"] is True
    assert captured["target"].target_symbols == ["AAA"]


@pytest.mark.parametrize(
    ("regime", "expected"),
    [("PANIC", False), ("BULL", True), ("BEAR", True)],
)
def test_final_buy_gate_preserves_regime_hard_entry_policy(regime, expected):
    candidate = {"score": 99.0, "rs_val": 1.0}

    assert daily_plan.is_buy_signal_candidate(candidate, 1.0, regime) is expected


def test_switch_candidate_filter_blocks_panic_and_allows_bull():
    candidates = pd.DataFrame([
        {"symbol": "AAA", "score": 99.0, "rs_val": 1.0, "close": 100.0},
    ])

    panic = daily_plan.filter_switch_candidates_for_daily_plan(candidates, 1.0, "PANIC")
    bull = daily_plan.filter_switch_candidates_for_daily_plan(candidates, 1.0, "BULL")

    assert panic.empty
    assert bull["symbol"].tolist() == ["AAA"]


def test_bound_panic_blocks_strategy_and_switch_buy_but_preserves_holding_sell(
    binding_environment, monkeypatch, tmp_path,
):
    captured: dict = {}
    real_build_target = daily_plan.build_target_portfolio_state
    _patch_daily_plan_dependencies(monkeypatch, captured)
    monkeypatch.setattr(daily_plan.market_analyzer, "get_market_state", lambda **kwargs: {
        "date": "2026-10-01", "regime": "PANIC", "trade_halted": False,
        "vix_value": 50.0, "triggers": {}, "plan": {},
    })

    def build_candidates(**kwargs):
        captured["screener"] = kwargs
        return pd.DataFrame([{
            "Symbol": "AAA", "Date": "2026-10-01", "Price": 100.0, "Score": 99.0,
            **{f"signal_{name}": 1 for name in RUNTIME_SIGNAL_NAMES},
        }])

    def capture_target(regime, candidates, config):
        captured["final_candidates"] = copy.deepcopy(candidates)
        target = real_build_target(regime, candidates, config)
        captured["target"] = target
        return target

    def panic_sell_diagnostic(symbol, *args, **kwargs):
        return {
            "symbol": symbol,
            "close": 8.0,
            "exit_low": 9.0,
            "atr_source": "indicator",
            "trailing_triggered": True,
            "stop_price": 9.0,
            "warning_items": [],
            "notes": "",
        }

    def capture_report(*args, **kwargs):
        captured["actions"] = copy.deepcopy(args[3])
        return "# panic plan\n"

    monkeypatch.setattr(daily_plan, "build_screener_results", build_candidates)
    monkeypatch.setattr(daily_plan, "calculate_candidate_rs_val", lambda *args, **kwargs: 1.0)
    monkeypatch.setattr(daily_plan, "build_target_portfolio_state", capture_target)
    monkeypatch.setattr(
        daily_plan, "compute_holding_score_for_switching",
        lambda *args, **kwargs: (0.0, 0.1, ["holding"]),
    )
    monkeypatch.setattr(
        daily_plan, "evaluate_switching_opportunity",
        lambda *args, **kwargs: pytest.fail("PANIC must not evaluate switch-in candidates"),
    )
    monkeypatch.setattr(
        daily_plan, "load_price_history_until",
        lambda *args, **kwargs: pd.DataFrame({"close": [8.0]}),
    )
    monkeypatch.setattr(daily_plan, "build_holding_sell_diagnostic", panic_sell_diagnostic)
    monkeypatch.setattr(daily_plan, "format_markdown_report", capture_report)
    frozen = runtime.resolve_runtime_binding("synthetic_a")

    daily_plan.generate_daily_plan(
        date_str="2026-10-02", data_date="2026-10-01",
        current_state=_empty_state(holdings=["BBB"]),
        output_path=tmp_path / "panic.md", account_id="synthetic_a", account_binding=frozen,
    )

    assert captured["screener"]["apply_entry_filter"] is False
    assert captured["final_candidates"][0]["score"] > 0
    assert captured["final_candidates"][0]["rs_val"] > 0
    assert captured["final_candidates"][0]["entry_signal"] is False
    assert captured["target"].target_symbols == []
    assert [item["symbol"] for item in captured["actions"] if item["type"] == "SELL"] == ["BBB"]
    assert not [item for item in captured["actions"] if item["type"] == "BUY"]


def test_bound_daily_plan_unexpected_materialization_error_aborts_without_exclusion_evidence(
    binding_environment, monkeypatch, tmp_path,
):
    captured: dict = {}
    _patch_daily_plan_dependencies(monkeypatch, captured)

    def fail(*args, **kwargs):
        raise PermissionError("market data read denied")

    monkeypatch.setattr(daily_plan.data_manager, "get_price_data", fail)
    frozen = runtime.resolve_runtime_binding("synthetic_a")
    output = tmp_path / "must-not-exist.md"

    with pytest.raises(PermissionError, match="market data read denied"):
        daily_plan.generate_daily_plan(
            date_str="2026-10-02", data_date="2026-10-01", current_state=_empty_state(),
            output_path=output, account_id="synthetic_a", account_binding=frozen,
        )

    assert "screener" not in captured
    assert not output.exists()


def test_config_snapshot_preserves_runtime_consumed_value_evidence(binding_environment):
    frozen = runtime.resolve_runtime_binding("synthetic_a")
    config, evidence = runtime.build_runtime_config(
        frozen, active_regime="BULL", start_date="x", end_date="x"
    )
    evidence["account_id"] = "synthetic_a"
    payload = build_paper_config_snapshot_payload(
        plan_date="2026-10-02",
        data_date="2026-10-01",
        trade_date="2026-10-02",
        market_state={"regime": "BULL"},
        final_config=config,
        source="test",
        market_state_write_log=False,
        runtime_binding=evidence,
    )
    assert payload["runtime_binding"] == evidence
    assert payload["runtime_binding"]["strategy_reference"] == {"id": "strategy_a", "version": "v1"}


def test_runbook_state_binding_is_passed_and_drift_blocks(
    binding_environment, monkeypatch, tmp_path,
):
    account_paths = create_initialized_account_paths(
        tmp_path / "account", account_id="synthetic_a", date_str="2026-10-01"
    )
    state = runbook_state.create_initial_state("synthetic_a", "2026-10-01", "2026-10-02")
    state_path = tmp_path / "state.json"
    runbook_state.save_state(state, state_path)
    monkeypatch.setattr(run_paper_daily_plan, "load_official_paper_state_for_daily_plan", lambda *args, **kwargs: _empty_state())
    captured: dict = {}
    monkeypatch.setattr(run_paper_daily_plan, "generate_daily_plan", lambda **kwargs: captured.update(kwargs) or str(kwargs["output_path"]))

    run_paper_daily_plan.run_paper_daily_plan(
        account_paths=account_paths, data_date="2026-10-01", trade_date="2026-10-02",
        runbook_state_path=state_path,
    )
    assert captured["account_binding"] == state.frozen_context.binding

    changed = copy.deepcopy(binding_environment["registry"])
    changed["strategy"][0]["content"]["parameters"]["entry_period"] = 99
    _write_json(binding_environment["registry_path"], changed)
    with pytest.raises(binding.BindingError, match="drift"):
        run_paper_daily_plan.run_paper_daily_plan(
            account_paths=account_paths, data_date="2026-10-01", trade_date="2026-10-02",
            runbook_state_path=state_path,
        )


def test_runbook_state_context_mismatch_fails_before_plan(
    binding_environment, monkeypatch, tmp_path,
):
    account_paths = create_initialized_account_paths(
        tmp_path / "account", account_id="synthetic_a", date_str="2026-10-01"
    )
    state = runbook_state.create_initial_state("synthetic_a", "2026-10-01", "2026-10-03")
    state_path = tmp_path / "state.json"
    runbook_state.save_state(state, state_path)
    with pytest.raises(ValueError, match="runbook_state_context_mismatch"):
        run_paper_daily_plan.run_paper_daily_plan(
            account_paths=account_paths, data_date="2026-10-01", trade_date="2026-10-02",
            runbook_state_path=state_path,
        )


def test_stage_a_daily_plan_command_pins_runbook_state_path(
    binding_environment, monkeypatch, tmp_path,
):
    command = runbook_command_registry.get_command("daily_plan")
    assert "--runbook-state-json" in command.argv_template
    assert "{runbook_state_path}" in command.argv_template
    state = runbook_state.create_initial_state("synthetic_a", "2026-10-01", "2026-10-02")
    state = runbook_state.pin_shared_input(state, {
        "data_date": "2026-10-01", "participant_account_ids": ["synthetic_a"],
        "snapshot": {"path": str(tmp_path / "market.sqlite3")},
    })
    state_path = runbook_state.get_state_path_for_context(
        tmp_path, "synthetic_a", "2026-10-01", "2026-10-02"
    )
    runbook_state.save_state(state, state_path)
    captured: dict = {}

    def fake_run(argv, cwd, timeout_sec, **kwargs):
        captured["argv"] = argv
        return {"executed": True, "exit_code": 1, "duration_ms": 1, "stdout": "", "stderr": "x"}

    monkeypatch.setattr(runbook_stage_runner, "run_allowlisted_command", fake_run)
    runbook_stage_runner._run_stage_a_command(
        state, tmp_path, tmp_path, command, False, 5
    )
    index = captured["argv"].index("--runbook-state-json")
    assert Path(captured["argv"][index + 1]) == state_path
