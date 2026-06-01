from __future__ import annotations

import csv
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_guard import assert_non_default_writer_target
from core.paper_account_state import PaperAccountState
from core.paper_market_valuation import PaperAccountValuation
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


PAPER_POSITION_SNAPSHOT_COLUMNS = [
    "snapshot_date",
    "symbol",
    "shares",
    "avg_price",
    "cost_value",
    "close_price",
    "market_value",
    "unrealized_pnl",
    "unrealized_pnl_pct",
    "realized_pnl",
    "total_pnl",
    "total_pnl_pct_on_current_cost",
    "valuation_method",
    "valuation_price_date",
    "price_staleness_days",
    "position_status",
    "created_at",
]

POSITION_SNAPSHOT_MONEY_FIELDS = {
    "avg_price",
    "cost_value",
    "close_price",
    "market_value",
    "unrealized_pnl",
    "realized_pnl",
    "total_pnl",
}


def _normalize_snapshot_date(snapshot_date: str) -> str:
    clean_date = snapshot_date.replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid snapshot_date format: {snapshot_date}")
    return datetime.strptime(clean_date, "%Y%m%d").strftime("%Y-%m-%d")


def build_paper_position_snapshot_backup_path(
    snapshot_path: Path,
    archive_dir: Path,
    now: datetime | None = None,
) -> Path:
    timestamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    return archive_dir / f"{snapshot_path.stem}_{timestamp}_backup{snapshot_path.suffix}"


def build_paper_position_snapshot_rows(
    state: PaperAccountState,
    market_valuation: PaperAccountValuation,
    snapshot_date: str,
    created_at: str | None = None,
) -> list[dict[str, Any]]:
    normalized_date = _normalize_snapshot_date(snapshot_date)
    rows: list[dict[str, Any]] = []

    for position in market_valuation.positions:
        realized_pnl = round(float(state.realized_pnl_by_symbol.get(position.symbol, 0.0)), 2)
        total_pnl = realized_pnl + float(position.unrealized_pnl)
        cost_value = float(position.cost_value)
        rows.append(
            {
                "snapshot_date": normalized_date,
                "symbol": position.symbol,
                "shares": position.shares,
                "avg_price": round(float(position.avg_price), 2),
                "cost_value": round(cost_value, 2),
                "close_price": round(float(position.close_price), 2),
                "market_value": round(float(position.market_value), 2),
                "unrealized_pnl": round(float(position.unrealized_pnl), 2),
                "unrealized_pnl_pct": position.unrealized_pnl_pct,
                "realized_pnl": realized_pnl,
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct_on_current_cost": (total_pnl / cost_value) if cost_value > 0 else "",
                "valuation_method": market_valuation.valuation_method,
                "valuation_price_date": position.valuation_price_date,
                "price_staleness_days": position.price_staleness_days,
                "position_status": "OPEN",
                "created_at": created_at or datetime.now().isoformat(timespec="seconds"),
            }
        )
    rows.sort(key=lambda row: (str(row["snapshot_date"]), str(row["symbol"])))
    return rows


def save_paper_position_snapshot(
    rows: list[dict[str, Any]],
    snapshot_date: str,
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

    normalized_date = _normalize_snapshot_date(snapshot_date)
    existing_rows: list[dict[str, Any]] = []
    backup_path: Path | None = None
    replaced = False

    if snapshot_path.exists():
        with snapshot_path.open("r", encoding="utf-8-sig", newline="") as handle:
            existing_rows = list(csv.DictReader(handle))
        if any(str(row.get("snapshot_date", "")).strip() == normalized_date for row in existing_rows):
            archive_dir.mkdir(parents=True, exist_ok=True)
            backup_path = build_paper_position_snapshot_backup_path(snapshot_path, archive_dir, now=now)
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
        if str(row.get("snapshot_date", "")).strip() != normalized_date
    ]

    serialized_rows: list[dict[str, Any]] = []
    for row in rows:
        serialized_row: dict[str, Any] = {}
        for column in PAPER_POSITION_SNAPSHOT_COLUMNS:
            value = row.get(column, "")
            if column in POSITION_SNAPSHOT_MONEY_FIELDS and value != "":
                serialized_row[column] = f"{float(value):.2f}"
            elif column in {"unrealized_pnl_pct", "total_pnl_pct_on_current_cost"} and value != "":
                serialized_row[column] = f"{float(value):.7f}"
            else:
                serialized_row[column] = value
        serialized_rows.append(serialized_row)

    final_rows = kept_rows + serialized_rows
    final_rows.sort(key=lambda row: (str(row.get("snapshot_date", "")).strip(), str(row.get("symbol", "")).strip()))

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with snapshot_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_POSITION_SNAPSHOT_COLUMNS)
        writer.writeheader()
        writer.writerows(final_rows)

    return {
        "path": snapshot_path,
        "backup_path": backup_path,
        "row_count": len(final_rows),
        "replaced": replaced,
        "snapshot_date": normalized_date,
        "saved_rows": rows,
    }
