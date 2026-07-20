from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest

import core.daily_plan_generator as daily_plan_generator
import core.notion_manual_execution_importer as importer
import core.paper_manual_execution_commit as commit_module
from core.manual_execution_long_position_cap import (
    get_configured_manual_execution_hedge_symbols,
)
from core.notion_manual_execution_importer import build_manual_execution_preview
from core.notion_settings import NotionSettings
from core.paper_account_paths import PaperAccountPaths, build_paper_account_paths
from core.paper_account_state import build_paper_state_from_trades
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS, build_paper_trade_id
from core.paper_manual_execution_commit import (
    ManualExecutionCommitError,
    commit_manual_execution_preview,
)
from core.paper_market_valuation import PaperAccountValuation, PaperPositionValuation
from core.target_portfolio_state import (
    CurrentPortfolioState,
    RebalanceDecision,
    TargetPortfolioState,
)


EXECUTION_DATE = "2026-05-20"
ACCOUNT_ID = "paper_safe1_e2e"


def _state(symbols: list[str]) -> CurrentPortfolioState:
    return CurrentPortfolioState(
        current_symbols=list(symbols),
        current_cash_ratio=0.2,
        current_hedge_ratio=0.0,
        absolute_cash=100_000.0,
        shares={symbol: 10 for symbol in symbols},
        avg_price={symbol: 100.0 for symbol in symbols},
        highest_prices={symbol: 100.0 for symbol in symbols},
        hedge_symbols=[],
    )


def _patch_daily_plan(
    monkeypatch,
    *,
    candidates: list[dict],
    added_symbols: list[str],
    score_by_symbol: dict[str, float],
) -> None:
    monkeypatch.setattr(
        daily_plan_generator.market_analyzer,
        "get_market_state",
        lambda target_date=None, write_log=True: {
            "date": EXECUTION_DATE,
            "regime": "BULL",
            "vix_value": 20.0,
            "triggers": {},
        },
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
    monkeypatch.setattr(
        daily_plan_generator,
        "load_market_index_series",
        lambda *args, **kwargs: pd.Series(dtype="float64"),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "load_universe_snapshot_as_of_quarter",
        lambda _date: {"snapshot": {"removed": []}, "metadata": {"warning": None}},
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "build_screener_results",
        lambda **kwargs: pd.DataFrame(candidates).copy(),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "build_candidate_filter_diagnostics",
        lambda *args, **kwargs: (
            [],
            {
                "total": len(candidates),
                "pass": len(candidates),
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
            "BULL", 0.2, 0.0, 10, list(added_symbols)
        ),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "evaluate_rebalance_need",
        lambda *args, **kwargs: RebalanceDecision(
            True, ["e2e"], list(added_symbols), [], 0.0, 0.0
        ),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "get_cash_policy_status",
        lambda current_cash, total_equity, target_cash_ratio: {
            "total_equity": total_equity,
            "current_cash": current_cash,
            "current_cash_ratio": current_cash / total_equity,
            "target_cash_ratio": target_cash_ratio,
            "required_cash_buffer": 0.0,
            "available_buying_power": current_cash,
            "is_violating_buffer": False,
        },
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "calculate_available_buying_power",
        lambda *args, **kwargs: 100_000.0,
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "load_price_history_until",
        lambda *args, **kwargs: pd.DataFrame([{"close": 100.0}]),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "compute_holding_score_for_switching",
        lambda symbol, *args, **kwargs: (
            score_by_symbol.get(symbol, 10.0),
            0.0,
            ["e2e"],
        ),
    )
    monkeypatch.setattr(
        daily_plan_generator,
        "evaluate_switching_opportunity",
        lambda *args, **kwargs: [],
    )
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
            "highest_meta_updated_at": EXECUTION_DATE,
            "highest_meta_basis": "trade_price",
            "highest_meta_source": "e2e",
            "highest_warning_reasons": [],
            "stop_price": 90.0,
            "trailing_triggered": False,
            "review_status": "-",
            "warning_status": "-",
            "warning_items": [],
            "notes": "",
        },
    )


def _generate_actions(
    monkeypatch,
    root: Path,
    *,
    symbols: list[str],
    candidates: list[dict],
    added_symbols: list[str],
    score_by_symbol: dict[str, float],
) -> list[dict]:
    _patch_daily_plan(
        monkeypatch,
        candidates=candidates,
        added_symbols=added_symbols,
        score_by_symbol=score_by_symbol,
    )
    report_path = root / "daily_plan" / "daily_action_plan.md"
    sidecar_path = root / "daily_plan" / "daily_action_plan.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    daily_plan_generator.generate_daily_plan(
        date_str=EXECUTION_DATE,
        current_state=_state(symbols),
        output_path=report_path,
        json_sidecar_path=sidecar_path,
        write_json_sidecar=True,
        account_id=ACCOUNT_ID,
    )
    assert report_path.is_file()
    payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
    return payload["items"]


def _mapping_root() -> dict[str, dict[str, str]]:
    return {
        "manual_executions": {
            "name": "Name",
            "external_key": "External Key",
            "account_id": "Account ID",
            "execution_date": "Execution Date",
            "plan_date": "Plan Date",
            "symbol": "Symbol",
            "side": "Side",
            "quantity": "Quantity",
            "actual_price": "Actual Price",
            "commission": "Commission",
            "currency": "Currency",
            "broker": "Broker",
            "status": "Status",
            "linked_daily_plan_key": "Linked Daily Plan Key",
            "note": "Note",
            "validation_status": "Validation Status",
            "validation_message": "Validation Message",
            "import_status": "Import Status",
            "imported_at": "Imported At",
            "synced_at": "Synced At",
        }
    }


def _action_page(action: dict, sequence: int) -> dict:
    symbol = str(action["symbol"])
    side = str(action["action"])
    properties = {
        "Name": {"type": "title", "title": [{"plain_text": f"{symbol} {side}"}]},
        "External Key": {"type": "rich_text", "rich_text": []},
        "Account ID": {"type": "select", "select": {"name": ACCOUNT_ID}},
        "Execution Date": {"type": "date", "date": {"start": EXECUTION_DATE}},
        "Plan Date": {"type": "date", "date": {"start": EXECUTION_DATE}},
        "Symbol": {"type": "rich_text", "rich_text": [{"plain_text": symbol}]},
        "Side": {"type": "select", "select": {"name": side}},
        "Quantity": {"type": "number", "number": int(action["quantity"])},
        "Actual Price": {"type": "number", "number": float(action["price"])},
        "Commission": {"type": "number", "number": 0.0},
        "Currency": {"type": "select", "select": {"name": "USD"}},
        "Broker": {"type": "rich_text", "rich_text": [{"plain_text": "PAPER"}]},
        "Status": {"type": "select", "select": {"name": "READY"}},
        "Linked Daily Plan Key": {
            "type": "rich_text",
            "rich_text": [{"plain_text": f"daily_plan:{ACCOUNT_ID}:{EXECUTION_DATE}"}],
        },
        "Note": {"type": "rich_text", "rich_text": []},
        "Validation Status": {"type": "select", "select": None},
        "Validation Message": {"type": "rich_text", "rich_text": []},
        "Import Status": {"type": "select", "select": None},
        "Imported At": {"type": "rich_text", "rich_text": []},
        "Synced At": {"type": "rich_text", "rich_text": []},
    }
    return {
        "id": f"page-{sequence}",
        "created_time": f"2026-05-20T00:00:0{sequence}Z",
        "properties": properties,
    }


class _FixtureNotionClient:
    def __init__(self, pages: list[dict]):
        self.pages = pages

    def query_data_source(self, *args, **kwargs) -> list[dict]:
        return self.pages


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _execution_row(symbol: str, *, shares: int = 10, price: float = 100.0) -> dict:
    row = {
        "date": "2026-05-19",
        "regime": "MANUAL",
        "symbol": symbol,
        "side": "BUY",
        "shares": shares,
        "price": price,
        "gross_amount": shares * price,
        "source": "mfu_safe1_e2e_seed",
        "status": "READY_FOR_PAPER_TRADE",
        "reason": "seed",
        "notes": "",
        "rec_shares": shares,
        "rec_price": price,
        "created_at": "2026-05-19T00:00:00",
    }
    row["trade_id"] = build_paper_trade_id(row)
    return {column: row.get(column, "") for column in PAPER_EXECUTION_LOG_COLUMNS}


def _seed_account(root: Path, symbols: list[str]) -> PaperAccountPaths:
    paths = build_paper_account_paths(
        ACCOUNT_ID,
        account_root=root / "account",
        allow_legacy_default=False,
        create=True,
    )
    initial_cash = 100_000.0
    current_cash = initial_cash - len(symbols) * 1_000.0
    _write_csv(
        paths.execution_log_path,
        PAPER_EXECUTION_LOG_COLUMNS,
        [_execution_row(symbol) for symbol in symbols],
    )
    _write_csv(
        paths.account_snapshot_path,
        ["snapshot_date", "initial_cash", "cash", "currency"],
        [
            {
                "snapshot_date": "2026-05-19",
                "initial_cash": initial_cash,
                "cash": current_cash,
                "currency": "USD",
            }
        ],
    )
    _write_csv(
        paths.position_snapshot_path,
        ["snapshot_date", "symbol", "shares"],
        [
            {"snapshot_date": "2026-05-19", "symbol": symbol, "shares": 10}
            for symbol in symbols
        ],
    )
    return paths


def _build_preview(actions: list[dict], paths: PaperAccountPaths):
    pages = [_action_page(action, index) for index, action in enumerate(actions, 1)]
    return build_manual_execution_preview(
        client=_FixtureNotionClient(pages),
        settings=NotionSettings(
            enabled=True,
            token_env="NOTION_TOKEN",
            data_sources={"manual_executions": "fixture-data-source"},
        ),
        mapping_root=_mapping_root(),
        execution_date=EXECUTION_DATE,
        account_id=ACCOUNT_ID,
        account_paths=paths,
        reports_dir=paths.reports_dir,
    )


def _fake_valuation(
    state,
    snapshot_date: str,
    db_path: Path,
) -> PaperAccountValuation:
    positions = [
        PaperPositionValuation(
            symbol=symbol,
            shares=position.shares,
            avg_price=position.avg_price,
            close_price=position.avg_price,
            market_value=position.shares * position.avg_price,
            cost_value=position.shares * position.avg_price,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=0.0,
            valuation_price_date=snapshot_date,
            price_staleness_days=0,
        )
        for symbol, position in sorted(state.positions.items())
    ]
    positions_value = sum(position.market_value for position in positions)
    total_equity = state.cash + positions_value
    return PaperAccountValuation(
        snapshot_date=snapshot_date,
        cash=state.cash,
        positions_cost_value=positions_value,
        positions_market_value=positions_value,
        total_equity_cost_basis=total_equity,
        total_equity_market_value=total_equity,
        cash_ratio_market_value=state.cash / total_equity,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=0.0,
        valuation_method="mfu_safe1_e2e_fixture",
        valuation_price_date=snapshot_date,
        valuation_price_dates={position.symbol: snapshot_date for position in positions},
        price_staleness_days={position.symbol: 0 for position in positions},
        positions=positions,
    )


def _read_execution_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _non_hedge_count(paths: PaperAccountPaths) -> int:
    state = build_paper_state_from_trades(
        _read_execution_rows(paths.execution_log_path),
        initial_cash=100_000.0,
        currency="USD",
    )
    hedge_symbols = get_configured_manual_execution_hedge_symbols()
    return sum(symbol not in hedge_symbols for symbol in state.positions)


def test_normal_cap_daily_plan_preview_commit_end_to_end(monkeypatch, tmp_path: Path):
    symbols = [f"L{index}" for index in range(9)]
    candidates = [
        {"symbol": "TOP", "close": 50.0, "score": 9.0, "rs_val": 2.0, "Date": EXECUTION_DATE},
        {"symbol": "SECOND", "close": 40.0, "score": 8.0, "rs_val": 1.0, "Date": EXECUTION_DATE},
    ]
    actions = _generate_actions(
        monkeypatch,
        tmp_path,
        symbols=symbols,
        candidates=candidates,
        added_symbols=["TOP", "SECOND"],
        score_by_symbol={},
    )
    assert [item["symbol"] for item in actions] == ["TOP"]
    assert actions[0]["action"] == "BUY"

    paths = _seed_account(tmp_path, symbols)
    preview = _build_preview(actions, paths)
    assert preview.commit_allowed == "true"
    assert preview.long_position_policy["projected_count"] == 10

    monkeypatch.setattr(commit_module, "value_paper_account_state", _fake_valuation)
    result = commit_manual_execution_preview(
        execution_date=EXECUTION_DATE,
        preview_json_path=Path(preview.json_path),
        account_paths=paths,
    )
    assert result.committed_row_count == 1
    committed = _read_execution_rows(paths.execution_log_path)[-1]
    assert float(committed["price"]) == float(actions[0]["price"])
    assert abs(int(committed["shares"])) == int(actions[0]["quantity"])
    assert _non_hedge_count(paths) == 10


def test_over_cap_recovery_daily_plan_preview_commit_end_to_end(
    monkeypatch,
    tmp_path: Path,
):
    symbols = [f"L{index}" for index in range(11)]
    actions = _generate_actions(
        monkeypatch,
        tmp_path,
        symbols=symbols,
        candidates=[],
        added_symbols=[],
        score_by_symbol={"L0": 0.0},
    )
    assert actions == [
        {
            "symbol": "L0",
            "action": "SELL",
            "quantity": 10,
            "price": 100.0,
            "warning": None,
            "reason": "LONG_POSITION_CAP_RECOVERY",
            "note": None,
        }
    ]

    paths = _seed_account(tmp_path, symbols)
    preview = _build_preview(actions, paths)
    assert preview.commit_allowed == "true"
    assert preview.long_position_policy["mode"] == "OVER_CAP_RECOVERY"
    assert preview.long_position_policy["projected_count"] == 10

    monkeypatch.setattr(commit_module, "value_paper_account_state", _fake_valuation)
    result = commit_manual_execution_preview(
        execution_date=EXECUTION_DATE,
        preview_json_path=Path(preview.json_path),
        account_paths=paths,
    )
    assert result.committed_row_count == 1
    assert _non_hedge_count(paths) == 10


def test_commit_blocks_state_drift_before_any_persistent_write(
    monkeypatch,
    tmp_path: Path,
):
    symbols = [f"L{index}" for index in range(9)]
    actions = _generate_actions(
        monkeypatch,
        tmp_path,
        symbols=symbols,
        candidates=[
            {"symbol": "TOP", "close": 50.0, "score": 9.0, "rs_val": 2.0, "Date": EXECUTION_DATE},
        ],
        added_symbols=["TOP"],
        score_by_symbol={},
    )
    paths = _seed_account(tmp_path, symbols)
    preview = _build_preview(actions, paths)
    assert preview.commit_allowed == "true"

    with paths.execution_log_path.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_EXECUTION_LOG_COLUMNS)
        writer.writerow(_execution_row("DRIFT"))
    before = paths.execution_log_path.read_bytes()

    write_calls: list[str] = []
    real_append = commit_module.append_paper_execution_log

    def _record_append(*args, **kwargs):
        write_calls.append(f"append:{kwargs.get('commit', False)}")
        return real_append(*args, **kwargs)

    monkeypatch.setattr(commit_module, "append_paper_execution_log", _record_append)
    monkeypatch.setattr(
        commit_module,
        "_create_dev_backups",
        lambda **kwargs: write_calls.append("backup"),
    )
    monkeypatch.setattr(
        commit_module,
        "save_paper_current_state",
        lambda *args, **kwargs: write_calls.append("current_state"),
    )
    monkeypatch.setattr(
        commit_module,
        "save_paper_account_snapshot",
        lambda *args, **kwargs: write_calls.append("account_snapshot"),
    )
    monkeypatch.setattr(
        commit_module,
        "save_paper_position_snapshot",
        lambda *args, **kwargs: write_calls.append("position_snapshot"),
    )
    monkeypatch.setattr(
        commit_module,
        "_write_commit_sidecar",
        lambda **kwargs: write_calls.append("sidecar"),
    )

    with pytest.raises(ManualExecutionCommitError, match="current=10, projected=11"):
        commit_manual_execution_preview(
            execution_date=EXECUTION_DATE,
            preview_json_path=Path(preview.json_path),
            account_paths=paths,
        )

    assert write_calls == []
    assert paths.execution_log_path.read_bytes() == before
