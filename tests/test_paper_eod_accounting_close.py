from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from core.paper_account_paths import PaperAccountPaths
from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_market_valuation import PaperAccountValuation, PaperPositionValuation
from scripts import run_paper_eod_update


def _account_paths(root: Path, account_id: str = "paper_eod_accounting") -> PaperAccountPaths:
    return PaperAccountPaths(
        account_id=account_id,
        root=root,
        legacy_default_used=False,
        execution_log_path=root / "paper_execution_log.csv",
        account_snapshot_path=root / "paper_account_snapshot.csv",
        position_snapshot_path=root / "paper_position_snapshot.csv",
        reports_dir=root / "reports",
        reviews_dir=root / "reviews",
        config_snapshots_dir=root / "config_snapshots",
        config_snapshot_archive_dir=root / "archive" / "config_snapshots",
        replay_diff_dir=root / "replay_diff",
        replay_diff_config_snapshot_archive_dir=root / "replay_diff" / "archive" / "config_snapshots",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _plan_markdown(date: str = "2026-06-15") -> str:
    return (
        "# Daily Plan\n\n"
        "## 5. Execution Journal\n\n"
        "| Date | Regime | Symbol | Type | Rec_Shares | Rec_Price | Act_Shares | Act_Price | Reason | Notes |\n"
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"
        f"| {date} | normal | AAPL | BUY | 10 | 100 | [ ] | [ ] | rebalance | |\n"
        f"| {date} | normal | MSFT | SELL | 5 | 110 | [ ] | [ ] | rebalance | |\n"
    )


def _write_plan(paths: PaperAccountPaths, *, items: list[dict[str, object]], date: str = "20260615") -> None:
    _write_text(paths.daily_action_plan_path(date), _plan_markdown("2026-06-15"))
    _write_text(
        paths.daily_action_plan_path(date).with_suffix(".json"),
        json.dumps({"items": items}, ensure_ascii=False, indent=2),
    )


def _seed_snapshots(paths: PaperAccountPaths) -> None:
    _write_text(paths.current_state_snapshot_path("2026-06-14"), "{}\n")
    _write_text(
        paths.account_snapshot_path,
        "snapshot_date,currency,initial_cash,cash,positions_cost_value,total_equity_cost_basis,"
        "cash_ratio_cost_basis,position_count,symbols,applied_trade_count,valuation_method,"
        "source_execution_log,source_current_state,created_at,positions_market_value,"
        "total_equity_market_value,cash_ratio_market_value,unrealized_pnl,unrealized_pnl_pct,"
        "realized_pnl,realized_pnl_by_symbol,total_pnl,total_pnl_pct,market_valuation_status,"
        "market_valuation_error,valuation_price_date,valuation_price_dates,price_staleness_days,"
        "max_price_staleness_days\n"
        "2026-06-14,USD,100000.00,100000.00,0.00,100000.00,1.0000000,0,,0,"
        "db_daily_price_close,,,,0.00,100000.00,1.0000000,0.00,0.0000000,0.00,{},0.00,"
        "0.0000000,success,,2026-06-14,{}, {},0\n",
    )
    _write_text(
        paths.position_snapshot_path,
        "snapshot_date,symbol,shares,avg_price,cost_value,close_price,market_value,unrealized_pnl,"
        "unrealized_pnl_pct,realized_pnl,total_pnl,total_pnl_pct_on_current_cost,valuation_method,"
        "valuation_price_date,price_staleness_days,position_status,created_at\n",
    )


def _trade_row(
    *,
    trade_id: str,
    date: str,
    symbol: str,
    side: str,
    shares: int,
    price: float,
    source: str = "notion_manual_execution",
) -> dict[str, object]:
    return {
        "trade_id": trade_id,
        "date": date,
        "regime": "normal",
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": price,
        "gross_amount": abs(shares) * price,
        "source": source,
        "status": "COMMITTED",
        "reason": "manual execution",
        "notes": "",
        "rec_shares": abs(shares),
        "rec_price": price,
        "created_at": f"{date}T16:00:00",
    }


def _fake_valuation(state, snapshot_date: str, db_path: Path) -> PaperAccountValuation:
    positions = []
    positions_cost_value = 0.0
    positions_market_value = 0.0
    valuation_price_dates = {}
    price_staleness_days = {}
    for symbol, position in sorted(state.positions.items()):
        close_price = float(position.avg_price) + 1.0
        cost_value = float(position.shares) * float(position.avg_price)
        market_value = float(position.shares) * close_price
        positions_cost_value += cost_value
        positions_market_value += market_value
        valuation_price_dates[symbol] = snapshot_date
        price_staleness_days[symbol] = 0
        positions.append(
            PaperPositionValuation(
                symbol=symbol,
                shares=position.shares,
                avg_price=position.avg_price,
                close_price=close_price,
                market_value=market_value,
                cost_value=cost_value,
                unrealized_pnl=market_value - cost_value,
                unrealized_pnl_pct=(market_value - cost_value) / cost_value if cost_value else 0.0,
                valuation_price_date=snapshot_date,
                price_staleness_days=0,
            )
        )
    total_equity_market = float(state.cash) + positions_market_value
    total_equity_cost = float(state.cash) + positions_cost_value
    return PaperAccountValuation(
        snapshot_date=snapshot_date,
        cash=float(state.cash),
        positions_cost_value=positions_cost_value,
        positions_market_value=positions_market_value,
        total_equity_cost_basis=total_equity_cost,
        total_equity_market_value=total_equity_market,
        cash_ratio_market_value=float(state.cash) / total_equity_market if total_equity_market else 0.0,
        unrealized_pnl=positions_market_value - positions_cost_value,
        unrealized_pnl_pct=(positions_market_value - positions_cost_value) / positions_cost_value
        if positions_cost_value
        else 0.0,
        valuation_method="fixture_close",
        valuation_price_date=snapshot_date,
        valuation_price_dates=valuation_price_dates,
        price_staleness_days=price_staleness_days,
        positions=positions,
    )


def _seed_account(paths: PaperAccountPaths, *, plan_items: list[dict[str, object]], trades: list[dict[str, object]]) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.reports_dir.mkdir(parents=True, exist_ok=True)
    _write_plan(paths, items=plan_items)
    _seed_snapshots(paths)
    _write_csv(paths.execution_log_path, PAPER_EXECUTION_LOG_COLUMNS, trades)


def test_eod_accounting_close_uses_existing_manual_execution_rows_without_virtual_fill(
    tmp_path,
    monkeypatch,
    capsys,
):
    paths = _account_paths(tmp_path / "paper_accounts" / "paper_eod_accounting")
    plan_items = [
        {"action": "BUY", "symbol": "AAPL", "quantity": 10},
        {"action": "BUY", "symbol": "MSFT", "quantity": 2},
    ]
    trades = [
        _trade_row(trade_id="manual-aapl", date="2026-06-15", symbol="AAPL", side="BUY", shares=10, price=100),
        _trade_row(trade_id="manual-msft", date="2026-06-15", symbol="MSFT", side="BUY", shares=2, price=200),
    ]
    _seed_account(paths, plan_items=plan_items, trades=trades)
    _write_text(paths.reports_dir / "manual_execution_import_commit_20260615.json", '{"committed_rows": 2}\n')
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)

    before_rows = _read_csv(paths.execution_log_path)
    exit_code = run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    )
    output = capsys.readouterr().out
    after_rows = _read_csv(paths.execution_log_path)

    assert exit_code == 0
    assert len(after_rows) == len(before_rows)
    assert not [row for row in after_rows if row["source"] == "paper_virtual_fill"]
    assert "eod_mode: accounting_close" in output
    assert "execution_candidate_count: 2" in output
    assert "execution_log_rows_for_date: 2" in output
    assert "manual_execution_commit_report_exists: true" in output
    assert "would_append_execution_log: false" in output
    assert "rows_appended: 0" in output
    assert paths.current_state_snapshot_path("2026-06-15").exists()
    assert any(row["snapshot_date"] == "2026-06-15" for row in _read_csv(paths.account_snapshot_path))
    assert any(row["snapshot_date"] == "2026-06-15" for row in _read_csv(paths.position_snapshot_path))


def test_eod_blocks_when_candidates_exist_without_committed_rows_or_commit_report(tmp_path, monkeypatch, capsys):
    paths = _account_paths(tmp_path / "paper_accounts" / "paper_eod_block")
    _seed_account(
        paths,
        plan_items=[{"action": "BUY", "symbol": "AAPL", "quantity": 10}],
        trades=[],
    )
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)

    before_rows = _read_csv(paths.execution_log_path)
    exit_code = run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert _read_csv(paths.execution_log_path) == before_rows
    assert not paths.current_state_snapshot_path("2026-06-15").exists()
    assert not any(row["snapshot_date"] == "2026-06-15" for row in _read_csv(paths.account_snapshot_path))
    assert "execution candidates exist but no committed execution rows were found" in output
    assert "Run Manual Execution commit first" in output


def test_eod_blocks_commit_report_without_committed_rows(tmp_path, monkeypatch, capsys):
    paths = _account_paths(tmp_path / "paper_accounts" / "paper_eod_mismatch")
    _seed_account(
        paths,
        plan_items=[{"action": "BUY", "symbol": "AAPL", "quantity": 10}],
        trades=[],
    )
    _write_text(paths.reports_dir / "manual_execution_import_commit_20260615.json", '{"committed_rows": 1}\n')
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)

    exit_code = run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    )
    output = capsys.readouterr().out

    assert exit_code == 1
    assert not paths.current_state_snapshot_path("2026-06-15").exists()
    assert "manual execution commit report exists but no committed execution rows were found" in output
    assert not [row for row in _read_csv(paths.execution_log_path) if row["source"] == "paper_virtual_fill"]


def test_eod_no_action_accounting_close_rolls_forward_without_execution_append(tmp_path, monkeypatch, capsys):
    paths = _account_paths(tmp_path / "paper_accounts" / "paper_eod_no_action")
    _seed_account(
        paths,
        plan_items=[],
        trades=[
            _trade_row(
                trade_id="previous-aapl",
                date="2026-06-14",
                symbol="AAPL",
                side="BUY",
                shares=10,
                price=100,
                source="fixture",
            )
        ],
    )
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)

    before_rows = _read_csv(paths.execution_log_path)
    exit_code = run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert _read_csv(paths.execution_log_path) == before_rows
    assert "no_action_day: true" in output
    assert "would_append_execution_log: false" in output
    assert paths.current_state_snapshot_path("2026-06-15").exists()
    assert any(row["snapshot_date"] == "2026-06-15" for row in _read_csv(paths.account_snapshot_path))


def test_eod_account_preview_failure_leaves_execution_log_and_snapshots_unchanged(
    tmp_path,
    monkeypatch,
):
    paths = _account_paths(tmp_path / "paper_accounts" / "paper_eod_preview_fail")
    _seed_account(
        paths,
        plan_items=[{"action": "SELL", "symbol": "AAPL", "quantity": 10}],
        trades=[
            _trade_row(
                trade_id="invalid-sell",
                date="2026-06-15",
                symbol="AAPL",
                side="SELL",
                shares=-10,
                price=100,
                source="notion_manual_execution",
            )
        ],
    )
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)

    before_rows = _read_csv(paths.execution_log_path)
    exit_code = run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    )

    assert exit_code == 1
    assert _read_csv(paths.execution_log_path) == before_rows
    assert not paths.current_state_snapshot_path("2026-06-15").exists()
    assert not any(row["snapshot_date"] == "2026-06-15" for row in _read_csv(paths.account_snapshot_path))
    assert not any(row["snapshot_date"] == "2026-06-15" for row in _read_csv(paths.position_snapshot_path))


def test_eod_dry_run_and_commit_both_report_no_execution_log_append(tmp_path, monkeypatch, capsys):
    paths = _account_paths(tmp_path / "paper_accounts" / "paper_eod_intent")
    _seed_account(
        paths,
        plan_items=[{"action": "BUY", "symbol": "AAPL", "quantity": 10}],
        trades=[
            _trade_row(
                trade_id="manual-aapl",
                date="2026-06-15",
                symbol="AAPL",
                side="BUY",
                shares=10,
                price=100,
            )
        ],
    )
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)

    assert run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=False,
        account_paths=paths,
    ) == 0
    dry_run_output = capsys.readouterr().out
    before_rows = _read_csv(paths.execution_log_path)
    assert run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    ) == 0
    commit_output = capsys.readouterr().out

    assert "would_append_execution_log: false" in dry_run_output
    assert "rows_to_append: 0" in dry_run_output
    assert "would_append_execution_log: false" in commit_output
    assert "rows_appended: 0" in commit_output
    assert _read_csv(paths.execution_log_path) == before_rows


def test_eod_empty_no_action_account_writes_cash_only_snapshots(tmp_path, monkeypatch, capsys):
    paths = _account_paths(tmp_path / "paper_accounts" / "paper_eod_empty_no_action")
    _seed_account(paths, plan_items=[], trades=[])
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)

    assert run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=False,
        account_paths=paths,
    ) == 0
    dry_run_output = capsys.readouterr().out
    assert "execution_candidate_count: 0" in dry_run_output
    assert "would_write_position_snapshot: true" in dry_run_output

    assert run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    ) == 0
    commit_output = capsys.readouterr().out

    assert "rows_appended: 0" in commit_output
    assert paths.current_state_snapshot_path("2026-06-15").exists()
    account_rows = _read_csv(paths.account_snapshot_path)
    assert any(
        row["snapshot_date"] == "2026-06-15" and row["position_count"] == "0"
        for row in account_rows
    )
    assert _read_csv(paths.position_snapshot_path) == []


def test_eod_no_action_account_values_existing_position(tmp_path, monkeypatch, capsys):
    paths = _account_paths(tmp_path / "paper_accounts" / "paper_eod_held_no_action")
    _seed_account(
        paths,
        plan_items=[],
        trades=[
            _trade_row(
                trade_id="prior-aapl",
                date="2026-06-14",
                symbol="AAPL",
                side="BUY",
                shares=10,
                price=100,
            )
        ],
    )
    monkeypatch.setattr(run_paper_eod_update, "value_paper_account_state", _fake_valuation)

    assert run_paper_eod_update.run_paper_eod_dry_run(
        "2026-06-15",
        allow_empty_journal=True,
        commit=True,
        account_paths=paths,
    ) == 0
    output = capsys.readouterr().out

    assert "execution_candidate_count: 0" in output
    assert "execution_log_rows_for_date: 0" in output
    assert "rows_appended: 0" in output
    position_rows = _read_csv(paths.position_snapshot_path)
    assert any(
        row["snapshot_date"] == "2026-06-15"
        and row["symbol"] == "AAPL"
        and row["shares"] == "10"
        for row in position_rows
    )


def test_eod_market_db_error_fail_stops_without_writing_snapshots(
    tmp_path,
    monkeypatch,
    capsys,
):
    paths = _account_paths(tmp_path / "paper_accounts" / "paper_eod_market_db_fail")
    _seed_account(
        paths,
        plan_items=[],
        trades=[
            _trade_row(
                trade_id="previous-aapl",
                date="2026-06-14",
                symbol="AAPL",
                side="BUY",
                shares=10,
                price=100,
                source="fixture",
            )
        ],
    )
    broken_db = tmp_path / "broken_market.db"
    sqlite3.connect(broken_db).close()
    monkeypatch.setattr(run_paper_eod_update, "market_db_path", lambda: broken_db)

    before_execution = paths.execution_log_path.read_bytes()
    before_account = paths.account_snapshot_path.read_bytes()
    before_position = paths.position_snapshot_path.read_bytes()

    for commit in (False, True):
        exit_code = run_paper_eod_update.run_paper_eod_dry_run(
            "2026-06-15",
            allow_empty_journal=True,
            commit=commit,
            account_paths=paths,
        )
        output = capsys.readouterr().out

        assert exit_code == 1
        assert "paper_high_watermark_market_db_error" in output
        assert not paths.current_state_snapshot_path("2026-06-15").exists()
        assert paths.execution_log_path.read_bytes() == before_execution
        assert paths.account_snapshot_path.read_bytes() == before_account
        assert paths.position_snapshot_path.read_bytes() == before_position
