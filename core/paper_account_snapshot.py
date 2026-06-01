from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_guard import assert_non_default_writer_target
from core.paper_account_state import PaperAccountState
from core.paper_market_valuation import PaperAccountValuation
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


PAPER_ACCOUNT_SNAPSHOT_COLUMNS = [
    "snapshot_date",
    "currency",
    "initial_cash",
    "cash",
    "positions_cost_value",
    "total_equity_cost_basis",
    "cash_ratio_cost_basis",
    "position_count",
    "symbols",
    "applied_trade_count",
    "valuation_method",
    "source_execution_log",
    "source_current_state",
    "created_at",
    "positions_market_value",
    "total_equity_market_value",
    "cash_ratio_market_value",
    "unrealized_pnl",
    "unrealized_pnl_pct",
    "realized_pnl",
    "realized_pnl_by_symbol",
    "total_pnl",
    "total_pnl_pct",
    "market_valuation_status",
    "market_valuation_error",
    "valuation_price_date",
    "valuation_price_dates",
    "price_staleness_days",
    "max_price_staleness_days",
]

SNAPSHOT_MONEY_FIELDS = {
    "initial_cash",
    "cash",
    "positions_cost_value",
    "total_equity_cost_basis",
    "positions_market_value",
    "total_equity_market_value",
    "unrealized_pnl",
    "realized_pnl",
    "total_pnl",
}


def _normalize_snapshot_date(snapshot_date: str) -> str:
    clean_date = snapshot_date.replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid snapshot_date format: {snapshot_date}")
    return datetime.strptime(clean_date, "%Y%m%d").strftime("%Y-%m-%d")


def build_paper_account_snapshot_backup_path(
    snapshot_path: Path,
    archive_dir: Path,
    now: datetime | None = None,
) -> Path:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return archive_dir / f"{snapshot_path.stem}_{timestamp}_backup{snapshot_path.suffix}"


def build_paper_account_snapshot_row(
    state: PaperAccountState,
    snapshot_date: str,
    initial_cash: float = 100000.0,
    source_execution_log: str | None = None,
    source_current_state: str | None = None,
    market_valuation: PaperAccountValuation | None = None,
    market_valuation_error: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    normalized_date = _normalize_snapshot_date(snapshot_date)
    positions_cost_value_raw = sum(
        position.shares * position.avg_price for position in state.positions.values()
    )
    cash = round(float(state.cash), 2)
    positions_cost_value = round(float(positions_cost_value_raw), 2)
    total_equity_cost_basis = round(cash + positions_cost_value, 2)
    if total_equity_cost_basis <= 0:
        raise ValueError("total_equity_cost_basis must be > 0")

    symbols = sorted(state.positions.keys())
    row = {
        "snapshot_date": normalized_date,
        "currency": state.currency,
        "initial_cash": round(float(initial_cash), 2),
        "cash": cash,
        "positions_cost_value": positions_cost_value,
        "total_equity_cost_basis": total_equity_cost_basis,
        "cash_ratio_cost_basis": cash / total_equity_cost_basis,
        "position_count": len(symbols),
        "symbols": "|".join(symbols),
        "applied_trade_count": len(state.applied_trade_ids),
        "valuation_method": "cost_basis",
        "source_execution_log": source_execution_log or "",
        "source_current_state": source_current_state or "",
        "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
        "positions_market_value": "",
        "total_equity_market_value": "",
        "cash_ratio_market_value": "",
        "unrealized_pnl": "",
        "unrealized_pnl_pct": "",
        "realized_pnl": round(float(state.realized_pnl), 2),
        "realized_pnl_by_symbol": json.dumps(
            {symbol: round(float(pnl), 2) for symbol, pnl in sorted(state.realized_pnl_by_symbol.items())},
            ensure_ascii=False,
            sort_keys=True,
        ),
        "total_pnl": "",
        "total_pnl_pct": "",
        "market_valuation_status": "not_run",
        "market_valuation_error": "",
        "valuation_price_date": "",
        "valuation_price_dates": "",
        "price_staleness_days": "",
        "max_price_staleness_days": "",
    }

    if market_valuation is not None:
        max_staleness = max(market_valuation.price_staleness_days.values(), default=0)
        total_pnl = float(state.realized_pnl) + float(market_valuation.unrealized_pnl)
        row.update(
            {
                "positions_market_value": round(float(market_valuation.positions_market_value), 2),
                "total_equity_market_value": round(float(market_valuation.total_equity_market_value), 2),
                "cash_ratio_market_value": market_valuation.cash_ratio_market_value,
                "unrealized_pnl": round(float(market_valuation.unrealized_pnl), 2),
                "unrealized_pnl_pct": market_valuation.unrealized_pnl_pct,
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": total_pnl / float(initial_cash),
                "market_valuation_status": "success",
                "market_valuation_error": "",
                "valuation_method": market_valuation.valuation_method,
                "valuation_price_date": market_valuation.valuation_price_date,
                "valuation_price_dates": json.dumps(
                    market_valuation.valuation_price_dates,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "price_staleness_days": json.dumps(
                    market_valuation.price_staleness_days,
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                "max_price_staleness_days": max_staleness,
            }
        )
    elif market_valuation_error:
        row.update(
            {
                "market_valuation_status": "failed",
                "market_valuation_error": market_valuation_error,
                "valuation_method": "db_daily_price_close_failed",
            }
        )

    return {column: row[column] for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS}


def save_paper_account_snapshot(
    snapshot_row: dict[str, Any],
    snapshot_path: Path,
    archive_dir: Path,
    now: datetime | None = None,
    account_paths=None,
) -> dict[str, Any]:
    if account_paths is None:
        assert_paper_path(snapshot_path, PAPER_TEST_DIR)
        assert_paper_path(archive_dir, PAPER_TEST_DIR)
    elif account_paths.account_id != "paper_default":
        assert_non_default_writer_target(
            snapshot_path,
            account_id=account_paths.account_id,
            account_root=account_paths.root,
        )
        assert_non_default_writer_target(
            archive_dir,
            account_id=account_paths.account_id,
            account_root=account_paths.root,
        )
    else:
        assert_paper_path(snapshot_path, PAPER_TEST_DIR)
        assert_paper_path(archive_dir, PAPER_TEST_DIR)

    snapshot_date = str(snapshot_row.get("snapshot_date", "")).strip()
    if not snapshot_date:
        raise ValueError("snapshot_row must include snapshot_date")

    existing_rows: list[dict[str, Any]] = []
    backup_path: Path | None = None
    replaced = False

    if snapshot_path.exists():
        with snapshot_path.open("r", encoding="utf-8-sig", newline="") as handle:
            existing_rows = list(csv.DictReader(handle))
        if any(str(row.get("snapshot_date", "")).strip() == snapshot_date for row in existing_rows):
            archive_dir.mkdir(parents=True, exist_ok=True)
            backup_path = build_paper_account_snapshot_backup_path(snapshot_path, archive_dir, now=now)
            if account_paths is None or account_paths.account_id == "paper_default":
                assert_paper_path(backup_path, PAPER_TEST_DIR)
            else:
                assert_non_default_writer_target(
                    backup_path,
                    account_id=account_paths.account_id,
                    account_root=account_paths.root,
                )
            shutil.copy2(snapshot_path, backup_path)
            replaced = True

    kept_rows = [
        row for row in existing_rows
        if str(row.get("snapshot_date", "")).strip() != snapshot_date
    ]
    serialized_row: dict[str, Any] = {}
    for column in PAPER_ACCOUNT_SNAPSHOT_COLUMNS:
        value = snapshot_row.get(column, "")
        if column in SNAPSHOT_MONEY_FIELDS and value != "":
            serialized_row[column] = f"{float(value):.2f}"
        elif column in {
            "cash_ratio_cost_basis",
            "cash_ratio_market_value",
            "unrealized_pnl_pct",
            "total_pnl_pct",
        } and value != "":
            serialized_row[column] = f"{float(value):.7f}"
        else:
            serialized_row[column] = value

    kept_rows.append(serialized_row)
    kept_rows.sort(key=lambda row: str(row.get("snapshot_date", "")).strip())

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerows(kept_rows)

    return {
        "path": snapshot_path,
        "backup_path": backup_path,
        "row_count": len(kept_rows),
        "replaced": replaced,
        "snapshot_row": snapshot_row,
    }
