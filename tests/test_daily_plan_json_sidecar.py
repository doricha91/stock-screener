import json
from pathlib import Path

import pandas as pd

import core.daily_plan_generator as daily_plan_generator
import scripts.run_paper_daily_plan as run_paper_daily_plan
from core.paper_account_paths import build_paper_account_paths
from core.paper_config_hash import PAPER_CONFIG_HASH_POLICY, compute_paper_config_hash
from core.target_portfolio_state import (
    CurrentPortfolioState,
    RebalanceDecision,
    TargetPortfolioState,
)


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


def _patch_minimal_daily_plan_dependencies(monkeypatch):
    monkeypatch.setattr(
        daily_plan_generator.market_analyzer,
        "get_market_state",
        lambda target_date=None, write_log=True: {
            "date": "2026-05-20",
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
        "build_candidate_filter_diagnostics",
        lambda *args, **kwargs: (
            [],
            {
                "total": 0,
                "pass": 0,
                "failed_score": 0,
                "failed_rs": 0,
                "failed_rs_calc": 0,
                "failed_entry": 0,
                "stale": 0,
            },
        ),
    )
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
            rebalance_needed=True,
            rebalance_reason=["test"],
            symbol_diff_added=["AAPL"],
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
        "calculate_available_buying_power",
        lambda *args, **kwargs: 10000.0,
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "build_strategy_entry_action_items",
        lambda *args, **kwargs: [
            {
                "type": "BUY",
                "symbol": "AAPL",
                "shares": 10,
                "price": 200.0,
                "reason": "STRATEGY_ENTRY",
                "note": "fixture note",
            }
        ],
    )


def test_daily_plan_json_sidecar_is_written_from_structured_action_items(monkeypatch, tmp_path: Path):
    _patch_minimal_daily_plan_dependencies(monkeypatch)
    output_path = tmp_path / "daily_action_plan_20260520.md"
    markdown_content = "# injected paper plan\n"
    monkeypatch.setattr(
        daily_plan_generator,
        "format_markdown_report",
        lambda *args, **kwargs: markdown_content,
    )

    report_path = daily_plan_generator.generate_daily_plan(
        date_str="2026-05-20",
        current_state=_empty_state(),
        output_path=output_path,
        account_id="paper_sandbox",
        run_mode="exploratory",
        official_run=False,
    )

    sidecar_path = output_path.with_suffix(".json")
    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert report_path == str(output_path)
    assert output_path.read_text(encoding="utf-8") == markdown_content
    assert payload["schema_version"] == "paper_daily_plan.v1"
    assert payload["account_id"] == "paper_sandbox"
    assert payload["plan_date"] == "2026-05-20"
    assert payload["run_mode"] == "exploratory"
    assert payload["official_run"] is False
    assert payload["fingerprints"] == {"generator_version": "paper_daily_plan.v1"}
    assert payload["items"] == [
        {
            "symbol": "AAPL",
            "action": "BUY",
            "quantity": 10,
            "price": 200.0,
            "warning": None,
            "reason": "STRATEGY_ENTRY",
            "note": "fixture note",
        }
    ]


def test_daily_plan_json_sidecar_does_not_replace_config_snapshot(monkeypatch, tmp_path: Path):
    _patch_minimal_daily_plan_dependencies(monkeypatch)
    output_path = tmp_path / "daily_action_plan_20260520.md"
    snapshot_path = tmp_path / "config_snapshots" / "paper_config_snapshot_20260520.json"
    archive_dir = tmp_path / "archive" / "config_snapshots"
    monkeypatch.setattr(daily_plan_generator, "format_markdown_report", lambda *args, **kwargs: "# plan\n")

    def _fake_save_paper_config_snapshot(**kwargs):
        Path(kwargs["output_path"]).parent.mkdir(parents=True, exist_ok=True)
        Path(kwargs["output_path"]).write_text(
            json.dumps({"schema_version": "paper_config_snapshot.test"}),
            encoding="utf-8",
        )

    monkeypatch.setattr(daily_plan_generator, "save_paper_config_snapshot", _fake_save_paper_config_snapshot)

    daily_plan_generator.generate_daily_plan(
        date_str="2026-05-20",
        current_state=_empty_state(),
        output_path=output_path,
        config_snapshot_path=snapshot_path,
        config_snapshot_archive_dir=archive_dir,
        account_id="paper_sandbox",
    )

    assert output_path.with_suffix(".json").exists()
    assert snapshot_path.exists()
    assert output_path.with_suffix(".json") != snapshot_path
    assert json.loads(snapshot_path.read_text(encoding="utf-8")) == {
        "schema_version": "paper_config_snapshot.test"
    }
    sidecar_payload = json.loads(output_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert sidecar_payload["fingerprints"]["generator_version"] == "paper_daily_plan.v1"
    assert sidecar_payload["fingerprints"]["config_snapshot_path"] == str(snapshot_path)
    assert sidecar_payload["fingerprints"]["config_hash"] == compute_paper_config_hash(
        {"schema_version": "paper_config_snapshot.test"}
    )
    assert sidecar_payload["fingerprints"]["config_hash_policy"] == PAPER_CONFIG_HASH_POLICY


def test_run_paper_daily_plan_passes_official_sidecar_metadata(monkeypatch, tmp_path: Path):
    captured: dict = {}
    account_paths = build_paper_account_paths(
        "paper_sandbox",
        account_root=tmp_path / "paper_sandbox",
        create=True,
    )

    monkeypatch.setattr(
        run_paper_daily_plan,
        "load_official_paper_state_for_daily_plan",
        lambda date_str: _empty_state(),
    )

    def _fake_generate_daily_plan(**kwargs):
        captured.update(kwargs)
        return str(kwargs["output_path"])

    monkeypatch.setattr(run_paper_daily_plan, "generate_daily_plan", _fake_generate_daily_plan)

    report_path = run_paper_daily_plan.run_paper_daily_plan("20260520", account_paths=account_paths)

    assert report_path == str(account_paths.daily_action_plan_path("20260520"))
    assert captured["account_id"] == "paper_sandbox"
    assert captured["run_mode"] == "official"
    assert captured["official_run"] is True
    assert captured["state_snapshot_path"] == account_paths.current_state_snapshot_path("20260520")


def test_daily_plan_json_sidecar_records_state_snapshot_path(monkeypatch, tmp_path: Path):
    _patch_minimal_daily_plan_dependencies(monkeypatch)
    output_path = tmp_path / "daily_action_plan_20260520.md"
    state_snapshot_path = tmp_path / "paper_current_state_20260520.json"
    monkeypatch.setattr(daily_plan_generator, "format_markdown_report", lambda *args, **kwargs: "# plan\n")

    daily_plan_generator.generate_daily_plan(
        date_str="2026-05-20",
        current_state=_empty_state(),
        output_path=output_path,
        account_id="paper_sandbox",
        state_snapshot_path=state_snapshot_path,
    )

    payload = json.loads(output_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert payload["fingerprints"]["generator_version"] == "paper_daily_plan.v1"
    assert payload["fingerprints"]["state_snapshot_path"] == str(state_snapshot_path)
    assert "code_commit_sha" not in payload["fingerprints"]


def test_daily_plan_json_sidecar_omits_config_hash_when_snapshot_missing(tmp_path: Path):
    snapshot_path = tmp_path / "missing_config_snapshot.json"

    payload = daily_plan_generator.build_daily_plan_json_payload(
        account_id="paper_sandbox",
        plan_date="2026-05-20",
        run_mode="exploratory",
        official_run=False,
        action_items=[],
        config_snapshot_path=snapshot_path,
    )

    assert payload["fingerprints"]["config_snapshot_path"] == str(snapshot_path)
    assert "config_hash" not in payload["fingerprints"]
    assert "config_hash_policy" not in payload["fingerprints"]


def test_daily_plan_json_sidecar_omits_config_hash_when_snapshot_malformed(tmp_path: Path):
    snapshot_path = tmp_path / "paper_config_snapshot_20260520.json"
    snapshot_path.write_text("{bad json", encoding="utf-8")

    payload = daily_plan_generator.build_daily_plan_json_payload(
        account_id="paper_sandbox",
        plan_date="2026-05-20",
        run_mode="exploratory",
        official_run=False,
        action_items=[],
        config_snapshot_path=snapshot_path,
    )

    assert payload["fingerprints"]["config_snapshot_path"] == str(snapshot_path)
    assert "config_hash" not in payload["fingerprints"]
    assert "config_hash_policy" not in payload["fingerprints"]
