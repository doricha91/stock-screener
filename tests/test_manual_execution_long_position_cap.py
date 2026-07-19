from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

import config
import core.notion_manual_execution_importer as importer
import core.paper_manual_execution_commit as commit_module
from core.long_position_policy import LongPositionAction
from core.manual_execution_long_position_cap import (
    get_configured_manual_execution_hedge_symbols,
    validate_manual_execution_long_position_actions,
)
from core.notion_manual_execution_importer import (
    ManualExecutionCandidate,
    build_manual_execution_preview,
)
from core.notion_settings import NotionSettings
from core.paper_account_paths import build_paper_account_paths
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS, build_paper_trade_id
from core.paper_market_valuation import PaperAccountValuation, PaperPositionValuation
from core.paper_manual_execution_commit import (
    ManualExecutionCommitError,
    commit_manual_execution_preview,
)


EXECUTION_DATE = "2026-07-17"


class _Client:
    pass


def _candidate(symbol: str, side: str, quantity: int, *, price: float = 10.0) -> ManualExecutionCandidate:
    return ManualExecutionCandidate(
        account_id="paper_default",
        page_id=f"page-{symbol}-{side}",
        name=f"{symbol} {side}",
        execution_date=EXECUTION_DATE,
        plan_date=EXECUTION_DATE,
        symbol=symbol,
        side=side,
        quantity=quantity,
        actual_price=price,
        commission=0.0,
        currency="USD",
        broker="PAPER",
        status="READY",
        note=None,
        linked_daily_plan_key=f"daily_plan:{EXECUTION_DATE}",
        notion_external_key=None,
        validation_status_raw=None,
        validation_message_raw=None,
        import_status_raw=None,
        imported_at_raw=None,
        synced_at_raw=None,
    )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _run_preview(
    monkeypatch,
    tmp_path: Path,
    *,
    holdings: dict[str, int],
    candidates: list[ManualExecutionCandidate],
    max_long_positions: int = 10,
    state_payload: dict | None = None,
):
    account_path = tmp_path / "paper_account_snapshot.csv"
    position_path = tmp_path / "paper_position_snapshot.csv"
    execution_path = tmp_path / "paper_execution_log.csv"
    _write_csv(account_path, ["snapshot_date", "cash"], [{"snapshot_date": "2026-07-16", "cash": "100000"}])
    _write_csv(
        position_path,
        ["snapshot_date", "symbol", "shares"],
        [
            {"snapshot_date": "2026-07-16", "symbol": symbol, "shares": shares}
            for symbol, shares in holdings.items()
        ],
    )
    _write_csv(execution_path, ["trade_id"], [])
    if state_payload is not None:
        (tmp_path / "paper_current_state_20260717.json").write_text(
            json.dumps(state_payload),
            encoding="utf-8",
        )
    monkeypatch.setattr(importer, "paper_account_snapshot_path", lambda: account_path)
    monkeypatch.setattr(importer, "paper_position_snapshot_path", lambda: position_path)
    monkeypatch.setattr(importer, "fetch_manual_execution_pages", lambda **kwargs: [])
    monkeypatch.setattr(importer, "normalize_manual_execution_pages", lambda **kwargs: candidates)
    return build_manual_execution_preview(
        client=_Client(),
        settings=NotionSettings(enabled=True, token_env="NOTION_TOKEN", data_sources={"manual_executions": "ds"}),
        mapping_root={"manual_executions": {}},
        execution_date=EXECUTION_DATE,
        reports_dir=tmp_path / "reports",
        max_long_positions=max_long_positions,
    )


def _symbols(count: int) -> dict[str, int]:
    return {f"S{index:02d}": 5 for index in range(count)}


def test_configured_hedges_are_normalized_and_immutable(monkeypatch):
    monkeypatch.setattr(config, "HEDGE_TICKERS", [" sqqq ", "TQQQ", "sqqq"])
    hedges = get_configured_manual_execution_hedge_symbols()
    assert hedges == frozenset({"SQQQ", "TQQQ"})
    assert isinstance(hedges, frozenset)


def test_configured_hedges_are_read_at_call_time(monkeypatch):
    monkeypatch.setattr(config, "HEDGE_TICKERS", ["SQQQ"])
    assert get_configured_manual_execution_hedge_symbols() == frozenset({"SQQQ"})
    monkeypatch.setattr(config, "HEDGE_TICKERS", ["CUSTOM"])
    assert get_configured_manual_execution_hedge_symbols() == frozenset({"CUSTOM"})


def test_custom_is_not_a_hedge_when_absent_from_config(monkeypatch):
    monkeypatch.setattr(config, "HEDGE_TICKERS", ["SQQQ"])
    assert "CUSTOM" not in get_configured_manual_execution_hedge_symbols()


def test_hedge_generator_is_materialized_once_for_policy_and_over_cap_check():
    class SingleUseHedges:
        def __init__(self):
            self.iterations = 0

        def __iter__(self):
            self.iterations += 1
            if self.iterations > 1:
                raise AssertionError("hedge iterable consumed more than once")
            yield " sqqq "

    hedges = SingleUseHedges()
    result = validate_manual_execution_long_position_actions(
        _symbols(11),
        [LongPositionAction(symbol="SQQQ", action_type="BUY", quantity=1)],
        hedge_symbols=hedges,
    )
    assert result.allowed is True
    assert hedges.iterations == 1


def test_invalid_hedge_and_action_inputs_remain_fail_closed():
    invalid_hedge = validate_manual_execution_long_position_actions(
        _symbols(11),
        [],
        hedge_symbols=[None],
    )
    invalid_action = validate_manual_execution_long_position_actions(
        _symbols(11),
        [{"action_type": "BUY", "quantity": 1}],
    )
    assert invalid_hedge.allowed is False
    assert "invalid_position_input" in invalid_hedge.error_codes
    assert invalid_action.allowed is False
    assert "invalid_action_input" in invalid_action.error_codes


def test_preview_allows_ninth_position_plus_one_new_buy(monkeypatch, tmp_path):
    preview = _run_preview(monkeypatch, tmp_path, holdings=_symbols(9), candidates=[_candidate("NEW", "BUY", 1)])
    assert preview.commit_allowed == "true"
    assert preview.long_position_policy["projected_count"] == 10


def test_preview_blocks_tenth_position_plus_one_new_buy_as_whole_batch(monkeypatch, tmp_path):
    candidates = [_candidate("NEW", "BUY", 1), _candidate("S00", "SELL", 1)]
    preview = _run_preview(monkeypatch, tmp_path, holdings=_symbols(10), candidates=candidates)
    assert preview.commit_allowed == "false"
    assert preview.fail_count == 2
    assert all("long_position_cap_blocked" in {issue.code for issue in item.validation_issues} for item in candidates)
    assert preview.long_position_policy["error_codes"] == ["max_long_positions_exceeded"]


def test_preview_top_up_does_not_increase_distinct_count(monkeypatch, tmp_path):
    preview = _run_preview(monkeypatch, tmp_path, holdings=_symbols(10), candidates=[_candidate("S00", "BUY", 2)])
    assert preview.commit_allowed == "true"
    assert preview.long_position_policy["current_count"] == preview.long_position_policy["projected_count"] == 10


def test_preview_full_sell_then_new_buy_is_allowed(monkeypatch, tmp_path):
    preview = _run_preview(
        monkeypatch,
        tmp_path,
        holdings=_symbols(10),
        candidates=[_candidate("S00", "SELL", 5), _candidate("NEW", "BUY", 1)],
    )
    assert preview.commit_allowed == "true"
    assert preview.long_position_policy["projected_count"] == 10


def test_preview_partial_sell_then_new_buy_is_blocked(monkeypatch, tmp_path):
    preview = _run_preview(
        monkeypatch,
        tmp_path,
        holdings=_symbols(10),
        candidates=[_candidate("S00", "SELL", 4), _candidate("NEW", "BUY", 1)],
    )
    assert preview.commit_allowed == "false"
    assert preview.long_position_policy["projected_count"] == 11


def test_preview_excludes_configured_hedge_symbol(monkeypatch, tmp_path):
    holdings = {**_symbols(10), "SQQQ": 3}
    preview = _run_preview(
        monkeypatch,
        tmp_path,
        holdings=holdings,
        candidates=[_candidate("SQQQ", "BUY", 1)],
    )
    assert preview.commit_allowed == "true"
    assert preview.long_position_policy["current_count"] == 10


def test_preview_over_cap_allows_new_configured_hedge_buy(monkeypatch, tmp_path):
    preview = _run_preview(
        monkeypatch,
        tmp_path,
        holdings=_symbols(11),
        candidates=[_candidate(" sqqq ", "BUY", 2)],
    )
    assert preview.commit_allowed == "true"
    assert preview.long_position_policy["mode"] == "OVER_CAP_RECOVERY"
    assert preview.long_position_policy["projected_count"] == 11
    assert "buy_blocked_while_over_cap" not in preview.long_position_policy["error_codes"]


def test_preview_state_json_does_not_change_configured_hedges(monkeypatch, tmp_path):
    preview = _run_preview(
        monkeypatch,
        tmp_path,
        holdings=_symbols(11),
        candidates=[_candidate("CUSTOM", "BUY", 1)],
        state_payload={"hedge_symbols": ["CUSTOM"]},
    )
    assert preview.commit_allowed == "false"
    assert preview.long_position_policy["current_count"] == 11
    assert "buy_blocked_while_over_cap" in preview.long_position_policy["error_codes"]


def test_preview_over_cap_buy_blocks_entire_batch(monkeypatch, tmp_path):
    candidates = [_candidate("S00", "SELL", 5), _candidate("NEW", "BUY", 1)]
    preview = _run_preview(monkeypatch, tmp_path, holdings=_symbols(11), candidates=candidates)
    assert preview.commit_allowed == "false"
    assert preview.fail_count == len(candidates)
    assert "buy_blocked_while_over_cap" in preview.long_position_policy["error_codes"]


def test_preview_over_cap_recovery_sells_only_are_allowed(monkeypatch, tmp_path):
    preview = _run_preview(
        monkeypatch,
        tmp_path,
        holdings=_symbols(11),
        candidates=[_candidate("S00", "SELL", 5)],
    )
    assert preview.commit_allowed == "true"
    assert preview.long_position_policy["mode"] == "OVER_CAP_RECOVERY"
    assert preview.long_position_policy["projected_count"] == 10


def test_preview_uses_configured_cap_fifteen_without_literal_ten(monkeypatch, tmp_path):
    preview = _run_preview(
        monkeypatch,
        tmp_path,
        holdings=_symbols(14),
        candidates=[_candidate("NEW", "BUY", 1)],
        max_long_positions=15,
    )
    assert preview.commit_allowed == "true"
    assert preview.long_position_policy["max_long_positions"] == 15


def _execution_row(symbol: str, *, shares: int = 5, price: float = 10.0) -> dict:
    row = {
        "date": "2026-07-16",
        "regime": "MANUAL",
        "symbol": symbol,
        "side": "BUY",
        "shares": shares,
        "price": price,
        "gross_amount": shares * price,
        "source": "seed",
        "status": "READY_FOR_PAPER_TRADE",
        "reason": "seed",
        "notes": "",
        "rec_shares": shares,
        "rec_price": price,
        "created_at": "2026-07-16T00:00:00",
    }
    row["trade_id"] = build_paper_trade_id(row)
    return {column: row.get(column, "") for column in PAPER_EXECUTION_LOG_COLUMNS}


def _commit_candidate(symbol: str, side: str, quantity: int, *, price: float = 10.0, sequence: int = 1) -> dict:
    return {
        "account_id": "paper_cap_test",
        "page_id": f"page-{sequence}",
        "name": f"{symbol} {side}",
        "execution_date": EXECUTION_DATE,
        "plan_date": EXECUTION_DATE,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "actual_price": price,
        "commission": 0.0,
        "currency": "USD",
        "broker": "PAPER",
        "status": "READY",
        "note": "",
        "linked_daily_plan_key": f"daily_plan:paper_cap_test:{EXECUTION_DATE}",
        "canonical_key": f"manual_execution:paper_cap_test:{EXECUTION_DATE}:{symbol}:{side}:{sequence:02d}",
        "validation_issues": [],
        "validation_status": "PASS",
    }


def _commit_env(tmp_path: Path, candidates: list[dict], holdings_count: int):
    paths = build_paper_account_paths(
        "paper_cap_test",
        account_root=tmp_path / "paper_cap_test",
        allow_legacy_default=False,
        create=True,
    )
    _write_csv(paths.execution_log_path, PAPER_EXECUTION_LOG_COLUMNS, [_execution_row(symbol) for symbol in _symbols(holdings_count)])
    _write_csv(
        paths.account_snapshot_path,
        ["snapshot_date", "initial_cash", "cash", "currency"],
        [{"snapshot_date": "2026-07-16", "initial_cash": "100000", "cash": "99500", "currency": "USD"}],
    )
    _write_csv(paths.position_snapshot_path, ["snapshot_date", "symbol", "shares"], [])
    preview_path = tmp_path / "preview.json"
    preview_path.write_text(
        json.dumps(
            {
                "execution_date": EXECUTION_DATE,
                "account_id": "paper_cap_test",
                "candidate_count": len(candidates),
                "pass_count": len(candidates),
                "warning_count": 0,
                "fail_count": 0,
                "commit_allowed": "true",
                "long_position_policy": {"allowed": True, "projected_count": 0},
                "candidates": candidates,
            }
        ),
        encoding="utf-8",
    )
    return paths, preview_path


def _fake_valuation(state, snapshot_date: str, db_path: Path) -> PaperAccountValuation:
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
        valuation_method="test",
        valuation_price_date=snapshot_date,
        valuation_price_dates={position.symbol: snapshot_date for position in positions},
        price_staleness_days={position.symbol: 0 for position in positions},
        positions=positions,
    )


def test_commit_state_json_custom_hedge_does_not_change_config_policy(tmp_path):
    paths, preview_path = _commit_env(
        tmp_path,
        [_commit_candidate("CUSTOM", "BUY", 2)],
        11,
    )
    paths.current_state_snapshot_path(EXECUTION_DATE).write_text(
        json.dumps({"hedge_symbols": ["CUSTOM"]}), encoding="utf-8"
    )
    with pytest.raises(ManualExecutionCommitError, match="buy_blocked_while_over_cap"):
        commit_manual_execution_preview(
            execution_date=EXECUTION_DATE,
            preview_json_path=preview_path,
            account_paths=paths,
        )
def test_commit_ignores_preview_embedded_hedge_and_policy_results(tmp_path):
    paths, preview_path = _commit_env(
        tmp_path,
        [_commit_candidate("CUSTOM", "BUY", 2)],
        11,
    )
    payload = json.loads(preview_path.read_text(encoding="utf-8"))
    payload["hedge_symbols"] = ["CUSTOM"]
    payload["long_position_policy"] = {
        "allowed": True,
        "current_count": 11,
        "projected_count": 11,
    }
    preview_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManualExecutionCommitError, match="buy_blocked_while_over_cap"):
        commit_manual_execution_preview(
            execution_date=EXECUTION_DATE,
            preview_json_path=preview_path,
            account_paths=paths,
        )


def test_commit_over_cap_full_recovery_sell_succeeds(monkeypatch, tmp_path):
    paths, preview_path = _commit_env(
        tmp_path,
        [_commit_candidate("S00", "SELL", 5, price=12.34)],
        11,
    )
    monkeypatch.setattr(commit_module, "value_paper_account_state", _fake_valuation)
    result = commit_manual_execution_preview(
        execution_date=EXECUTION_DATE,
        preview_json_path=preview_path,
        account_paths=paths,
    )
    assert result.committed_row_count == 1
    with paths.execution_log_path.open("r", encoding="utf-8-sig", newline="") as handle:
        committed = list(csv.DictReader(handle))[-1]
    assert committed["side"] == "SELL"
    assert committed["shares"] == "-5"
    assert float(committed["price"]) == 12.34


def test_commit_over_cap_new_configured_hedge_buy_succeeds(monkeypatch, tmp_path):
    paths, preview_path = _commit_env(
        tmp_path,
        [_commit_candidate("sqqq", "BUY", 7, price=22.22)],
        11,
    )
    monkeypatch.setattr(commit_module, "value_paper_account_state", _fake_valuation)
    result = commit_manual_execution_preview(
        execution_date=EXECUTION_DATE,
        preview_json_path=preview_path,
        account_paths=paths,
    )
    assert result.committed_row_count == 1
    with paths.execution_log_path.open("r", encoding="utf-8-sig", newline="") as handle:
        committed = list(csv.DictReader(handle))[-1]
    assert committed["symbol"] == "SQQQ"
    assert committed["shares"] == "7"
    assert float(committed["price"]) == 22.22


def test_commit_over_cap_mixed_recovery_sell_and_regular_buy_blocks_all(tmp_path):
    candidates = [
        _commit_candidate("S00", "SELL", 5, sequence=1),
        _commit_candidate("NEW", "BUY", 1, sequence=2),
    ]
    paths, preview_path = _commit_env(tmp_path, candidates, 11)
    before = paths.execution_log_path.read_bytes()
    with pytest.raises(ManualExecutionCommitError, match="buy_blocked_while_over_cap"):
        commit_manual_execution_preview(
            execution_date=EXECUTION_DATE,
            preview_json_path=preview_path,
            account_paths=paths,
        )
    assert paths.execution_log_path.read_bytes() == before


def test_commit_reinvokes_policy_instead_of_reusing_preview_result(monkeypatch, tmp_path):
    paths, preview_path = _commit_env(tmp_path, [_commit_candidate("NEW", "BUY", 1)], 10)
    calls = 0
    real_validator = commit_module.validate_manual_execution_long_position_actions

    def _counting_validator(*args, **kwargs):
        nonlocal calls
        calls += 1
        return real_validator(*args, **kwargs)

    monkeypatch.setattr(commit_module, "validate_manual_execution_long_position_actions", _counting_validator)
    with pytest.raises(ManualExecutionCommitError, match="independent long-position"):
        commit_manual_execution_preview(execution_date=EXECUTION_DATE, preview_json_path=preview_path, account_paths=paths)
    assert calls == 1


def test_commit_blocks_when_latest_execution_state_changed_after_preview(tmp_path):
    paths, preview_path = _commit_env(tmp_path, [_commit_candidate("NEW", "BUY", 1)], 10)
    payload = json.loads(preview_path.read_text(encoding="utf-8"))
    payload["long_position_policy"] = {"allowed": True, "current_count": 9, "projected_count": 10}
    preview_path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManualExecutionCommitError, match="current=10, projected=11"):
        commit_manual_execution_preview(execution_date=EXECUTION_DATE, preview_json_path=preview_path, account_paths=paths)


def test_commit_blocks_entire_safe_sell_and_forbidden_buy_batch(tmp_path):
    candidates = [
        _commit_candidate("S00", "SELL", 4, sequence=1),
        _commit_candidate("NEW", "BUY", 1, sequence=2),
    ]
    paths, preview_path = _commit_env(tmp_path, candidates, 10)
    before = paths.execution_log_path.read_bytes()
    with pytest.raises(ManualExecutionCommitError, match="max_long_positions_exceeded"):
        commit_manual_execution_preview(execution_date=EXECUTION_DATE, preview_json_path=preview_path, account_paths=paths)
    assert paths.execution_log_path.read_bytes() == before


def test_commit_cap_block_occurs_before_all_persistent_writes(monkeypatch, tmp_path):
    paths, preview_path = _commit_env(tmp_path, [_commit_candidate("NEW", "BUY", 1)], 10)
    writes: list[str] = []
    monkeypatch.setattr(commit_module, "append_paper_execution_log", lambda *args, **kwargs: writes.append("append"))
    monkeypatch.setattr(commit_module, "_create_dev_backups", lambda **kwargs: writes.append("backup"))
    monkeypatch.setattr(commit_module, "save_paper_current_state", lambda *args, **kwargs: writes.append("state"))
    monkeypatch.setattr(commit_module, "save_paper_account_snapshot", lambda *args, **kwargs: writes.append("account"))
    monkeypatch.setattr(commit_module, "save_paper_position_snapshot", lambda *args, **kwargs: writes.append("position"))
    monkeypatch.setattr(commit_module, "_write_commit_sidecar", lambda **kwargs: writes.append("sidecar"))
    with pytest.raises(ManualExecutionCommitError, match="before any write"):
        commit_manual_execution_preview(execution_date=EXECUTION_DATE, preview_json_path=preview_path, account_paths=paths)
    assert writes == []


def test_commit_action_adapter_preserves_actual_price_and_act_shares():
    preview = commit_module._candidate_to_trade_preview(
        _commit_candidate("AAPL", "BUY", 7, price=123.45)
    )
    assert preview.shares == 7
    assert preview.price == 123.45
    assert preview.rec_shares == 7
    assert preview.rec_price == 123.45


def test_non_default_preview_uses_only_requested_account_state(monkeypatch, tmp_path):
    default_holdings = _symbols(10)
    account_paths = build_paper_account_paths(
        "paper_growth",
        account_root=tmp_path / "paper_growth",
        allow_legacy_default=False,
        create=True,
    )
    _write_csv(account_paths.account_snapshot_path, ["snapshot_date", "cash"], [{"snapshot_date": "2026-07-16", "cash": "100000"}])
    _write_csv(account_paths.position_snapshot_path, ["snapshot_date", "symbol", "shares"], [])
    _write_csv(account_paths.execution_log_path, ["trade_id"], [])
    monkeypatch.setattr(importer, "fetch_manual_execution_pages", lambda **kwargs: [])
    candidate = _candidate("NEW", "BUY", 1)
    candidate.account_id = "paper_growth"
    monkeypatch.setattr(importer, "normalize_manual_execution_pages", lambda **kwargs: [candidate])
    monkeypatch.setattr(importer, "paper_position_snapshot_path", lambda: tmp_path / "default.csv")
    _write_csv(tmp_path / "default.csv", ["snapshot_date", "symbol", "shares"], [
        {"snapshot_date": "2026-07-16", "symbol": symbol, "shares": shares}
        for symbol, shares in default_holdings.items()
    ])
    preview = build_manual_execution_preview(
        client=_Client(),
        settings=NotionSettings(enabled=True, token_env="NOTION_TOKEN", data_sources={"manual_executions": "ds"}),
        mapping_root={"manual_executions": {}},
        execution_date=EXECUTION_DATE,
        account_id="paper_growth",
        account_paths=account_paths,
    )
    assert preview.commit_allowed == "true"
    assert preview.long_position_policy["current_count"] == 0
