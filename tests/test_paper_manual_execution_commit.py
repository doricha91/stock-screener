from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

import core.paper_manual_execution_commit as commit_module
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS, build_paper_trade_id
from core.paper_account_paths import build_paper_account_paths
from core.paper_manual_execution_commit import (
    MANUAL_EXECUTION_REASON,
    MANUAL_EXECUTION_SOURCE,
    ManualExecutionCommitError,
    commit_manual_execution_preview,
)
from core.paper_market_valuation import PaperAccountValuation, PaperPositionValuation
from core.paper_daily_review_scope import sha256_file
from core.paths import OUTPUTS, PAPER_TEST_DIR


def _unique_path(prefix: str, suffix: str) -> Path:
    return PAPER_TEST_DIR / f"{prefix}_{uuid4().hex}{suffix}"


def _unique_output_dir(prefix: str) -> Path:
    return OUTPUTS / prefix / uuid4().hex


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _account_row(*, snapshot_date: str = "2026-05-24", initial_cash: str = "1000.00", cash: str = "1000.00") -> dict:
    return {
        "snapshot_date": snapshot_date,
        "currency": "USD",
        "initial_cash": initial_cash,
        "cash": cash,
        "positions_cost_value": "0.00",
        "total_equity_cost_basis": initial_cash,
        "cash_ratio_cost_basis": "1.0000000",
        "position_count": "0",
        "symbols": "",
        "applied_trade_count": "0",
        "valuation_method": "cost_basis",
        "source_execution_log": "",
        "source_current_state": "",
        "created_at": "2026-05-24T10:00:00",
        "positions_market_value": "",
        "total_equity_market_value": "",
        "cash_ratio_market_value": "",
        "unrealized_pnl": "",
        "unrealized_pnl_pct": "",
        "realized_pnl": "0.00",
        "realized_pnl_by_symbol": "{}",
        "total_pnl": "",
        "total_pnl_pct": "",
        "market_valuation_status": "not_run",
        "market_valuation_error": "",
        "valuation_price_date": "",
        "valuation_price_dates": "",
        "price_staleness_days": "",
        "max_price_staleness_days": "",
    }


def _position_row(*, snapshot_date: str, symbol: str, shares: str, avg_price: str = "10.00") -> dict:
    return {
        "snapshot_date": snapshot_date,
        "symbol": symbol,
        "shares": shares,
        "avg_price": avg_price,
        "cost_value": f"{float(shares) * float(avg_price):.2f}",
        "close_price": avg_price,
        "market_value": f"{float(shares) * float(avg_price):.2f}",
        "unrealized_pnl": "0.00",
        "unrealized_pnl_pct": "0.0000000",
        "realized_pnl": "0.00",
        "total_pnl": "0.00",
        "total_pnl_pct_on_current_cost": "0.0000000",
        "valuation_method": "db_daily_price_close",
        "valuation_price_date": snapshot_date,
        "price_staleness_days": "0",
        "position_status": "OPEN",
        "created_at": "2026-05-24T10:00:00",
    }


def _execution_row(*, date: str, symbol: str, side: str, shares: int, price: float) -> dict:
    row = {
        "date": date,
        "regime": "BULL",
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": price,
        "gross_amount": shares * price,
        "source": "seed",
        "status": "READY_FOR_PAPER_TRADE",
        "reason": "seed",
        "notes": "",
        "rec_shares": abs(shares),
        "rec_price": price,
        "created_at": "2026-05-24T10:00:00",
    }
    row["trade_id"] = build_paper_trade_id(row)
    return {column: row.get(column, "") for column in PAPER_EXECUTION_LOG_COLUMNS}


def _preview_payload(*, date: str, commit_allowed: str, fail_count: int, warning_count: int, candidates: list[dict]) -> dict:
    return {
        "execution_date": date,
        "account_id": "paper_default",
        "candidate_count": len(candidates),
        "pass_count": sum(1 for item in candidates if item["validation_status"] == "PASS"),
        "warning_count": warning_count,
        "fail_count": fail_count,
        "commit_allowed": commit_allowed,
        "source_data_source_id": "ds-manual",
        "json_path": "",
        "markdown_path": "",
        "projected_cash_start": 1000.0,
        "projected_cash_end": 900.0,
        "projected_cash_impact": -100.0,
        "projected_position_impact": {"AAPL": 1},
        "candidates": candidates,
    }


def _v2_evidence(path: Path, rows: list[dict], *, data_date: str = "2026-05-24") -> dict:
    payload = {
        "schema_version": "execution_reconciliation_preview.v2",
        "reconciliation_contract_version": "execution_reconciliation_preview.v2",
        "runner_result": "PASS",
        "account_id": "paper_default",
        "data_date": data_date,
        "trade_date": "2026-05-25",
        "input_finalized": True,
        "planned_count": len(rows),
        "executed_count": sum(row.get("outcome") == "EXECUTED" for row in rows),
        "partial_count": sum(row.get("outcome") == "PARTIAL" for row in rows),
        "not_executed_count": sum(row.get("outcome") == "NOT_EXECUTED" for row in rows),
        "count_invariant_satisfied": True,
        "rows": rows,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return {
        "data_date": data_date,
        "reconciliation_preview_json_path": path,
        "reconciliation_preview_sha256": sha256_file(path),
        "expected_outcome_rows": [row for row in rows if row.get("outcome") in {"EXECUTED", "PARTIAL"}],
    }


def _candidate(*, symbol: str, side: str, quantity: int, actual_price: float, validation_status: str = "PASS", note: str = "", commission: float = 0.0, currency: str = "USD", broker: str | None = "IBKR", page_id: str = "page-1") -> dict:
    issues = []
    if validation_status == "WARNING":
        issues = [{"severity": "WARNING", "code": "missing_broker", "message": "Broker is blank."}]
    return {
        "page_id": page_id,
        "name": f"{symbol} {side}",
        "execution_date": "2026-05-25",
        "plan_date": "2026-05-25",
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "actual_price": actual_price,
        "commission": commission,
        "currency": currency,
        "broker": broker,
        "status": "READY",
        "note": note,
        "linked_daily_plan_key": "daily_plan:2026-05-25",
        "notion_external_key": None,
        "validation_status_raw": None,
        "validation_message_raw": None,
        "import_status_raw": None,
        "imported_at_raw": None,
        "synced_at_raw": None,
        "canonical_key": f"manual_execution:2026-05-25:{symbol}:{side}:01",
        "projected_cash_delta": -(quantity * actual_price + commission) if side == "BUY" else (quantity * actual_price - commission),
        "projected_position_delta": quantity if side == "BUY" else -quantity,
        "validation_issues": issues,
        "validation_status": validation_status,
    }


def _fake_valuation(state, snapshot_date: str, db_path: Path) -> PaperAccountValuation:
    positions = []
    valuation_price_dates: dict[str, str] = {}
    staleness: dict[str, int] = {}
    positions_cost_value = 0.0
    positions_market_value = 0.0
    for symbol, position in sorted(state.positions.items()):
        close_price = position.avg_price
        cost_value = position.shares * position.avg_price
        market_value = position.shares * close_price
        positions_cost_value += cost_value
        positions_market_value += market_value
        positions.append(
            PaperPositionValuation(
                symbol=symbol,
                shares=position.shares,
                avg_price=position.avg_price,
                close_price=close_price,
                market_value=market_value,
                cost_value=cost_value,
                unrealized_pnl=0.0,
                unrealized_pnl_pct=0.0 if cost_value else None,
                valuation_price_date=snapshot_date,
                price_staleness_days=0,
            )
        )
        valuation_price_dates[symbol] = snapshot_date
        staleness[symbol] = 0
    total_equity_cost_basis = float(state.cash) + positions_cost_value
    total_equity_market_value = float(state.cash) + positions_market_value
    return PaperAccountValuation(
        snapshot_date=snapshot_date,
        cash=float(state.cash),
        positions_cost_value=positions_cost_value,
        positions_market_value=positions_market_value,
        total_equity_cost_basis=total_equity_cost_basis,
        total_equity_market_value=total_equity_market_value,
        cash_ratio_market_value=1.0 if total_equity_market_value == 0 else float(state.cash) / total_equity_market_value,
        unrealized_pnl=0.0,
        unrealized_pnl_pct=0.0 if positions_cost_value else None,
        valuation_method="db_daily_price_close",
        valuation_price_date=snapshot_date,
        valuation_price_dates=valuation_price_dates,
        price_staleness_days=staleness,
        positions=positions,
    )


@pytest.fixture
def commit_env(monkeypatch):
    exec_path = _unique_path("paper_execution_log_manual_commit", ".csv")
    account_path = _unique_path("paper_account_snapshot_manual_commit", ".csv")
    position_path = _unique_path("paper_position_snapshot_manual_commit", ".csv")
    current_state_path = _unique_path("paper_current_state_manual_commit", ".json")
    reports_dir = _unique_path("reports_manual_commit", "")
    backup_dir = _unique_output_dir("dev_backups_manual_commit")
    preview_path = _unique_path("manual_execution_preview_manual_commit", ".json")
    current_state_dates: list[str] = []
    reports_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(commit_module, "paper_execution_log_path", lambda: exec_path)
    monkeypatch.setattr(commit_module, "paper_account_snapshot_path", lambda: account_path)
    monkeypatch.setattr(commit_module, "paper_position_snapshot_path", lambda: position_path)
    def _current_state_path(date: str) -> Path:
        current_state_dates.append(date)
        return current_state_path

    monkeypatch.setattr(commit_module, "paper_current_state_snapshot_path", _current_state_path)
    monkeypatch.setattr(commit_module, "paper_reports_dir", lambda: reports_dir)
    monkeypatch.setattr(commit_module, "dev_backups_dir", lambda: backup_dir)
    monkeypatch.setattr(commit_module, "market_db_path", lambda: str(_unique_path("market_db_unused", ".db")))
    monkeypatch.setattr(commit_module, "value_paper_account_state", _fake_valuation)

    _write_csv(exec_path, PAPER_EXECUTION_LOG_COLUMNS, [])
    _write_csv(account_path, list(_account_row().keys()), [_account_row()])
    _write_csv(position_path, list(_position_row(snapshot_date="2026-05-24", symbol="AAPL", shares="0").keys()), [])

    try:
        yield {
            "exec_path": exec_path,
            "account_path": account_path,
            "position_path": position_path,
            "current_state_path": current_state_path,
            "current_state_dates": current_state_dates,
            "reports_dir": reports_dir,
            "backup_dir": backup_dir,
            "preview_path": preview_path,
        }
    finally:
        for path in [preview_path, exec_path, account_path, position_path, current_state_path]:
            if path.exists():
                path.unlink()
        for directory in [reports_dir, backup_dir]:
            if directory.exists():
                shutil.rmtree(directory)


def test_fail_preview_is_rejected(commit_env):
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="false",
        fail_count=1,
        warning_count=0,
        candidates=[_candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0, validation_status="FAIL")],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManualExecutionCommitError, match="FAIL rows"):
        commit_manual_execution_preview(
            execution_date="2026-05-25",
            preview_json_path=commit_env["preview_path"],
        )


def test_warning_preview_requires_allow_warnings(commit_env):
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true_with_warnings",
        fail_count=0,
        warning_count=1,
        candidates=[_candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0, validation_status="WARNING", broker=None)],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManualExecutionCommitError, match="--allow-warnings"):
        commit_manual_execution_preview(
            execution_date="2026-05-25",
            preview_json_path=commit_env["preview_path"],
        )


def test_warning_preview_commits_with_allow_warnings(commit_env):
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true_with_warnings",
        fail_count=0,
        warning_count=1,
        candidates=[_candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0, validation_status="WARNING", broker=None)],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    result = commit_manual_execution_preview(
        execution_date="2026-05-25",
        preview_json_path=commit_env["preview_path"],
        allow_warnings=True,
    )
    assert result.account_id == "paper_default"
    assert result.committed_row_count == 1
    assert result.current_state_written is True
    with commit_env["exec_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["shares"] == "1"
    current_state = json.loads(commit_env["current_state_path"].read_text(encoding="utf-8"))
    assert current_state["absolute_cash"] == 900.0
    assert commit_env["current_state_dates"] == ["2026-05-25"]
    with commit_env["account_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        account_snapshot_rows = list(csv.DictReader(handle))
    with commit_env["position_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        position_snapshot_rows = list(csv.DictReader(handle))
    assert {row["account_id"] for row in account_snapshot_rows} == {"paper_default"}
    assert {row["account_id"] for row in position_snapshot_rows} == {"paper_default"}
    sidecar = json.loads(Path(result.commit_json_path).read_text(encoding="utf-8"))
    assert sidecar["account_id"] == "paper_default"
    assert sidecar["committed_rows"][0]["account_id"] == "paper_default"
    assert sidecar["committed_rows"][0]["commit_status"] == "COMMITTED"
    assert sidecar["committed_rows"][0]["canonical_key"] == "manual_execution:paper_default:2026-05-25:AAPL:BUY:01"
    assert sidecar["committed_rows"][0]["legacy_canonical_key"] == "manual_execution:2026-05-25:AAPL:BUY:01"
    assert sidecar["committed_rows"][0]["legacy_key_compatible"] is True
    assert sidecar["committed_rows"][0]["commission"] == 0.0
    assert sidecar["committed_rows"][0]["currency"] == "USD"
    assert sidecar["committed_rows"][0]["broker"] is None
    assert "paper_current_state" in result.backups


def test_sell_commits_negative_shares(commit_env):
    seed_row = _execution_row(date="2026-05-24", symbol="AAPL", side="BUY", shares=5, price=100.0)
    _write_csv(commit_env["exec_path"], PAPER_EXECUTION_LOG_COLUMNS, [seed_row])
    _write_csv(commit_env["position_path"], list(_position_row(snapshot_date="2026-05-24", symbol="AAPL", shares="5").keys()), [_position_row(snapshot_date="2026-05-24", symbol="AAPL", shares="5")])
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true",
        fail_count=0,
        warning_count=0,
        candidates=[_candidate(symbol="AAPL", side="SELL", quantity=2, actual_price=110.0)],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    result = commit_manual_execution_preview(
        execution_date="2026-05-25",
        preview_json_path=commit_env["preview_path"],
    )
    with commit_env["exec_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert rows[-1]["side"] == "SELL"
    assert rows[-1]["shares"] == "-2"
    assert result.position_snapshot_written is True
    current_state = json.loads(commit_env["current_state_path"].read_text(encoding="utf-8"))
    assert current_state["shares"]["AAPL"] == 3


def test_duplicate_trade_id_blocks_commit(commit_env):
    duplicate_trade_id = build_paper_trade_id(
        {
            "date": "2026-05-25",
            "symbol": "AAPL",
            "side": "BUY",
            "shares": 1,
            "price": 100.0,
            "reason": MANUAL_EXECUTION_REASON,
            "source": MANUAL_EXECUTION_SOURCE,
        }
    )
    existing = {
        "trade_id": duplicate_trade_id,
        "date": "2026-05-25",
        "regime": "MANUAL",
        "symbol": "AAPL",
        "side": "BUY",
        "shares": "1",
        "price": "100.0",
        "gross_amount": "100.0",
        "source": MANUAL_EXECUTION_SOURCE,
        "status": "READY_FOR_PAPER_TRADE",
        "reason": MANUAL_EXECUTION_REASON,
        "notes": "",
        "rec_shares": "1",
        "rec_price": "100.0",
        "created_at": "2026-05-25T10:00:00",
    }
    _write_csv(commit_env["exec_path"], PAPER_EXECUTION_LOG_COLUMNS, [existing])
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true",
        fail_count=0,
        warning_count=0,
        candidates=[_candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0)],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManualExecutionCommitError, match="already exist"):
        commit_manual_execution_preview(
            execution_date="2026-05-25",
            preview_json_path=commit_env["preview_path"],
        )


def test_commit_preserves_execution_log_schema(commit_env):
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true",
        fail_count=0,
        warning_count=0,
        candidates=[_candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0)],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    commit_manual_execution_preview(
        execution_date="2026-05-25",
        preview_json_path=commit_env["preview_path"],
    )
    with commit_env["exec_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == PAPER_EXECUTION_LOG_COLUMNS


def test_commit_succeeds_when_current_state_did_not_preexist(commit_env):
    assert not commit_env["current_state_path"].exists()
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true",
        fail_count=0,
        warning_count=0,
        candidates=[_candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0)],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    result = commit_manual_execution_preview(
        execution_date="2026-05-25",
        preview_json_path=commit_env["preview_path"],
    )
    assert result.backups["paper_current_state"] is None
    assert commit_env["current_state_path"].exists()


def test_existing_current_state_is_backed_up(commit_env):
    commit_env["current_state_path"].write_text(
        json.dumps({"current_symbols": [], "current_cash_ratio": 1.0, "current_hedge_ratio": 0.0, "absolute_cash": 1000.0, "shares": {}, "avg_price": {}, "highest_prices": {}}),
        encoding="utf-8",
    )
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true",
        fail_count=0,
        warning_count=0,
        candidates=[_candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0)],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    result = commit_manual_execution_preview(
        execution_date="2026-05-25",
        preview_json_path=commit_env["preview_path"],
    )
    backup_path = result.backups["paper_current_state"]
    assert backup_path is not None
    assert Path(backup_path).exists()


def test_current_state_save_failure_rolls_back(commit_env, monkeypatch):
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true",
        fail_count=0,
        warning_count=0,
        candidates=[_candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0)],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")

    def _raise_current_state(*args, **kwargs):
        raise RuntimeError("boom_current_state")

    monkeypatch.setattr(commit_module, "save_paper_current_state", _raise_current_state)

    with pytest.raises(ManualExecutionCommitError, match="boom_current_state"):
        commit_manual_execution_preview(
            execution_date="2026-05-25",
            preview_json_path=commit_env["preview_path"],
        )

    with commit_env["exec_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == []
    assert not commit_env["current_state_path"].exists()


def test_v2_outcome_filter_commits_only_trade_bearing_candidate(commit_env):
    aapl = _candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0)
    msft = _candidate(symbol="MSFT", side="BUY", quantity=1, actual_price=200.0)
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true",
        fail_count=0,
        warning_count=0,
        candidates=[aapl, msft],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    outcome_rows = [
        {
            "candidate_key": aapl["canonical_key"],
            "symbol": "AAPL",
            "side": "BUY",
            "actual_quantity": 1,
            "actual_price": 100.0,
            "outcome": "EXECUTED",
        },
        {
            "candidate_key": msft["canonical_key"],
            "symbol": "MSFT",
            "side": "BUY",
            "actual_quantity": None,
            "actual_price": None,
            "outcome": "NOT_EXECUTED",
        },
    ]
    evidence = _v2_evidence(commit_env["preview_path"].with_name("reconciliation.json"), outcome_rows)

    result = commit_manual_execution_preview(
        execution_date="2026-05-25",
        preview_json_path=commit_env["preview_path"],
        eligible_candidate_keys={aapl["canonical_key"]},
        **evidence,
    )

    assert result.committed_row_count == 1
    with commit_env["exec_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["symbol"] for row in rows] == ["AAPL"]
    snapshots_before = {
        path: path.read_bytes()
        for path in (
            commit_env["exec_path"],
            commit_env["account_path"],
            commit_env["position_path"],
            commit_env["current_state_path"],
        )
    }
    with pytest.raises(ManualExecutionCommitError, match="already exist"):
        commit_manual_execution_preview(
            execution_date="2026-05-25",
            preview_json_path=commit_env["preview_path"],
            eligible_candidate_keys={aapl["canonical_key"]},
            **evidence,
        )
    assert {path: path.read_bytes() for path in snapshots_before} == snapshots_before


def test_v2_filtered_commit_blocks_stale_input_preview_before_write(commit_env):
    candidate = _candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0)
    payload = _preview_payload(
        date="2026-05-25", commit_allowed="true", fail_count=0, warning_count=0,
        candidates=[candidate],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    outcome_rows = [
        {
            "candidate_key": candidate["canonical_key"],
            "symbol": "AAPL",
            "side": "BUY",
            "actual_quantity": 1,
            "actual_price": 101.0,
            "outcome": "EXECUTED",
        }
    ]
    evidence = _v2_evidence(commit_env["preview_path"].with_name("reconciliation.json"), outcome_rows)

    with pytest.raises(ManualExecutionCommitError, match="does not match"):
        commit_manual_execution_preview(
            execution_date="2026-05-25",
            preview_json_path=commit_env["preview_path"],
            eligible_candidate_keys={candidate["canonical_key"]},
            **evidence,
        )

    with commit_env["exec_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        assert list(csv.DictReader(handle)) == []


def test_v2_commit_blocks_tampered_reconciliation_digest_before_domain_write(commit_env):
    candidate = _candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0)
    payload = _preview_payload(
        date="2026-05-25", commit_allowed="true", fail_count=0, warning_count=0,
        candidates=[candidate],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    outcome_rows = [
        {
            "candidate_key": candidate["canonical_key"],
            "symbol": "AAPL",
            "side": "BUY",
            "actual_quantity": 1,
            "actual_price": 100.0,
            "outcome": "EXECUTED",
        }
    ]
    evidence = _v2_evidence(commit_env["preview_path"].with_name("reconciliation.json"), outcome_rows)
    evidence["reconciliation_preview_json_path"].write_text("{}", encoding="utf-8")

    with pytest.raises(ManualExecutionCommitError, match="SHA-256 mismatch"):
        commit_manual_execution_preview(
            execution_date="2026-05-25",
            preview_json_path=commit_env["preview_path"],
            eligible_candidate_keys={candidate["canonical_key"]},
            **evidence,
        )

    with commit_env["exec_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        assert list(csv.DictReader(handle)) == []
    assert not commit_env["current_state_path"].exists()


def test_v2_filtered_commit_revalidates_latest_ledger_hard_cap(commit_env):
    existing = _execution_row(
        date="2026-05-24", symbol="AAPL", side="BUY", shares=1, price=100.0
    )
    _write_csv(commit_env["exec_path"], PAPER_EXECUTION_LOG_COLUMNS, [existing])
    candidate = _candidate(symbol="MSFT", side="BUY", quantity=1, actual_price=200.0)
    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true",
        fail_count=0,
        warning_count=0,
        candidates=[candidate],
    )
    commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    outcome_rows = [
        {
            "candidate_key": candidate["canonical_key"],
            "symbol": "MSFT",
            "side": "BUY",
            "actual_quantity": 1,
            "actual_price": 200.0,
            "outcome": "EXECUTED",
        }
    ]
    evidence = _v2_evidence(commit_env["preview_path"].with_name("reconciliation.json"), outcome_rows)

    with pytest.raises(ManualExecutionCommitError, match="hard-cap"):
        commit_manual_execution_preview(
            execution_date="2026-05-25",
            preview_json_path=commit_env["preview_path"],
            eligible_candidate_keys={candidate["canonical_key"]},
            max_long_positions=1,
            **evidence,
        )

    with commit_env["exec_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["symbol"] for row in rows] == ["AAPL"]


def test_non_default_preview_commit_writes_under_account_root(tmp_path, monkeypatch):
    account_root = tmp_path / "paper_accounts" / "paper_growth"
    account_paths = build_paper_account_paths(
        "paper_growth",
        account_root=account_root,
        allow_legacy_default=False,
        create=True,
    )
    monkeypatch.setattr(commit_module, "market_db_path", lambda: str(tmp_path / "unused_market.db"))
    monkeypatch.setattr(commit_module, "value_paper_account_state", _fake_valuation)

    preview_path = tmp_path / "manual_execution_preview_non_default.json"
    _write_csv(account_paths.execution_log_path, PAPER_EXECUTION_LOG_COLUMNS, [])
    _write_csv(account_paths.account_snapshot_path, list(_account_row().keys()), [_account_row()])
    _write_csv(account_paths.position_snapshot_path, list(_position_row(snapshot_date="2026-05-24", symbol="AAPL", shares="0").keys()), [])

    payload = _preview_payload(
        date="2026-05-25",
        commit_allowed="true",
        fail_count=0,
        warning_count=0,
        candidates=[_candidate(symbol="AAPL", side="BUY", quantity=1, actual_price=100.0)],
    )
    payload["account_id"] = "paper_growth"
    payload["candidates"][0]["account_id"] = "paper_growth"
    payload["candidates"][0]["canonical_key"] = "manual_execution:paper_growth:2026-05-25:AAPL:BUY:01"
    preview_path.write_text(json.dumps(payload), encoding="utf-8")

    result = commit_manual_execution_preview(
        execution_date="2026-05-25",
        preview_json_path=preview_path,
        account_paths=account_paths,
    )

    assert result.account_id == "paper_growth"
    assert result.committed_row_count > 0
    expected_paths = [
        account_paths.execution_log_path,
        account_paths.account_snapshot_path,
        account_paths.position_snapshot_path,
        account_paths.current_state_snapshot_path("20260525"),
    ]
    assert all(path.exists() for path in expected_paths)
    assert all(path.resolve().is_relative_to(account_paths.root.resolve()) for path in expected_paths)

    with account_paths.account_snapshot_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        account_snapshot_rows = list(csv.DictReader(handle))
    with account_paths.position_snapshot_path.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        position_snapshot_rows = list(csv.DictReader(handle))
    assert {row["account_id"] for row in account_snapshot_rows} == {"paper_growth"}
    assert position_snapshot_rows
    assert {row["account_id"] for row in position_snapshot_rows} == {"paper_growth"}

    sidecar = json.loads(Path(result.commit_json_path).read_text(encoding="utf-8"))
    row = sidecar["committed_rows"][0]
    assert row["account_id"] == "paper_growth"
    assert row["canonical_key"] == "manual_execution:paper_growth:2026-05-25:AAPL:BUY:01"
    assert row["legacy_canonical_key"] is None
    assert row["legacy_key_compatible"] is False
    assert Path(result.commit_json_path).is_relative_to(account_paths.reports_dir.resolve())
    assert account_paths.execution_log_path.exists()
    assert account_paths.current_state_snapshot_path("20260525").exists()
