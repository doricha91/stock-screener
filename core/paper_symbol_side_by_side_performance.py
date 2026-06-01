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


PAPER_SYMBOL_SIDE_BY_SIDE_PERFORMANCE_COLUMNS = [
    "symbol",
    "symbol_status",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "realized_trade_count",
    "win_count",
    "loss_count",
    "flat_count",
    "win_rate",
    "avg_realized_return_pct",
    "open_shares",
    "open_market_value",
    "open_cost_basis",
    "open_unrealized_return_pct",
    "position_weight_market",
    "cost_basis_method",
    "entry_basis_type",
    "lot_linking_status",
    "snapshot_date",
    "realized_pnl_rank",
    "unrealized_pnl_rank",
    "total_pnl_rank",
    "total_pnl_contribution_pct",
    "risk_note",
]

REQUIRED_REALIZED_COLUMNS = [
    "symbol",
    "total_realized_pnl",
    "realized_trade_count",
    "win_count",
    "loss_count",
    "flat_count",
    "win_rate",
    "avg_realized_return_pct",
    "cost_basis_method",
    "entry_basis_type",
    "lot_linking_status",
]

REQUIRED_UNREALIZED_COLUMNS = [
    "symbol",
    "snapshot_date",
    "shares",
    "market_value",
    "cost_basis",
    "unrealized_pnl",
    "unrealized_return_pct",
    "position_weight_market",
    "cost_basis_method",
]


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


def _normalize_date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) == 8 and text.isdigit():
        return datetime.strptime(text, "%Y%m%d").strftime("%Y-%m-%d")
    return datetime.strptime(text, "%Y-%m-%d").strftime("%Y-%m-%d")


def load_paper_symbol_realized_performance_rows(
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
    missing = [column for column in REQUIRED_REALIZED_COLUMNS if column not in rows[0]]
    if missing:
        raise ValueError("Missing paper symbol realized performance columns: " + ", ".join(missing))
    return rows


def load_paper_symbol_unrealized_performance_rows(
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
    missing = [column for column in REQUIRED_UNREALIZED_COLUMNS if column not in rows[0]]
    if missing:
        raise ValueError("Missing paper symbol unrealized performance columns: " + ", ".join(missing))
    return rows


def build_paper_symbol_side_by_side_performance(
    realized_rows: list[dict[str, str]],
    unrealized_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    warnings: list[str] = []
    realized_by_symbol: dict[str, dict[str, Any]] = {}
    unrealized_by_symbol: dict[str, dict[str, Any]] = {}

    for row in realized_rows:
        symbol = str(row.get("symbol", "")).strip()
        if not symbol:
            raise ValueError("symbol is required in realized rows")
        realized_by_symbol[symbol] = {
            "symbol": symbol,
            "realized_pnl": _parse_float(row.get("total_realized_pnl", ""), "total_realized_pnl"),
            "realized_trade_count": _parse_int(row.get("realized_trade_count", ""), "realized_trade_count"),
            "win_count": _parse_int(row.get("win_count", ""), "win_count"),
            "loss_count": _parse_int(row.get("loss_count", ""), "loss_count"),
            "flat_count": _parse_int(row.get("flat_count", ""), "flat_count"),
            "win_rate": _parse_float(row.get("win_rate", ""), "win_rate"),
            "avg_realized_return_pct": _parse_float(row.get("avg_realized_return_pct", ""), "avg_realized_return_pct"),
            "cost_basis_method": str(row.get("cost_basis_method", "")).strip(),
            "entry_basis_type": str(row.get("entry_basis_type", "")).strip(),
            "lot_linking_status": str(row.get("lot_linking_status", "")).strip(),
        }

    for row in unrealized_rows:
        symbol = str(row.get("symbol", "")).strip()
        if not symbol:
            raise ValueError("symbol is required in unrealized rows")
        unrealized_by_symbol[symbol] = {
            "symbol": symbol,
            "snapshot_date": _normalize_date(row.get("snapshot_date", "")),
            "open_shares": _parse_int(row.get("shares", ""), "shares"),
            "open_market_value": _parse_float(row.get("market_value", ""), "market_value"),
            "open_cost_basis": _parse_float(row.get("cost_basis", ""), "cost_basis"),
            "unrealized_pnl": _parse_float(row.get("unrealized_pnl", ""), "unrealized_pnl"),
            "open_unrealized_return_pct": _parse_float(row.get("unrealized_return_pct", ""), "unrealized_return_pct"),
            "position_weight_market": _parse_float(row.get("position_weight_market", ""), "position_weight_market"),
            "cost_basis_method": str(row.get("cost_basis_method", "")).strip(),
        }

    all_symbols = sorted(set(realized_by_symbol) | set(unrealized_by_symbol))
    combined_rows: list[dict[str, Any]] = []
    for symbol in all_symbols:
        realized = realized_by_symbol.get(symbol)
        unrealized = unrealized_by_symbol.get(symbol)
        if realized and unrealized:
            status = "realized_and_unrealized"
        elif realized:
            status = "realized_only"
        else:
            status = "unrealized_only"

        cost_basis_method = (
            realized["cost_basis_method"] if realized is not None else unrealized["cost_basis_method"]
        )
        entry_basis_type = realized["entry_basis_type"] if realized is not None else ""
        lot_linking_status = realized["lot_linking_status"] if realized is not None else ""

        realized_pnl = realized["realized_pnl"] if realized is not None else 0.0
        unrealized_pnl = unrealized["unrealized_pnl"] if unrealized is not None else 0.0
        total_pnl = realized_pnl + unrealized_pnl

        if realized is None:
            risk_note = "no_realized_history"
        elif unrealized is None:
            risk_note = "no_open_position"
        else:
            risk_note = ""

        combined_rows.append(
            {
                "symbol": symbol,
                "symbol_status": status,
                "realized_pnl": realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "total_pnl": total_pnl,
                "realized_trade_count": realized["realized_trade_count"] if realized is not None else 0,
                "win_count": realized["win_count"] if realized is not None else 0,
                "loss_count": realized["loss_count"] if realized is not None else 0,
                "flat_count": realized["flat_count"] if realized is not None else 0,
                "win_rate": realized["win_rate"] if realized is not None else 0.0,
                "avg_realized_return_pct": realized["avg_realized_return_pct"] if realized is not None else 0.0,
                "open_shares": unrealized["open_shares"] if unrealized is not None else 0,
                "open_market_value": unrealized["open_market_value"] if unrealized is not None else 0.0,
                "open_cost_basis": unrealized["open_cost_basis"] if unrealized is not None else 0.0,
                "open_unrealized_return_pct": unrealized["open_unrealized_return_pct"] if unrealized is not None else 0.0,
                "position_weight_market": unrealized["position_weight_market"] if unrealized is not None else 0.0,
                "cost_basis_method": cost_basis_method or COST_BASIS_METHOD,
                "entry_basis_type": entry_basis_type,
                "lot_linking_status": lot_linking_status,
                "snapshot_date": unrealized["snapshot_date"] if unrealized is not None else "",
                "risk_note": risk_note,
            }
        )

    total_positive_pnl = sum(max(float(row["total_pnl"]), 0.0) for row in combined_rows)
    total_negative_pnl = sum(min(float(row["total_pnl"]), 0.0) for row in combined_rows)
    total_abs_pnl = total_positive_pnl + abs(total_negative_pnl)
    total_ranked = sorted(combined_rows, key=lambda row: (float(row["total_pnl"]), str(row["symbol"])), reverse=True)
    realized_ranked = sorted(combined_rows, key=lambda row: (float(row["realized_pnl"]), str(row["symbol"])), reverse=True)
    unrealized_ranked = sorted(combined_rows, key=lambda row: (float(row["unrealized_pnl"]), str(row["symbol"])), reverse=True)
    for idx, row in enumerate(realized_ranked, start=1):
        row["realized_pnl_rank"] = idx
    for idx, row in enumerate(unrealized_ranked, start=1):
        row["unrealized_pnl_rank"] = idx
    for idx, row in enumerate(total_ranked, start=1):
        row["total_pnl_rank"] = idx
    for row in combined_rows:
        row["total_pnl_contribution_pct"] = (float(row["total_pnl"]) / total_abs_pnl * 100.0) if total_abs_pnl > 0 else 0.0

    summary_data = {
        "symbol_count": len(combined_rows),
        "realized_only_count": sum(1 for row in combined_rows if row["symbol_status"] == "realized_only"),
        "unrealized_only_count": sum(1 for row in combined_rows if row["symbol_status"] == "unrealized_only"),
        "realized_and_unrealized_count": sum(1 for row in combined_rows if row["symbol_status"] == "realized_and_unrealized"),
        "total_realized_pnl": sum(float(row["realized_pnl"]) for row in combined_rows),
        "total_unrealized_pnl": sum(float(row["unrealized_pnl"]) for row in combined_rows),
        "total_pnl_reference": sum(float(row["total_pnl"]) for row in combined_rows),
        "top_total_pnl_symbols": total_ranked[:3],
        "worst_total_pnl_symbols": list(reversed(total_ranked[-3:])),
        "top_unrealized_pnl_symbols": unrealized_ranked[:3],
        "worst_realized_pnl_symbols": list(reversed(realized_ranked[-3:])),
    }
    return sorted(combined_rows, key=lambda row: str(row["symbol"])), summary_data, warnings


def _serialize_csv_value(column: str, value: Any) -> Any:
    if column in {
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
        "avg_realized_return_pct",
        "open_market_value",
        "open_cost_basis",
        "open_unrealized_return_pct",
        "position_weight_market",
        "total_pnl_contribution_pct",
    } and value != "":
        if column in {"realized_pnl", "unrealized_pnl", "total_pnl", "open_market_value", "open_cost_basis"}:
            return f"{float(value):.2f}"
        return f"{float(value):.7f}"
    return value


def write_paper_symbol_side_by_side_performance(
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
        writer = csv.DictWriter(handle, fieldnames=PAPER_SYMBOL_SIDE_BY_SIDE_PERFORMANCE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    column: _serialize_csv_value(column, row.get(column, ""))
                    for column in PAPER_SYMBOL_SIDE_BY_SIDE_PERFORMANCE_COLUMNS
                }
            )


def summarize_paper_symbol_side_by_side_performance(
    summary_data: dict[str, Any],
    warnings: list[str],
    realized_input_path: Path,
    unrealized_input_path: Path,
    output_path: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "realized_input_path": str(realized_input_path),
        "unrealized_input_path": str(unrealized_input_path),
        "output_path": str(output_path),
        "warnings": warnings,
        "limitations": [
            "This report shows realized and unrealized performance side by side.",
            "total_pnl is a reference metric, not a lot-matched accounting result.",
            "Realized PnL is average-cost SELL-event based.",
            "Unrealized PnL is current open-position snapshot based.",
            "FIFO/LIFO/lot ledger accounting is not implemented.",
            "open_date and holding_days are intentionally excluded.",
            "Metrics are preliminary when trade count or snapshot history is small.",
        ],
        **summary_data,
    }


def _format_symbol_rows(rows: list[dict[str, Any]], metric_key: str) -> str:
    if not rows:
        return "-"
    return ", ".join(f"{row['symbol']} ({float(row[metric_key]):.2f})" for row in rows)


def render_paper_symbol_side_by_side_performance_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Paper Symbol Side-by-Side Performance Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Realized input file path: {summary['realized_input_path']}",
        f"- Unrealized input file path: {summary['unrealized_input_path']}",
        f"- Output CSV path: {summary['output_path']}",
        f"- Symbol count: {summary['symbol_count']}",
        f"- realized_only count: {summary['realized_only_count']}",
        f"- unrealized_only count: {summary['unrealized_only_count']}",
        f"- realized_and_unrealized count: {summary['realized_and_unrealized_count']}",
        f"- Total realized PnL: {summary['total_realized_pnl']:.2f}",
        f"- Total unrealized PnL: {summary['total_unrealized_pnl']:.2f}",
        f"- Total PnL reference: {summary['total_pnl_reference']:.2f}",
        f"- Top total PnL symbols: {_format_symbol_rows(summary['top_total_pnl_symbols'], 'total_pnl')}",
        f"- Worst total PnL symbols: {_format_symbol_rows(summary['worst_total_pnl_symbols'], 'total_pnl')}",
        f"- Top unrealized PnL symbols: {_format_symbol_rows(summary['top_unrealized_pnl_symbols'], 'unrealized_pnl')}",
        f"- Worst realized PnL symbols: {_format_symbol_rows(summary['worst_realized_pnl_symbols'], 'realized_pnl')}",
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


def write_paper_symbol_side_by_side_performance_summary(
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
