from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_execution_log import PAPER_EXECUTION_LOG_COLUMNS
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


REALIZED_TRADE_JOURNAL_COLUMNS = [
    "close_date",
    "symbol",
    "shares_closed",
    "entry_price_basis",
    "exit_price",
    "realized_pnl",
    "realized_return_pct",
    "close_trade_id",
    "source",
    "reason",
    "cost_basis_method",
    "entry_basis_type",
    "lot_linking_status",
    "regime",
    "gross_amount",
    "notes",
    "rec_shares",
    "rec_price",
    "position_shares_before_sell",
    "position_shares_after_sell",
    "avg_price_before_sell",
    "cash_after_trade",
    "realized_pnl_cumulative_after_trade",
    "realized_pnl_by_symbol_after_trade",
]

DEFAULT_INITIAL_CASH = 100000.0
DEFAULT_CURRENCY = "USD"
COST_BASIS_METHOD = "average_cost"
ENTRY_BASIS_TYPE = "position_avg_price_before_sell"
LOT_LINKING_STATUS = "not_applicable"


@dataclass(frozen=True)
class ReplayPosition:
    shares: int
    avg_price: float


@dataclass(frozen=True)
class RealizedTradeJournalBuildResult:
    rows: list[dict[str, Any]]
    duplicate_skipped_count: int
    warnings: list[str]


def _normalize_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("date is required")
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
    return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")


def _parse_trade_row(trade_row: dict[str, Any]) -> dict[str, Any]:
    trade_id = str(trade_row.get("trade_id", "")).strip()
    symbol = str(trade_row.get("symbol", "")).strip()
    side = str(trade_row.get("side", "")).strip().upper()
    if not trade_id:
        raise ValueError("trade_id is required")
    if not symbol:
        raise ValueError("symbol is required")
    if side not in {"BUY", "SELL"}:
        raise ValueError(f"unsupported side: {side}")

    try:
        shares = int(trade_row.get("shares"))
    except Exception as exc:
        raise ValueError("shares must be an integer") from exc

    try:
        price = float(trade_row.get("price"))
    except Exception as exc:
        raise ValueError("price must be numeric") from exc

    if price <= 0:
        raise ValueError("price must be > 0")
    if shares == 0:
        raise ValueError("shares must not be 0")
    if side == "BUY" and shares < 0:
        raise ValueError("BUY shares must be > 0")
    if side == "SELL" and shares > 0:
        raise ValueError("SELL shares must be < 0")

    return {
        "trade_id": trade_id,
        "date": _normalize_date(str(trade_row.get("date", "")).strip()),
        "regime": str(trade_row.get("regime", "")).strip(),
        "symbol": symbol,
        "side": side,
        "shares": shares,
        "price": price,
        "gross_amount": float(trade_row.get("gross_amount")) if str(trade_row.get("gross_amount", "")).strip() else shares * price,
        "source": str(trade_row.get("source", "")).strip(),
        "reason": str(trade_row.get("reason", "")).strip(),
        "notes": str(trade_row.get("notes", "")).strip(),
        "rec_shares": str(trade_row.get("rec_shares", "")).strip(),
        "rec_price": str(trade_row.get("rec_price", "")).strip(),
    }


def load_paper_execution_rows(path: Path) -> list[dict[str, str]]:
    assert_paper_path(path, PAPER_TEST_DIR)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    missing_columns = [column for column in PAPER_EXECUTION_LOG_COLUMNS if column not in rows[0]]
    if missing_columns:
        raise ValueError("Missing paper execution log columns: " + ", ".join(missing_columns))
    return rows


def build_average_cost_realized_trade_journal(
    trade_rows: list[dict[str, Any]],
    initial_cash: float = DEFAULT_INITIAL_CASH,
    currency: str = DEFAULT_CURRENCY,
) -> RealizedTradeJournalBuildResult:
    del currency

    cash = float(initial_cash)
    positions: dict[str, ReplayPosition] = {}
    realized_pnl_cumulative = 0.0
    realized_pnl_by_symbol: dict[str, float] = {}
    applied_trade_ids: set[str] = set()
    output_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    duplicate_skipped_count = 0

    for raw_row in trade_rows:
        row = _parse_trade_row(raw_row)
        trade_id = row["trade_id"]
        symbol = row["symbol"]
        side = row["side"]
        shares = row["shares"]
        price = row["price"]

        if trade_id in applied_trade_ids:
            duplicate_skipped_count += 1
            warnings.append(f"Duplicate trade_id skipped: {trade_id}")
            continue

        if side == "BUY":
            cost = shares * price
            if cash < cost:
                raise ValueError("insufficient cash for BUY")
            existing = positions.get(symbol)
            if existing is None:
                positions[symbol] = ReplayPosition(shares=shares, avg_price=price)
            else:
                new_total_shares = existing.shares + shares
                new_avg_price = ((existing.shares * existing.avg_price) + (shares * price)) / new_total_shares
                positions[symbol] = ReplayPosition(shares=new_total_shares, avg_price=new_avg_price)
            cash -= cost
        else:
            sell_quantity = abs(shares)
            existing = positions.get(symbol)
            if existing is None:
                raise ValueError("cannot SELL without an open position")
            if existing.shares < sell_quantity:
                raise ValueError("cannot SELL more shares than held")

            avg_price_before_sell = existing.avg_price
            position_shares_before_sell = existing.shares
            realized_pnl = (price - avg_price_before_sell) * sell_quantity
            realized_return_pct = round((price / avg_price_before_sell - 1.0) * 100.0, 7)
            realized_pnl_cumulative += realized_pnl
            realized_pnl_by_symbol[symbol] = realized_pnl_by_symbol.get(symbol, 0.0) + realized_pnl
            cash += sell_quantity * price

            position_shares_after_sell = existing.shares - sell_quantity
            if position_shares_after_sell == 0:
                positions.pop(symbol, None)
            else:
                positions[symbol] = ReplayPosition(
                    shares=position_shares_after_sell,
                    avg_price=avg_price_before_sell,
                )

            output_rows.append(
                {
                    "close_date": row["date"],
                    "symbol": symbol,
                    "shares_closed": sell_quantity,
                    "entry_price_basis": avg_price_before_sell,
                    "exit_price": price,
                    "realized_pnl": realized_pnl,
                    "realized_return_pct": realized_return_pct,
                    "close_trade_id": trade_id,
                    "source": row["source"],
                    "reason": row["reason"],
                    "cost_basis_method": COST_BASIS_METHOD,
                    "entry_basis_type": ENTRY_BASIS_TYPE,
                    "lot_linking_status": LOT_LINKING_STATUS,
                    "regime": row["regime"],
                    "gross_amount": row["gross_amount"],
                    "notes": row["notes"],
                    "rec_shares": row["rec_shares"],
                    "rec_price": row["rec_price"],
                    "position_shares_before_sell": position_shares_before_sell,
                    "position_shares_after_sell": position_shares_after_sell,
                    "avg_price_before_sell": avg_price_before_sell,
                    "cash_after_trade": cash,
                    "realized_pnl_cumulative_after_trade": realized_pnl_cumulative,
                    "realized_pnl_by_symbol_after_trade": realized_pnl_by_symbol[symbol],
                }
            )

        applied_trade_ids.add(trade_id)

    return RealizedTradeJournalBuildResult(
        rows=output_rows,
        duplicate_skipped_count=duplicate_skipped_count,
        warnings=warnings,
    )


def _serialize_csv_value(column: str, value: Any) -> Any:
    if column in {
        "entry_price_basis",
        "exit_price",
        "realized_pnl",
        "gross_amount",
        "avg_price_before_sell",
        "cash_after_trade",
        "realized_pnl_cumulative_after_trade",
        "realized_pnl_by_symbol_after_trade",
    } and value != "":
        return f"{float(value):.2f}"
    if column == "realized_return_pct" and value != "":
        return f"{float(value):.7f}"
    return value


def write_realized_trade_journal(rows: list[dict[str, Any]], output_path: Path) -> None:
    assert_paper_path(output_path, PAPER_TEST_DIR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REALIZED_TRADE_JOURNAL_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    column: _serialize_csv_value(column, row.get(column, ""))
                    for column in REALIZED_TRADE_JOURNAL_COLUMNS
                }
            )


def summarize_realized_trade_journal(
    rows: list[dict[str, Any]],
    input_path: Path,
    output_path: Path,
    duplicate_skipped_count: int = 0,
    warnings: list[str] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    warnings = warnings or []
    realized_pnls = [float(row["realized_pnl"]) for row in rows]
    realized_returns = [float(row["realized_return_pct"]) for row in rows]
    total_realized_pnl = sum(realized_pnls)
    win_count = sum(1 for value in realized_pnls if value > 0)
    loss_count = sum(1 for value in realized_pnls if value < 0)
    flat_count = sum(1 for value in realized_pnls if value == 0)
    total_count = len(rows)
    win_rate = (win_count / total_count * 100.0) if total_count > 0 else 0.0
    avg_realized_return_pct = (sum(realized_returns) / total_count) if total_count > 0 else 0.0
    total_shares_closed = sum(int(row["shares_closed"]) for row in rows)
    symbols = sorted({str(row["symbol"]) for row in rows})
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "input_path": str(input_path),
        "output_path": str(output_path),
        "cost_basis_method": COST_BASIS_METHOD,
        "entry_basis_type": ENTRY_BASIS_TYPE,
        "lot_linking_status": LOT_LINKING_STATUS,
        "total_realized_trade_count": total_count,
        "total_realized_pnl": total_realized_pnl,
        "win_count": win_count,
        "loss_count": loss_count,
        "flat_count": flat_count,
        "win_rate": win_rate,
        "avg_realized_return_pct": avg_realized_return_pct,
        "total_shares_closed": total_shares_closed,
        "symbols_included": symbols,
        "duplicate_skipped_count": duplicate_skipped_count,
        "warnings": warnings,
        "limitations": [
            "This journal is SELL-event based, not lot-matched closed trade accounting.",
            "open_date and holding_days are intentionally excluded.",
            "FIFO/LIFO/specific-lot accounting is not implemented.",
            "entry_price_basis uses average cost immediately before each SELL.",
        ],
    }


def render_realized_trade_journal_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Paper Realized Trade Journal Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Input file path: {summary['input_path']}",
        f"- Output CSV path: {summary['output_path']}",
        f"- Cost basis method: {summary['cost_basis_method']}",
        f"- Entry basis type: {summary['entry_basis_type']}",
        f"- Lot linking status: {summary['lot_linking_status']}",
        f"- Total realized trade count: {summary['total_realized_trade_count']}",
        f"- Total realized PnL: {summary['total_realized_pnl']:.2f}",
        f"- Win count: {summary['win_count']}",
        f"- Loss count: {summary['loss_count']}",
        f"- Flat count: {summary['flat_count']}",
        f"- Win rate: {summary['win_rate']:.2f}%",
        f"- Avg realized return pct: {summary['avg_realized_return_pct']:.7f}%",
        f"- Total shares closed: {summary['total_shares_closed']}",
        f"- Symbols included: {'|'.join(summary['symbols_included']) if summary['symbols_included'] else '-'}",
        f"- Duplicate skipped count: {summary['duplicate_skipped_count']}",
        "",
        "## Warnings",
    ]
    if summary["warnings"]:
        lines.extend(f"- {warning}" for warning in summary["warnings"])
    else:
        lines.append("- None")
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def write_realized_trade_journal_summary(markdown: str, output_path: Path) -> None:
    assert_paper_path(output_path, PAPER_TEST_DIR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
