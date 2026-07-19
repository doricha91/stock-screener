from pathlib import Path

import pandas as pd
import pytest

import core.daily_plan_generator as daily_plan_generator
from core.target_portfolio_state import CurrentPortfolioState, RebalanceDecision, TargetPortfolioState


def _state(symbols):
    return CurrentPortfolioState(
        current_symbols=list(symbols),
        current_cash_ratio=0.2,
        current_hedge_ratio=0.0,
        absolute_cash=20000.0,
        shares={symbol: 10 for symbol in symbols},
        avg_price={symbol: 100.0 for symbol in symbols},
        highest_prices={symbol: 100.0 for symbol in symbols},
        hedge_symbols=[],
    )


def _candidate_frame(include_candidate=True):
    if not include_candidate:
        return pd.DataFrame()
    return pd.DataFrame([
        {"symbol": "NEW", "close": 50.0, "score": 8.0, "rs_val": 1.0, "Date": "2026-05-20"}
    ])


def _patch_daily_plan(
    monkeypatch,
    *,
    score_by_symbol,
    include_candidate=True,
    added_symbols=None,
):
    captured = {"score_calls": [], "switch_inputs": [], "actions": [], "warnings": []}
    monkeypatch.setattr(
        daily_plan_generator.market_analyzer,
        "get_market_state",
        lambda target_date=None, write_log=True: {"date": "2026-05-20", "regime": "BULL", "vix_value": 20.0, "triggers": {}},
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "make_config",
        lambda *args, **kwargs: {"max_positions": 10, "max_long_positions": 10},
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "get_regime_config",
        lambda regime, base_config: {
            **base_config,
            "MARKET_BENCHMARK_SYMBOL": "SPY",
            "max_positions": 10,
            "max_long_positions": 10,
            "stale_candidate_max_days": 7,
            "target_cash_ratio": 0.2,
            "score_threshold": 1.5,
        },
    )
    monkeypatch.setattr(daily_plan_generator, "load_market_index_series", lambda *args, **kwargs: pd.Series(dtype="float64"))
    monkeypatch.setattr(
        daily_plan_generator,
        "load_universe_snapshot_as_of_quarter",
        lambda _date: {"snapshot": {"removed": []}, "metadata": {"warning": None}},
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "build_screener_results",
        lambda **kwargs: _candidate_frame(include_candidate).copy(),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "build_candidate_filter_diagnostics",
        lambda *args, **kwargs: ([], {"total": 0, "pass": 0, "failed_score": 0, "failed_rs": 0, "failed_rs_calc": 0, "failed_entry": 0, "stale": 0}),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "build_target_portfolio_state",
        lambda *args, **kwargs: TargetPortfolioState("BULL", 0.2, 0.0, 10, list(added_symbols or [])),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "evaluate_rebalance_need",
        lambda *args, **kwargs: RebalanceDecision(True, ["test"], list(added_symbols or []), [], 0.0, 0.0),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "get_cash_policy_status",
        lambda current_cash, total_equity, target_cash_ratio: {
            "total_equity": total_equity,
            "current_cash": current_cash,
            "current_cash_ratio": 0.2,
            "target_cash_ratio": target_cash_ratio,
            "required_cash_buffer": 0.0,
            "available_buying_power": current_cash,
            "is_violating_buffer": False,
        },
    )
    monkeypatch.setattr(daily_plan_generator, "calculate_available_buying_power", lambda *args, **kwargs: 10000.0)
    monkeypatch.setattr(
        daily_plan_generator,
        "load_price_history_until",
        lambda *args, **kwargs: pd.DataFrame([{"close": 100.0}]),
    )

    def fake_score(symbol, *args, **kwargs):
        captured["score_calls"].append(symbol)
        score = score_by_symbol.get(symbol, 5.0)
        return score, 0.0, ["test"]

    monkeypatch.setattr(daily_plan_generator, "compute_holding_score_for_switching", fake_score)
    monkeypatch.setattr(
        daily_plan_generator,
        "build_holding_sell_diagnostic",
        lambda symbol, *args, **kwargs: {
            "symbol": symbol,
            "close": 100.0,
            "exit_low": 90.0,
            "sell_signal": False,
            "atr": 1.0,
            "atr_source": "indicator",
            "highest_price": 100.0,
            "highest_source": "state",
            "highest_meta_updated_at": "2026-05-20",
            "highest_meta_basis": "trade_price",
            "highest_meta_source": "test",
            "highest_warning_reasons": [],
            "stop_price": 90.0,
            "trailing_triggered": False,
            "review_status": "-",
            "warning_status": "-",
            "warning_items": [],
            "notes": "",
        },
    )
    original_formatter = daily_plan_generator.format_markdown_report

    def capture_report(*args, **kwargs):
        captured["actions"] = list(args[3])
        captured["warnings"] = list(kwargs["warning_items"])
        return original_formatter(*args, **kwargs)

    monkeypatch.setattr(daily_plan_generator, "format_markdown_report", capture_report)
    return captured


def test_over_cap_invalid_score_with_candidate_completes_warning_plan_without_switch_or_buy(monkeypatch, tmp_path: Path):
    symbols = [f"L{i}" for i in range(11)]
    captured = _patch_daily_plan(monkeypatch, score_by_symbol={"L0": None}, added_symbols=["NEW"])
    monkeypatch.setattr(daily_plan_generator, "evaluate_switching_opportunity", lambda *args, **kwargs: pytest.fail("switching must not run"))
    monkeypatch.setattr(daily_plan_generator, "build_switch_action_items", lambda *args, **kwargs: pytest.fail("switch builder must not run"))
    output = tmp_path / "plan.md"

    daily_plan_generator.generate_daily_plan(
        date_str="2026-05-20", current_state=_state(symbols), output_path=output, write_json_sidecar=False
    )

    assert len(captured["score_calls"]) == len(symbols)
    assert not captured["actions"]
    assert captured["warnings"][0]["reason"] == daily_plan_generator.WARNING_LONG_POSITION_RECOVERY_SCORE_UNAVAILABLE
    markdown = output.read_text(encoding="utf-8")
    assert "Warnings" in markdown and "L0" in markdown


def test_over_cap_switchable_candidate_creates_only_exact_recovery_sells(monkeypatch, tmp_path: Path):
    symbols = [f"L{i}" for i in range(12)]
    scores = {symbol: 10.0 for symbol in symbols}
    scores.update({"L0": 1.0, "L1": 1.0})
    captured = _patch_daily_plan(monkeypatch, score_by_symbol=scores, added_symbols=["NEW"])
    monkeypatch.setattr(daily_plan_generator, "evaluate_switching_opportunity", lambda *args, **kwargs: pytest.fail("switching must not run"))
    monkeypatch.setattr(daily_plan_generator, "build_switch_action_items", lambda *args, **kwargs: pytest.fail("switch builder must not run"))

    daily_plan_generator.generate_daily_plan(
        date_str="2026-05-20", current_state=_state(symbols), output_path=tmp_path / "plan.md", write_json_sidecar=False
    )

    assert [item["symbol"] for item in captured["actions"]] == ["L1", "L0"]
    assert all(item["reason"] == "LONG_POSITION_CAP_RECOVERY" for item in captured["actions"])


def test_normal_projects_only_valid_once_computed_holding_scores_to_switching(monkeypatch, tmp_path: Path):
    symbols = ["VALID", "INVALID"]
    captured = _patch_daily_plan(monkeypatch, score_by_symbol={"VALID": 5.0, "INVALID": None}, added_symbols=["NEW"])

    def fake_switch(_candidates, holding_rows, _config):
        captured["switch_inputs"] = holding_rows
        return [{"sell_symbol": "VALID", "buy_symbol": "NEW", "buy_row": {"close": 50.0}, "score_gap": 3.0}]

    monkeypatch.setattr(daily_plan_generator, "evaluate_switching_opportunity", fake_switch)
    daily_plan_generator.generate_daily_plan(
        date_str="2026-05-20", current_state=_state(symbols), output_path=tmp_path / "plan.md", write_json_sidecar=False
    )

    assert captured["score_calls"] == symbols
    assert [row["symbol"] for row in captured["switch_inputs"]] == ["VALID"]
    assert [item["reason"].split()[0] for item in captured["actions"]] == ["SWITCH_OUT", "SWITCH_IN"]


@pytest.mark.parametrize("invalid", [False, True])
def test_over_cap_without_candidates_still_scores_and_recovers_or_warns(monkeypatch, tmp_path: Path, invalid: bool):
    symbols = [f"L{i}" for i in range(11)]
    captured = _patch_daily_plan(
        monkeypatch,
        score_by_symbol={"L0": None if invalid else 0.0},
        include_candidate=False,
        added_symbols=[],
    )
    monkeypatch.setattr(daily_plan_generator, "evaluate_switching_opportunity", lambda *args, **kwargs: pytest.fail("switching must not run"))
    daily_plan_generator.generate_daily_plan(
        date_str="2026-05-20", current_state=_state(symbols), output_path=tmp_path / "plan.md", write_json_sidecar=False
    )

    assert len(captured["score_calls"]) == len(symbols)
    if invalid:
        assert captured["actions"] == []
        assert captured["warnings"][0]["reason"] == daily_plan_generator.WARNING_LONG_POSITION_RECOVERY_SCORE_UNAVAILABLE
    else:
        assert captured["warnings"] == []
        assert captured["actions"] == [{
            "type": "SELL", "symbol": "L0", "shares": 10, "price": 100.0, "reason": "LONG_POSITION_CAP_RECOVERY"
        }]


def test_final_normal_cap_violation_fails_before_markdown_write(monkeypatch, tmp_path: Path):
    symbols = [f"L{i}" for i in range(10)]
    _patch_daily_plan(monkeypatch, score_by_symbol={}, added_symbols=["NEW"])
    monkeypatch.setattr(daily_plan_generator, "evaluate_switching_opportunity", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        daily_plan_generator,
        "build_strategy_entry_action_items",
        lambda *args, **kwargs: [{"type": "BUY", "symbol": "NEW", "shares": 1, "price": 50.0, "reason": "STRATEGY_ENTRY"}],
    )
    output = tmp_path / "unsafe_normal.md"

    with pytest.raises(RuntimeError, match="Final NORMAL"):
        daily_plan_generator.generate_daily_plan(
            date_str="2026-05-20", current_state=_state(symbols), output_path=output, write_json_sidecar=False
        )
    assert not output.exists()


def test_final_over_cap_buy_violation_fails_before_markdown_write(monkeypatch, tmp_path: Path):
    symbols = [f"L{i}" for i in range(11)]
    _patch_daily_plan(monkeypatch, score_by_symbol={"L0": None}, added_symbols=["NEW"])
    monkeypatch.setattr(daily_plan_generator, "evaluate_switching_opportunity", lambda *args, **kwargs: pytest.fail("switching must not run"))
    monkeypatch.setattr(
        daily_plan_generator,
        "build_strategy_entry_action_items",
        lambda *args, **kwargs: [{"type": "BUY", "symbol": "NEW", "shares": 1, "price": 50.0, "reason": "STRATEGY_ENTRY"}],
    )
    output = tmp_path / "unsafe_recovery.md"

    with pytest.raises(RuntimeError, match="Final OVER_CAP_RECOVERY"):
        daily_plan_generator.generate_daily_plan(
            date_str="2026-05-20", current_state=_state(symbols), output_path=output, write_json_sidecar=False
        )
    assert not output.exists()
