from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_guard import assert_path_under_account_root
from core.paper_realized_trade_journal import COST_BASIS_METHOD
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


PAPER_SYMBOL_UNREALIZED_PERFORMANCE_COLUMNS = [
    "snapshot_date",
    "symbol",
    "shares",
    "avg_price",
    "market_price",
    "cost_basis",
    "market_value",
    "unrealized_pnl",
    "unrealized_return_pct",
    "position_weight_market",
    "position_status",
    "unrealized_pnl_rank",
    "market_value_rank",
    "unrealized_return_rank",
    "cost_basis_method",
    "valuation_status",
]

REQUIRED_POSITION_SNAPSHOT_COLUMNS = [
    "snapshot_date",
    "symbol",
    "shares",
    "avg_price",
    "cost_value",
    "close_price",
    "market_value",
    "unrealized_pnl",
    "unrealized_pnl_pct",
    "position_status",
]

REQUIRED_ACCOUNT_SNAPSHOT_COLUMNS = [
    "snapshot_date",
    "positions_cost_value",
    "positions_market_value",
    "unrealized_pnl",
    "market_valuation_status",
]

TOLERANCE = 0.05


def _normalize_date(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("snapshot_date is required")
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


def load_paper_position_snapshot_rows(
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
    missing_columns = [column for column in REQUIRED_POSITION_SNAPSHOT_COLUMNS if column not in rows[0]]
    if missing_columns:
        raise ValueError("Missing paper position snapshot columns: " + ", ".join(missing_columns))
    return rows


def load_paper_account_snapshot_rows(
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
    missing_columns = [column for column in REQUIRED_ACCOUNT_SNAPSHOT_COLUMNS if column not in rows[0]]
    if missing_columns:
        raise ValueError("Missing paper account snapshot columns: " + ", ".join(missing_columns))
    return rows


def build_paper_symbol_unrealized_performance(
    position_rows: list[dict[str, str]],
    account_rows: list[dict[str, str]] | None = None,
    tolerance: float = TOLERANCE,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    warnings: list[str] = []
    account_rows = account_rows or []
    if not position_rows:
        warnings.append("No position snapshot rows found in paper_position_snapshot.csv")
        return [], {
            "latest_snapshot_date": "",
            "open_symbol_count": 0,
            "total_market_value": 0.0,
            "total_cost_basis": 0.0,
            "total_unrealized_pnl": 0.0,
            "best_unrealized_pnl_symbols": [],
            "worst_unrealized_pnl_symbols": [],
            "best_unrealized_return_symbols": [],
            "worst_unrealized_return_symbols": [],
            "largest_market_value_symbols": [],
            "account_cross_check": {"status": "not_run", "messages": ["No position rows available"]},
        }, warnings

    normalized_rows = []
    for raw_row in position_rows:
        normalized_rows.append(
            {
                **raw_row,
                "snapshot_date": _normalize_date(raw_row.get("snapshot_date", "")),
            }
        )
    latest_snapshot_date = max(row["snapshot_date"] for row in normalized_rows)
    latest_rows = [
        row for row in normalized_rows
        if row["snapshot_date"] == latest_snapshot_date and str(row.get("position_status", "")).strip().upper() == "OPEN"
    ]
    if not latest_rows:
        warnings.append(f"No OPEN rows found for latest snapshot_date {latest_snapshot_date}")
        return [], {
            "latest_snapshot_date": latest_snapshot_date,
            "open_symbol_count": 0,
            "total_market_value": 0.0,
            "total_cost_basis": 0.0,
            "total_unrealized_pnl": 0.0,
            "best_unrealized_pnl_symbols": [],
            "worst_unrealized_pnl_symbols": [],
            "best_unrealized_return_symbols": [],
            "worst_unrealized_return_symbols": [],
            "largest_market_value_symbols": [],
            "account_cross_check": {"status": "not_run", "messages": [f"No OPEN rows found for latest snapshot_date {latest_snapshot_date}"]},
        }, warnings

    processed_rows: list[dict[str, Any]] = []
    for row in latest_rows:
        shares = _parse_int(row.get("shares", ""), "shares")
        avg_price = _parse_float(row.get("avg_price", ""), "avg_price")
        cost_basis = _parse_float(row.get("cost_value", ""), "cost_value")
        market_price = _parse_float(row.get("close_price", ""), "close_price")
        market_value = _parse_float(row.get("market_value", ""), "market_value")
        unrealized_pnl = _parse_float(row.get("unrealized_pnl", ""), "unrealized_pnl")
        unrealized_return_ratio = _parse_float(row.get("unrealized_pnl_pct", ""), "unrealized_pnl_pct")
        recalculated_unrealized_pnl = market_value - cost_basis
        recalculated_unrealized_return_pct = ((recalculated_unrealized_pnl / cost_basis) * 100.0) if cost_basis > 0 else 0.0
        input_unrealized_return_pct = unrealized_return_ratio * 100.0
        if abs(unrealized_pnl - recalculated_unrealized_pnl) > tolerance:
            warnings.append(
                f"{row['symbol']}: unrealized_pnl input/recalc mismatch ({unrealized_pnl:.2f} vs {recalculated_unrealized_pnl:.2f})"
            )
        if abs(input_unrealized_return_pct - recalculated_unrealized_return_pct) > tolerance:
            warnings.append(
                f"{row['symbol']}: unrealized_return_pct input/recalc mismatch ({input_unrealized_return_pct:.7f} vs {recalculated_unrealized_return_pct:.7f})"
            )
        processed_rows.append(
            {
                "snapshot_date": latest_snapshot_date,
                "symbol": str(row.get("symbol", "")).strip(),
                "shares": shares,
                "avg_price": avg_price,
                "market_price": market_price,
                "cost_basis": cost_basis,
                "market_value": market_value,
                "unrealized_pnl": unrealized_pnl,
                "unrealized_return_pct": input_unrealized_return_pct,
                "position_status": "OPEN",
                "cost_basis_method": COST_BASIS_METHOD,
                "valuation_status": "success",
            }
        )

    total_market_value = sum(float(row["market_value"]) for row in processed_rows)
    total_cost_basis = sum(float(row["cost_basis"]) for row in processed_rows)
    total_unrealized_pnl = sum(float(row["unrealized_pnl"]) for row in processed_rows)

    for row in processed_rows:
        row["position_weight_market"] = (float(row["market_value"]) / total_market_value) if total_market_value > 0 else 0.0

    pnl_ranked = sorted(processed_rows, key=lambda row: (float(row["unrealized_pnl"]), str(row["symbol"])), reverse=True)
    market_ranked = sorted(processed_rows, key=lambda row: (float(row["market_value"]), str(row["symbol"])), reverse=True)
    return_ranked = sorted(processed_rows, key=lambda row: (float(row["unrealized_return_pct"]), str(row["symbol"])), reverse=True)
    for idx, row in enumerate(pnl_ranked, start=1):
        row["unrealized_pnl_rank"] = idx
    for idx, row in enumerate(market_ranked, start=1):
        row["market_value_rank"] = idx
    for idx, row in enumerate(return_ranked, start=1):
        row["unrealized_return_rank"] = idx

    account_cross_check = {"status": "not_run", "messages": []}
    matching_account_rows = []
    if account_rows:
        matching_account_rows = [
            {**row, "snapshot_date": _normalize_date(row.get("snapshot_date", ""))}
            for row in account_rows
            if _normalize_date(row.get("snapshot_date", "")) == latest_snapshot_date
        ]
        if not matching_account_rows:
            warnings.append(f"No account snapshot row found for latest snapshot_date {latest_snapshot_date}")
            account_cross_check = {"status": "warning", "messages": [f"No account snapshot row found for latest snapshot_date {latest_snapshot_date}"]}
        else:
            account_row = matching_account_rows[-1]
            messages: list[str] = []
            status = "passed"
            expected_market = _parse_float(account_row.get("positions_market_value", ""), "positions_market_value")
            expected_cost = _parse_float(account_row.get("positions_cost_value", ""), "positions_cost_value")
            expected_unrealized = _parse_float(account_row.get("unrealized_pnl", ""), "unrealized_pnl")
            if abs(total_market_value - expected_market) > tolerance:
                messages.append(
                    f"positions_market_value mismatch: positions={total_market_value:.2f}, account={expected_market:.2f}"
                )
                status = "warning"
            if abs(total_cost_basis - expected_cost) > tolerance:
                messages.append(
                    f"positions_cost_value mismatch: positions={total_cost_basis:.2f}, account={expected_cost:.2f}"
                )
                status = "warning"
            if abs(total_unrealized_pnl - expected_unrealized) > tolerance:
                messages.append(
                    f"unrealized_pnl mismatch: positions={total_unrealized_pnl:.2f}, account={expected_unrealized:.2f}"
                )
                status = "warning"
            if not messages:
                messages.append("Cross-check passed within tolerance.")
            else:
                warnings.extend(messages)
            account_cross_check = {"status": status, "messages": messages}

    summary_data = {
        "latest_snapshot_date": latest_snapshot_date,
        "open_symbol_count": len(processed_rows),
        "total_market_value": total_market_value,
        "total_cost_basis": total_cost_basis,
        "total_unrealized_pnl": total_unrealized_pnl,
        "best_unrealized_pnl_symbols": pnl_ranked[:3],
        "worst_unrealized_pnl_symbols": list(reversed(pnl_ranked[-3:])),
        "best_unrealized_return_symbols": return_ranked[:3],
        "worst_unrealized_return_symbols": list(reversed(return_ranked[-3:])),
        "largest_market_value_symbols": market_ranked[:3],
        "account_cross_check": account_cross_check,
    }
    processed_rows.sort(key=lambda row: str(row["symbol"]))
    return processed_rows, summary_data, warnings


def _serialize_csv_value(column: str, value: Any) -> Any:
    if column in {"avg_price", "market_price", "cost_basis", "market_value", "unrealized_pnl"} and value != "":
        return f"{float(value):.2f}"
    if column in {"unrealized_return_pct", "position_weight_market"} and value != "":
        return f"{float(value):.7f}"
    return value


def write_paper_symbol_unrealized_performance(
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
        writer = csv.DictWriter(handle, fieldnames=PAPER_SYMBOL_UNREALIZED_PERFORMANCE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    column: _serialize_csv_value(column, row.get(column, ""))
                    for column in PAPER_SYMBOL_UNREALIZED_PERFORMANCE_COLUMNS
                }
            )


def summarize_paper_symbol_unrealized_performance(
    summary_data: dict[str, Any],
    warnings: list[str],
    input_path: Path,
    output_path: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "input_path": str(input_path),
        "output_path": str(output_path),
        "warnings": warnings,
        "limitations": [
            "This report summarizes current open-position unrealized performance only.",
            "Realized PnL and closed trades are not included.",
            "Total symbol performance will be handled in a later MFU.",
            "FIFO/LIFO/lot ledger accounting is not implemented.",
            "open_date and holding_days are intentionally excluded.",
        ],
        **summary_data,
    }


def _format_symbol_rows(rows: list[dict[str, Any]], metric_key: str) -> str:
    if not rows:
        return "-"
    return ", ".join(f"{row['symbol']} ({float(row[metric_key]):.2f})" for row in rows)


def render_paper_symbol_unrealized_performance_summary(summary: dict[str, Any]) -> str:
    cross_check = summary["account_cross_check"]
    lines = [
        "# Paper Symbol Unrealized Performance Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Input file path: {summary['input_path']}",
        f"- Output CSV path: {summary['output_path']}",
        f"- Latest snapshot_date: {summary['latest_snapshot_date'] or 'N/A'}",
        f"- Open symbol count: {summary['open_symbol_count']}",
        f"- Total market value: {summary['total_market_value']:.2f}",
        f"- Total cost basis: {summary['total_cost_basis']:.2f}",
        f"- Total unrealized PnL: {summary['total_unrealized_pnl']:.2f}",
        f"- Best unrealized PnL symbols: {_format_symbol_rows(summary['best_unrealized_pnl_symbols'], 'unrealized_pnl')}",
        f"- Worst unrealized PnL symbols: {_format_symbol_rows(summary['worst_unrealized_pnl_symbols'], 'unrealized_pnl')}",
        f"- Best unrealized return symbols: {_format_symbol_rows(summary['best_unrealized_return_symbols'], 'unrealized_return_pct')}",
        f"- Worst unrealized return symbols: {_format_symbol_rows(summary['worst_unrealized_return_symbols'], 'unrealized_return_pct')}",
        f"- Largest market value symbols: {_format_symbol_rows(summary['largest_market_value_symbols'], 'market_value')}",
        "",
        "## Account Snapshot Cross-Check",
        f"- Status: {cross_check['status']}",
    ]
    lines.extend(f"- {message}" for message in cross_check["messages"])
    lines.extend(["", "## Warnings"])
    if summary["warnings"]:
        lines.extend(f"- {warning}" for warning in summary["warnings"])
    else:
        lines.append("- None")
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def write_paper_symbol_unrealized_performance_summary(
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
