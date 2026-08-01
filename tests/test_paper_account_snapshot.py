import csv
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.paper_account_snapshot import (
    PAPER_ACCOUNT_SNAPSHOT_COLUMNS,
    build_paper_account_snapshot_row,
    save_paper_account_snapshot,
)
from core.paper_market_valuation import PaperAccountValuation
from core.paper_account_state import build_paper_state_from_trades, create_initial_paper_state


def _make_trade(
    trade_id: str,
    symbol: str,
    side: str,
    shares: int,
    price: float,
) -> dict:
    return {
        "trade_id": trade_id,
        "date": "2026-05-09",
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": price,
        "gross_amount": shares * price,
    }


def _read_rows(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _account_paths(root: Path, account_id: str = "paper_growth") -> SimpleNamespace:
    return SimpleNamespace(account_id=account_id, root=root)


def test_build_paper_account_snapshot_row_calculates_cost_basis_fields():
    state = build_paper_state_from_trades(
        [
            _make_trade("t1", "CPAY", "BUY", 29, 343.99),
            _make_trade("t2", "GEN", "BUY", 440, 22.68),
            _make_trade("t3", "VRSN", "BUY", 34, 288.21),
        ],
        initial_cash=100000.0,
        currency="USD",
    )
    row = build_paper_account_snapshot_row(
        state,
        "20260509",
        initial_cash=100000.0,
        source_execution_log="outputs/paper_test/paper_execution_log.csv",
        source_current_state="outputs/paper_test/paper_current_state_20260509.json",
        created_at="2026-05-11T12:00:00",
    )
    assert row["cash"] == 70245.95
    assert row["positions_cost_value"] == 29754.05
    assert row["total_equity_cost_basis"] == 100000.0
    assert row["cash_ratio_cost_basis"] == 0.7024595
    assert row["position_count"] == 3
    assert row["symbols"] == "CPAY|GEN|VRSN"
    assert row["applied_trade_count"] == 3
    assert row["valuation_method"] == "cost_basis"
    assert row["market_valuation_status"] == "not_run"
    assert row["realized_pnl"] == 0.0
    assert json.loads(row["realized_pnl_by_symbol"]) == {}


def test_build_paper_account_snapshot_row_empty_positions():
    state = create_initial_paper_state()
    row = build_paper_account_snapshot_row(state, "2026-05-09")
    assert row["positions_cost_value"] == 0.0
    assert row["total_equity_cost_basis"] == 100000.0
    assert row["cash_ratio_cost_basis"] == 1.0
    assert row["position_count"] == 0
    assert row["symbols"] == ""


def test_build_paper_account_snapshot_row_with_market_valuation_success():
    state = build_paper_state_from_trades(
        [
            _make_trade("t1", "CPAY", "BUY", 10, 100.0),
            _make_trade("t2", "CPAY", "SELL", -4, 120.0),
        ],
        initial_cash=100000.0,
        currency="USD",
    )
    valuation = PaperAccountValuation(
        snapshot_date="2026-05-09",
        cash=99480.0,
        positions_cost_value=600.0,
        positions_market_value=720.0,
        total_equity_cost_basis=100080.0,
        total_equity_market_value=100200.0,
        cash_ratio_market_value=99480.0 / 100200.0,
        unrealized_pnl=200.0,
        unrealized_pnl_pct=200.0 / 600.0,
        valuation_method="db_daily_price_close",
        valuation_price_date="2026-05-09",
        valuation_price_dates={"CPAY": "2026-05-09"},
        price_staleness_days={"CPAY": 0},
        positions=[],
    )
    row = build_paper_account_snapshot_row(
        state,
        "2026-05-09",
        market_valuation=valuation,
    )
    assert row["realized_pnl"] == 80.0
    assert json.loads(row["realized_pnl_by_symbol"]) == {"CPAY": 80.0}
    assert row["positions_market_value"] == 720.0
    assert row["total_equity_market_value"] == 100200.0
    assert row["market_valuation_status"] == "success"
    assert row["market_valuation_error"] == ""
    assert row["valuation_method"] == "db_daily_price_close"
    assert row["total_pnl"] == 280.0
    assert row["total_pnl_pct"] == 0.0028
    assert json.loads(row["valuation_price_dates"]) == {"CPAY": "2026-05-09"}
    assert json.loads(row["price_staleness_days"]) == {"CPAY": 0}
    assert row["max_price_staleness_days"] == 0


def test_build_paper_account_snapshot_row_with_market_valuation_failure():
    state = build_paper_state_from_trades(
        [
            _make_trade("t1", "CPAY", "BUY", 10, 100.0),
            _make_trade("t2", "CPAY", "SELL", -4, 120.0),
        ],
        initial_cash=100000.0,
        currency="USD",
    )
    row = build_paper_account_snapshot_row(
        state,
        "2026-05-09",
        market_valuation_error="No daily_price close found for CPAY on or before 2026-05-09",
    )
    assert row["positions_cost_value"] == 600.0
    assert row["realized_pnl"] == 80.0
    assert json.loads(row["realized_pnl_by_symbol"]) == {"CPAY": 80.0}
    assert row["market_valuation_status"] == "failed"
    assert "No daily_price close found" in row["market_valuation_error"]
    assert row["positions_market_value"] == ""
    assert row["total_equity_market_value"] == ""
    assert row["total_pnl"] == ""
    assert row["total_pnl_pct"] == ""
    assert row["valuation_method"] == "db_daily_price_close_failed"


def test_save_paper_account_snapshot_replaces_same_date_and_creates_backup(tmp_path):
    root = tmp_path / "paper_growth"
    snapshot_path = root / "paper_account_snapshot.csv"
    archive_dir = root / "archive"
    root.mkdir(parents=True)
    account_paths = _account_paths(root)
    old_row = {column: "" for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS}
    old_row.update(
        {
            "account_id": "paper_growth",
            "snapshot_date": "2026-05-09",
            "currency": "USD",
            "initial_cash": 100000.0,
            "cash": 90000.0,
            "positions_cost_value": 10000.0,
            "total_equity_cost_basis": 100000.0,
            "cash_ratio_cost_basis": 0.9,
            "position_count": 1,
            "symbols": "OLD",
            "applied_trade_count": 1,
            "valuation_method": "cost_basis",
            "source_execution_log": "old_log.csv",
            "source_current_state": "old_state.json",
            "created_at": "2026-05-10T00:00:00",
        }
    )
    with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerows([old_row])

    state = build_paper_state_from_trades(
        [_make_trade("t1", "CPAY", "BUY", 29, 343.99)],
        initial_cash=100000.0,
        currency="USD",
    )
    new_row = build_paper_account_snapshot_row(state, "2026-05-09", account_id="paper_growth")
    result = save_paper_account_snapshot(
        new_row,
        snapshot_path,
        archive_dir,
        now=datetime(2026, 5, 11, 12, 0, 0),
        account_paths=account_paths,
    )
    assert result["replaced"] is True
    assert result["backup_path"] is not None
    assert result["backup_path"].exists()
    rows = _read_rows(snapshot_path)
    assert len(rows) == 1
    assert rows[0]["snapshot_date"] == "2026-05-09"
    assert rows[0]["symbols"] == "CPAY"


def test_build_paper_account_snapshot_row_records_max_price_staleness_days():
    state = build_paper_state_from_trades(
        [
            _make_trade("t1", "CPAY", "BUY", 10, 100.0),
            _make_trade("t2", "GEN", "BUY", 20, 50.0),
        ],
        initial_cash=100000.0,
        currency="USD",
    )
    valuation = PaperAccountValuation(
        snapshot_date="2026-05-09",
        cash=98000.0,
        positions_cost_value=2000.0,
        positions_market_value=2100.0,
        total_equity_cost_basis=100000.0,
        total_equity_market_value=100100.0,
        cash_ratio_market_value=98000.0 / 100100.0,
        unrealized_pnl=100.0,
        unrealized_pnl_pct=0.05,
        valuation_method="db_daily_price_close",
        valuation_price_date="2026-05-07",
        valuation_price_dates={"CPAY": "2026-05-09", "GEN": "2026-05-07"},
        price_staleness_days={"CPAY": 0, "GEN": 2},
        positions=[],
    )
    row = build_paper_account_snapshot_row(
        state,
        "2026-05-09",
        market_valuation=valuation,
    )
    assert row["max_price_staleness_days"] == 2
    assert json.loads(row["price_staleness_days"]) == {"CPAY": 0, "GEN": 2}


def test_save_paper_account_snapshot_keeps_other_dates(tmp_path):
    root = tmp_path / "paper_growth"
    snapshot_path = root / "paper_account_snapshot.csv"
    archive_dir = root / "archive"
    root.mkdir(parents=True)
    account_paths = _account_paths(root)
    row_0508 = {column: "" for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS}
    row_0508.update(
        {
            "account_id": "paper_growth",
            "snapshot_date": "2026-05-08",
            "currency": "USD",
            "initial_cash": 100000.0,
            "cash": 100000.0,
            "positions_cost_value": 0.0,
            "total_equity_cost_basis": 100000.0,
            "cash_ratio_cost_basis": 1.0,
            "position_count": 0,
            "symbols": "",
            "applied_trade_count": 0,
            "valuation_method": "cost_basis",
            "source_execution_log": "",
            "source_current_state": "",
            "created_at": "2026-05-10T00:00:00",
        }
    )
    with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerows([row_0508])

    state = build_paper_state_from_trades(
        [_make_trade("t1", "CPAY", "BUY", 29, 343.99)],
        initial_cash=100000.0,
        currency="USD",
    )
    new_row = build_paper_account_snapshot_row(state, "2026-05-09", account_id="paper_growth")
    result = save_paper_account_snapshot(
        new_row,
        snapshot_path,
        archive_dir,
        account_paths=account_paths,
    )
    assert result["replaced"] is False
    rows = _read_rows(snapshot_path)
    assert [row["snapshot_date"] for row in rows] == ["2026-05-08", "2026-05-09"]


def test_save_paper_account_snapshot_rejects_non_paper_path(tmp_path):
    root = tmp_path / "paper_growth"
    snapshot_path = tmp_path / "outside" / "paper_account_snapshot.csv"
    archive_dir = root / "archive"
    state = create_initial_paper_state()
    row = build_paper_account_snapshot_row(state, "2026-05-09", account_id="paper_growth")
    with pytest.raises(ValueError):
        save_paper_account_snapshot(
            row,
            snapshot_path,
            archive_dir,
            account_paths=_account_paths(root),
        )


def test_save_account_snapshot_backfills_legacy_identity_under_account_root(tmp_path):
    root = tmp_path / "paper_growth"
    snapshot_path = root / "paper_account_snapshot.csv"
    archive_dir = root / "archive"
    root.mkdir(parents=True)
    legacy_fieldnames = [
        column for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS if column != "account_id"
    ]
    legacy_row = {column: "" for column in legacy_fieldnames}
    legacy_row.update(
        {
            "snapshot_date": "2026-05-08",
            "currency": "USD",
            "initial_cash": "100000",
            "cash": "100000",
            "total_equity_cost_basis": "100000",
        }
    )
    with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=legacy_fieldnames)
        writer.writeheader()
        writer.writerow(legacy_row)
    account_paths = SimpleNamespace(account_id="paper_growth", root=root)
    row = build_paper_account_snapshot_row(
        create_initial_paper_state(),
        "2026-05-09",
        account_id="paper_growth",
    )

    result = save_paper_account_snapshot(
        row,
        snapshot_path,
        archive_dir,
        account_paths=account_paths,
    )

    assert result["legacy_backfilled"] is True
    assert result["backup_path"] is not None
    assert {saved["account_id"] for saved in _read_rows(snapshot_path)} == {"paper_growth"}


def test_save_account_snapshot_rejects_mixed_identity_without_mutation(tmp_path):
    root = tmp_path / "paper_growth"
    snapshot_path = root / "paper_account_snapshot.csv"
    archive_dir = root / "archive"
    root.mkdir(parents=True)
    mixed_rows = []
    for account_id, snapshot_date in (
        ("paper_growth", "2026-05-08"),
        ("paper_other", "2026-05-09"),
    ):
        mixed_row = {column: "" for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS}
        mixed_row.update(
            {
                "account_id": account_id,
                "snapshot_date": snapshot_date,
                "initial_cash": "100000",
            }
        )
        mixed_rows.append(mixed_row)
    with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerows(mixed_rows)
    before = snapshot_path.read_bytes()
    row = build_paper_account_snapshot_row(
        create_initial_paper_state(),
        "2026-05-10",
        account_id="paper_growth",
    )

    with pytest.raises(ValueError, match="mixed_account_ids"):
        save_paper_account_snapshot(
            row,
            snapshot_path,
            archive_dir,
            account_paths=SimpleNamespace(account_id="paper_growth", root=root),
        )

    assert snapshot_path.read_bytes() == before
    assert not archive_dir.exists()


def test_save_account_snapshot_rejects_headerless_legacy_file_without_mutation(tmp_path):
    root = tmp_path / "paper_growth"
    snapshot_path = root / "paper_account_snapshot.csv"
    archive_dir = root / "archive"
    root.mkdir(parents=True)
    snapshot_path.write_text("", encoding="utf-8")
    row = build_paper_account_snapshot_row(
        create_initial_paper_state(),
        "2026-05-10",
        account_id="paper_growth",
    )

    with pytest.raises(ValueError, match="missing_header"):
        save_paper_account_snapshot(
            row,
            snapshot_path,
            archive_dir,
            account_paths=_account_paths(root),
        )

    assert snapshot_path.read_bytes() == b""
    assert not archive_dir.exists()


def test_account_snapshot_rejects_unknown_header_without_mutation(tmp_path):
    root = tmp_path / "paper_growth"
    snapshot_path = root / "paper_account_snapshot.csv"
    archive_dir = root / "archive"
    root.mkdir(parents=True)
    fieldnames = [*PAPER_ACCOUNT_SNAPSHOT_COLUMNS, "unknown_legacy_field"]
    existing_row = {column: "" for column in fieldnames}
    existing_row.update(
        {
            "account_id": "paper_growth",
            "snapshot_date": "2026-05-09",
            "unknown_legacy_field": "must-not-be-dropped",
        }
    )
    with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(existing_row)
    before = snapshot_path.read_bytes()
    row = build_paper_account_snapshot_row(
        create_initial_paper_state(),
        "2026-05-10",
        account_id="paper_growth",
    )

    with pytest.raises(ValueError, match="reason=unknown_columns") as exc_info:
        save_paper_account_snapshot(
            row,
            snapshot_path,
            archive_dir,
            account_paths=_account_paths(root),
        )

    assert "unknown_legacy_field" in str(exc_info.value)
    assert snapshot_path.read_bytes() == before
    assert not archive_dir.exists()


def test_account_snapshot_rejects_extra_values_without_mutation(tmp_path):
    root = tmp_path / "paper_growth"
    snapshot_path = root / "paper_account_snapshot.csv"
    archive_dir = root / "archive"
    root.mkdir(parents=True)
    values = ["" for _ in PAPER_ACCOUNT_SNAPSHOT_COLUMNS]
    values[PAPER_ACCOUNT_SNAPSHOT_COLUMNS.index("account_id")] = "paper_growth"
    values[PAPER_ACCOUNT_SNAPSHOT_COLUMNS.index("snapshot_date")] = "2026-05-09"
    snapshot_path.write_text(
        ",".join(PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
        + "\n"
        + ",".join([*values, "unexpected"])
        + "\n",
        encoding="utf-8",
    )
    before = snapshot_path.read_bytes()
    row = build_paper_account_snapshot_row(
        create_initial_paper_state(),
        "2026-05-10",
        account_id="paper_growth",
    )

    with pytest.raises(ValueError, match="reason=extra_columns"):
        save_paper_account_snapshot(
            row,
            snapshot_path,
            archive_dir,
            account_paths=_account_paths(root),
        )

    assert snapshot_path.read_bytes() == before
    assert not archive_dir.exists()


def test_account_snapshot_rejects_missing_required_header_without_mutation(tmp_path):
    root = tmp_path / "paper_growth"
    snapshot_path = root / "paper_account_snapshot.csv"
    archive_dir = root / "archive"
    root.mkdir(parents=True)
    fieldnames = [
        column for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS if column != "currency"
    ]
    existing_row = {column: "" for column in fieldnames}
    existing_row.update(
        {
            "account_id": "paper_growth",
            "snapshot_date": "2026-05-09",
        }
    )
    with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(existing_row)
    before = snapshot_path.read_bytes()
    row = build_paper_account_snapshot_row(
        create_initial_paper_state(),
        "2026-05-10",
        account_id="paper_growth",
    )

    with pytest.raises(ValueError, match="reason=missing_columns") as exc_info:
        save_paper_account_snapshot(
            row,
            snapshot_path,
            archive_dir,
            account_paths=_account_paths(root),
        )

    assert "currency" in str(exc_info.value)
    assert snapshot_path.read_bytes() == before
    assert not archive_dir.exists()


def test_account_snapshot_does_not_migrate_when_account_id_and_other_column_are_missing(tmp_path):
    root = tmp_path / "paper_growth"
    snapshot_path = root / "paper_account_snapshot.csv"
    archive_dir = root / "archive"
    root.mkdir(parents=True)
    fieldnames = [
        column
        for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS
        if column not in {"account_id", "currency"}
    ]
    existing_row = {column: "" for column in fieldnames}
    existing_row["snapshot_date"] = "2026-05-09"
    with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(existing_row)
    before = snapshot_path.read_bytes()
    row = build_paper_account_snapshot_row(
        create_initial_paper_state(),
        "2026-05-10",
        account_id="paper_growth",
    )

    with pytest.raises(ValueError, match="reason=missing_columns") as exc_info:
        save_paper_account_snapshot(
            row,
            snapshot_path,
            archive_dir,
            account_paths=_account_paths(root),
        )

    assert "account_id" in str(exc_info.value)
    assert "currency" in str(exc_info.value)
    assert snapshot_path.read_bytes() == before
    assert not archive_dir.exists()
