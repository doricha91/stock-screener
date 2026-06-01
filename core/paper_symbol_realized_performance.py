from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_guard import assert_path_under_account_root
from core.paper_realized_trade_journal import (
    COST_BASIS_METHOD,
    ENTRY_BASIS_TYPE,
    LOT_LINKING_STATUS,
)
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


PAPER_SYMBOL_REALIZED_PERFORMANCE_COLUMNS = [
    "symbol",
    "realized_trade_count",
    "total_realized_pnl",
    "win_count",
    "loss_count",
    "flat_count",
    "win_rate",
    "loss_rate",
    "flat_rate",
    "avg_realized_pnl",
    "avg_realized_return_pct",
    "best_trade_pnl",
    "worst_trade_pnl",
    "best_trade_return_pct",
    "worst_trade_return_pct",
    "total_shares_closed",
    "cost_basis_method",
    "entry_basis_type",
    "lot_linking_status",
    "first_close_date",
    "last_close_date",
    "positive_realized_pnl",
    "negative_realized_pnl",
    "gross_profit",
    "gross_loss",
    "profit_factor",
]

REQUIRED_REALIZED_TRADE_JOURNAL_COLUMNS = [
    "close_date",
    "symbol",
    "shares_closed",
    "realized_pnl",
    "realized_return_pct",
    "cost_basis_method",
    "entry_basis_type",
    "lot_linking_status",
]


def _normalize_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("close_date is required")
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
    return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")


def _parse_float(value: Any, field_name: str) -> float:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is blank")
    normalized = text.replace(",", "").replace("$", "")
    lowered = normalized.lower()
    if lowered in {"nan", "inf", "-inf", "infinity", "-infinity"}:
        raise ValueError(f"invalid numeric in {field_name}: {value}")
    try:
        return float(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid numeric in {field_name}: {value}") from exc


def _parse_int(value: Any, field_name: str) -> int:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is blank")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"invalid integer in {field_name}: {value}") from exc


def load_paper_realized_trade_journal_rows(
    path: Path,
    allowed_root: Path | None = None,
) -> list[dict[str, str]]:
    if allowed_root is None:
        assert_paper_path(path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(path, allowed_root)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    missing_columns = [column for column in REQUIRED_REALIZED_TRADE_JOURNAL_COLUMNS if column not in rows[0]]
    if missing_columns:
        raise ValueError("Missing realized trade journal columns: " + ", ".join(missing_columns))
    return rows


def _validate_policy(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    if not rows:
        return COST_BASIS_METHOD, ENTRY_BASIS_TYPE, LOT_LINKING_STATUS
    policy_triplets = {
        (
            str(row.get("cost_basis_method", "")).strip(),
            str(row.get("entry_basis_type", "")).strip(),
            str(row.get("lot_linking_status", "")).strip(),
        )
        for row in rows
    }
    if len(policy_triplets) != 1:
        raise ValueError("Mixed cost basis policy rows are not supported")
    cost_basis_method, entry_basis_type, lot_linking_status = next(iter(policy_triplets))
    if cost_basis_method != COST_BASIS_METHOD:
        raise ValueError(f"Unsupported cost_basis_method: {cost_basis_method}")
    if entry_basis_type != ENTRY_BASIS_TYPE:
        raise ValueError(f"Unsupported entry_basis_type: {entry_basis_type}")
    if lot_linking_status != LOT_LINKING_STATUS:
        raise ValueError(f"Unsupported lot_linking_status: {lot_linking_status}")
    return cost_basis_method, entry_basis_type, lot_linking_status


def build_paper_symbol_realized_performance(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[str]]:
    cost_basis_method, entry_basis_type, lot_linking_status = _validate_policy(rows)
    warnings: list[str] = []
    if not rows:
        warnings.append("No realized trade rows found in paper_realized_trade_journal.csv")
        return [], warnings

    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw_row in rows:
        symbol = str(raw_row.get("symbol", "")).strip()
        if not symbol:
            raise ValueError("symbol is required")
        parsed_row = {
            "symbol": symbol,
            "close_date": _normalize_date(raw_row.get("close_date", "")),
            "shares_closed": _parse_int(raw_row.get("shares_closed", ""), "shares_closed"),
            "realized_pnl": _parse_float(raw_row.get("realized_pnl", ""), "realized_pnl"),
            "realized_return_pct": _parse_float(raw_row.get("realized_return_pct", ""), "realized_return_pct"),
        }
        grouped.setdefault(symbol, []).append(parsed_row)

    output_rows: list[dict[str, Any]] = []
    for symbol in sorted(grouped):
        symbol_rows = grouped[symbol]
        realized_trade_count = len(symbol_rows)
        realized_pnls = [row["realized_pnl"] for row in symbol_rows]
        realized_returns = [row["realized_return_pct"] for row in symbol_rows]
        total_realized_pnl = sum(realized_pnls)
        win_count = sum(1 for value in realized_pnls if value > 0)
        loss_count = sum(1 for value in realized_pnls if value < 0)
        flat_count = sum(1 for value in realized_pnls if value == 0)
        win_rate = win_count / realized_trade_count
        loss_rate = loss_count / realized_trade_count
        flat_rate = flat_count / realized_trade_count
        avg_realized_pnl = total_realized_pnl / realized_trade_count
        avg_realized_return_pct = sum(realized_returns) / realized_trade_count
        gross_profit = sum(value for value in realized_pnls if value > 0)
        negative_realized_pnl = sum(value for value in realized_pnls if value < 0)
        gross_loss = abs(negative_realized_pnl)
        output_rows.append(
            {
                "symbol": symbol,
                "realized_trade_count": realized_trade_count,
                "total_realized_pnl": total_realized_pnl,
                "win_count": win_count,
                "loss_count": loss_count,
                "flat_count": flat_count,
                "win_rate": win_rate,
                "loss_rate": loss_rate,
                "flat_rate": flat_rate,
                "avg_realized_pnl": avg_realized_pnl,
                "avg_realized_return_pct": avg_realized_return_pct,
                "best_trade_pnl": max(realized_pnls),
                "worst_trade_pnl": min(realized_pnls),
                "best_trade_return_pct": max(realized_returns),
                "worst_trade_return_pct": min(realized_returns),
                "total_shares_closed": sum(row["shares_closed"] for row in symbol_rows),
                "cost_basis_method": cost_basis_method,
                "entry_basis_type": entry_basis_type,
                "lot_linking_status": lot_linking_status,
                "first_close_date": min(row["close_date"] for row in symbol_rows),
                "last_close_date": max(row["close_date"] for row in symbol_rows),
                "positive_realized_pnl": gross_profit,
                "negative_realized_pnl": negative_realized_pnl,
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
                "profit_factor": (gross_profit / gross_loss) if gross_loss > 0 else "",
            }
        )

    return output_rows, warnings


def _serialize_csv_value(column: str, value: Any) -> Any:
    if column in {
        "total_realized_pnl",
        "avg_realized_pnl",
        "best_trade_pnl",
        "worst_trade_pnl",
        "positive_realized_pnl",
        "negative_realized_pnl",
        "gross_profit",
        "gross_loss",
    } and value != "":
        return f"{float(value):.2f}"
    if column in {
        "win_rate",
        "loss_rate",
        "flat_rate",
        "avg_realized_return_pct",
        "best_trade_return_pct",
        "worst_trade_return_pct",
        "profit_factor",
    } and value != "":
        return f"{float(value):.7f}"
    return value


def write_paper_symbol_realized_performance(
    rows: list[dict[str, Any]],
    output_path: Path,
    allowed_root: Path | None = None,
) -> None:
    if allowed_root is None:
        assert_paper_path(output_path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(output_path, allowed_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_SYMBOL_REALIZED_PERFORMANCE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    column: _serialize_csv_value(column, row.get(column, ""))
                    for column in PAPER_SYMBOL_REALIZED_PERFORMANCE_COLUMNS
                }
            )


def summarize_paper_symbol_realized_performance(
    rows: list[dict[str, Any]],
    input_path: Path,
    output_path: Path,
    warnings: list[str] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    warnings = list(warnings or [])
    symbol_count = len(rows)
    total_realized_trade_count = sum(int(row["realized_trade_count"]) for row in rows)
    total_realized_pnl = sum(float(row["total_realized_pnl"]) for row in rows)
    total_win_count = sum(int(row["win_count"]) for row in rows)
    total_loss_count = sum(int(row["loss_count"]) for row in rows)
    total_flat_count = sum(int(row["flat_count"]) for row in rows)
    overall_win_rate = (total_win_count / total_realized_trade_count * 100.0) if total_realized_trade_count > 0 else 0.0
    top_symbols = sorted(rows, key=lambda row: (float(row["total_realized_pnl"]), str(row["symbol"])), reverse=True)[:3]
    worst_symbols = sorted(rows, key=lambda row: (float(row["total_realized_pnl"]), str(row["symbol"])))[:3]
    if total_realized_trade_count == 0:
        warnings.append("No realized trades available; symbol performance report is empty.")
    if rows:
        cost_basis_method = str(rows[0]["cost_basis_method"])
        entry_basis_type = str(rows[0]["entry_basis_type"])
        lot_linking_status = str(rows[0]["lot_linking_status"])
    else:
        cost_basis_method = COST_BASIS_METHOD
        entry_basis_type = ENTRY_BASIS_TYPE
        lot_linking_status = LOT_LINKING_STATUS
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "input_path": str(input_path),
        "output_path": str(output_path),
        "symbol_count": symbol_count,
        "total_realized_trade_count": total_realized_trade_count,
        "total_realized_pnl": total_realized_pnl,
        "total_win_count": total_win_count,
        "total_loss_count": total_loss_count,
        "total_flat_count": total_flat_count,
        "overall_win_rate": overall_win_rate,
        "top_symbols": top_symbols,
        "worst_symbols": worst_symbols,
        "cost_basis_method": cost_basis_method,
        "entry_basis_type": entry_basis_type,
        "lot_linking_status": lot_linking_status,
        "warnings": warnings,
        "limitations": [
            "This report summarizes realized SELL-event performance only.",
            "Unrealized PnL and current open positions are not included.",
            "FIFO/LIFO/lot-matched closed trade accounting is not implemented.",
            "open_date and holding_days are intentionally excluded.",
            "Metrics are preliminary when realized trade count is small.",
        ],
    }


def render_paper_symbol_realized_performance_summary(summary: dict[str, Any]) -> str:
    def _format_symbol_rows(rows: list[dict[str, Any]]) -> str:
        if not rows:
            return "-"
        return ", ".join(f"{row['symbol']} ({float(row['total_realized_pnl']):.2f})" for row in rows)

    lines = [
        "# Paper Symbol Realized Performance Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Input file path: {summary['input_path']}",
        f"- Output CSV path: {summary['output_path']}",
        f"- Symbol count: {summary['symbol_count']}",
        f"- Total realized trade count: {summary['total_realized_trade_count']}",
        f"- Total realized PnL: {summary['total_realized_pnl']:.2f}",
        f"- Total win/loss/flat count: {summary['total_win_count']} / {summary['total_loss_count']} / {summary['total_flat_count']}",
        f"- Overall win rate: {summary['overall_win_rate']:.2f}%",
        f"- Top realized PnL symbols: {_format_symbol_rows(summary['top_symbols'])}",
        f"- Worst realized PnL symbols: {_format_symbol_rows(summary['worst_symbols'])}",
        f"- Cost basis method: {summary['cost_basis_method']}",
        f"- Entry basis type: {summary['entry_basis_type']}",
        f"- Lot linking status: {summary['lot_linking_status']}",
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


def write_paper_symbol_realized_performance_summary(
    markdown: str,
    output_path: Path,
    allowed_root: Path | None = None,
) -> None:
    if allowed_root is None:
        assert_paper_path(output_path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(output_path, allowed_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
