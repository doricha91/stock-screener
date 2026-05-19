from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_realized_trade_journal import (
    COST_BASIS_METHOD,
    ENTRY_BASIS_TYPE,
    LOT_LINKING_STATUS,
)
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


PAPER_REALIZED_RANKING_COLUMNS = [
    "ranking_type",
    "rank",
    "symbol",
    "metric_value",
    "total_realized_pnl",
    "realized_trade_count",
    "win_count",
    "loss_count",
    "flat_count",
    "win_rate",
    "avg_realized_return_pct",
    "profit_factor",
    "note",
]

REQUIRED_SYMBOL_PERFORMANCE_COLUMNS = [
    "symbol",
    "realized_trade_count",
    "total_realized_pnl",
    "win_count",
    "loss_count",
    "flat_count",
    "win_rate",
    "avg_realized_return_pct",
    "profit_factor",
    "cost_basis_method",
    "entry_basis_type",
    "lot_linking_status",
]

SMALL_SAMPLE_THRESHOLD = 2


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


def load_paper_symbol_realized_performance_rows(path: Path) -> list[dict[str, str]]:
    assert_paper_path(path, PAPER_TEST_DIR)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    missing_columns = [column for column in REQUIRED_SYMBOL_PERFORMANCE_COLUMNS if column not in rows[0]]
    if missing_columns:
        raise ValueError("Missing symbol realized performance columns: " + ", ".join(missing_columns))
    return rows


def _small_sample_note(row: dict[str, Any]) -> str:
    count = int(row["realized_trade_count"])
    if count <= SMALL_SAMPLE_THRESHOLD:
        return f"small_sample_trade_count={count}"
    return ""


def _parse_profit_factor(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.lower()
    if normalized in {"n/a", "na", "inf", "+inf", "-inf", "infinity", "+infinity", "-infinity"}:
        return None
    return _parse_float(value, "profit_factor")


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


def _parse_rows(rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    parsed_rows: list[dict[str, Any]] = []
    for raw_row in rows:
        symbol = str(raw_row.get("symbol", "")).strip()
        if not symbol:
            raise ValueError("symbol is required")
        parsed_rows.append(
            {
                "symbol": symbol,
                "realized_trade_count": _parse_int(raw_row.get("realized_trade_count", ""), "realized_trade_count"),
                "total_realized_pnl": _parse_float(raw_row.get("total_realized_pnl", ""), "total_realized_pnl"),
                "win_count": _parse_int(raw_row.get("win_count", ""), "win_count"),
                "loss_count": _parse_int(raw_row.get("loss_count", ""), "loss_count"),
                "flat_count": _parse_int(raw_row.get("flat_count", ""), "flat_count"),
                "win_rate": _parse_float(raw_row.get("win_rate", ""), "win_rate"),
                "avg_realized_return_pct": _parse_float(raw_row.get("avg_realized_return_pct", ""), "avg_realized_return_pct"),
                "profit_factor": _parse_profit_factor(raw_row.get("profit_factor", "")),
                "cost_basis_method": str(raw_row.get("cost_basis_method", "")).strip(),
                "entry_basis_type": str(raw_row.get("entry_basis_type", "")).strip(),
                "lot_linking_status": str(raw_row.get("lot_linking_status", "")).strip(),
            }
        )
    return parsed_rows


def _make_ranking_rows(
    ranking_type: str,
    ranked_rows: list[dict[str, Any]],
    metric_value_getter,
    note_getter=None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index, row in enumerate(ranked_rows, start=1):
        note = note_getter(row) if note_getter is not None else _small_sample_note(row)
        metric_value = metric_value_getter(row)
        result.append(
            {
                "ranking_type": ranking_type,
                "rank": index,
                "symbol": row["symbol"],
                "metric_value": metric_value,
                "total_realized_pnl": row["total_realized_pnl"],
                "realized_trade_count": row["realized_trade_count"],
                "win_count": row["win_count"],
                "loss_count": row["loss_count"],
                "flat_count": row["flat_count"],
                "win_rate": row["win_rate"],
                "avg_realized_return_pct": row["avg_realized_return_pct"],
                "profit_factor": "" if row["profit_factor"] is None else row["profit_factor"],
                "note": note,
            }
        )
    return result


def build_paper_realized_rankings(
    rows: list[dict[str, str]],
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], list[str], dict[str, Any]]:
    cost_basis_method, entry_basis_type, lot_linking_status = _validate_policy(rows)
    warnings: list[str] = []
    parsed_rows = _parse_rows(rows) if rows else []
    if not parsed_rows:
        warnings.append("No symbol realized performance rows found in paper_symbol_realized_performance.csv")

    top_realized = sorted(
        parsed_rows,
        key=lambda row: (row["total_realized_pnl"], row["realized_trade_count"], row["symbol"]),
        reverse=True,
    )
    worst_realized = sorted(
        parsed_rows,
        key=lambda row: (row["total_realized_pnl"], row["realized_trade_count"], row["symbol"]),
    )
    loss_rows = [row for row in parsed_rows if row["total_realized_pnl"] < 0]
    total_abs_loss = sum(abs(row["total_realized_pnl"]) for row in loss_rows)
    if not loss_rows:
        warnings.append("No realized loss symbols")
    loss_contribution = sorted(loss_rows, key=lambda row: abs(row["total_realized_pnl"]), reverse=True)
    win_rate = sorted(
        parsed_rows,
        key=lambda row: (row["win_rate"], row["realized_trade_count"], row["total_realized_pnl"], row["symbol"]),
        reverse=True,
    )
    profit_factor_rows = [row for row in parsed_rows if row["profit_factor"] is not None]
    if len(profit_factor_rows) < len(parsed_rows):
        warnings.append("Some symbols have blank or non-comparable profit_factor values.")
    profit_factor = sorted(
        profit_factor_rows,
        key=lambda row: (row["profit_factor"], row["realized_trade_count"], row["total_realized_pnl"], row["symbol"]),
        reverse=True,
    )
    trade_count = sorted(
        parsed_rows,
        key=lambda row: (row["realized_trade_count"], row["total_realized_pnl"], row["symbol"]),
        reverse=True,
    )

    if any(row["realized_trade_count"] <= SMALL_SAMPLE_THRESHOLD for row in parsed_rows):
        warnings.append(
            f"Some symbols have only {SMALL_SAMPLE_THRESHOLD} or fewer realized trades; ranking interpretation is preliminary."
        )

    rankings = {
        "top_realized_pnl": top_realized,
        "worst_realized_pnl": worst_realized,
        "loss_contribution": loss_contribution,
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "trade_count": trade_count,
    }

    ranking_csv_rows: list[dict[str, Any]] = []
    ranking_csv_rows.extend(
        _make_ranking_rows("top_realized_pnl", top_realized, lambda row: row["total_realized_pnl"])
    )
    ranking_csv_rows.extend(
        _make_ranking_rows("worst_realized_pnl", worst_realized, lambda row: row["total_realized_pnl"])
    )
    ranking_csv_rows.extend(
        _make_ranking_rows(
            "loss_contribution",
            loss_contribution,
            lambda row: (abs(row["total_realized_pnl"]) / total_abs_loss * 100.0) if total_abs_loss > 0 else "",
            note_getter=lambda row: _small_sample_note(row),
        )
    )
    ranking_csv_rows.extend(
        _make_ranking_rows("win_rate", win_rate, lambda row: row["win_rate"] * 100.0)
    )
    ranking_csv_rows.extend(
        _make_ranking_rows("profit_factor", profit_factor, lambda row: row["profit_factor"])
    )
    ranking_csv_rows.extend(
        _make_ranking_rows("trade_count", trade_count, lambda row: row["realized_trade_count"])
    )

    overall = {
        "symbol_count": len(parsed_rows),
        "total_realized_trade_count": sum(row["realized_trade_count"] for row in parsed_rows),
        "total_realized_pnl": sum(row["total_realized_pnl"] for row in parsed_rows),
        "total_win_count": sum(row["win_count"] for row in parsed_rows),
        "total_loss_count": sum(row["loss_count"] for row in parsed_rows),
        "total_flat_count": sum(row["flat_count"] for row in parsed_rows),
        "overall_win_rate": (
            sum(row["win_count"] for row in parsed_rows)
            / sum(row["realized_trade_count"] for row in parsed_rows)
            * 100.0
        ) if parsed_rows else 0.0,
        "cost_basis_method": cost_basis_method,
        "entry_basis_type": entry_basis_type,
        "lot_linking_status": lot_linking_status,
        "total_abs_loss": total_abs_loss,
    }
    return rankings, ranking_csv_rows, warnings, overall


def _serialize_csv_value(column: str, value: Any) -> Any:
    if column in {"metric_value", "total_realized_pnl", "avg_realized_return_pct", "profit_factor"} and value != "":
        return f"{float(value):.7f}" if column != "total_realized_pnl" else f"{float(value):.2f}"
    if column == "win_rate" and value != "":
        return f"{float(value):.7f}"
    return value


def write_paper_realized_ranking_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    assert_paper_path(output_path, PAPER_TEST_DIR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_REALIZED_RANKING_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {column: _serialize_csv_value(column, row.get(column, "")) for column in PAPER_REALIZED_RANKING_COLUMNS}
            )


def summarize_paper_realized_ranking_report(
    rankings: dict[str, list[dict[str, Any]]],
    warnings: list[str],
    overall: dict[str, Any],
    input_path: Path,
    output_csv_path: Path,
    output_markdown_path: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "input_path": str(input_path),
        "output_csv_path": str(output_csv_path),
        "output_markdown_path": str(output_markdown_path),
        "rankings": rankings,
        "warnings": warnings,
        "limitations": [
            "This report summarizes realized SELL-event performance only.",
            "Open positions and unrealized PnL are not included.",
            "FIFO/LIFO/lot ledger accounting is not implemented.",
            "open_date and holding_days are intentionally excluded.",
            "Metrics are preliminary when realized trade count is small.",
        ],
        **overall,
    }


def _render_table(rows: list[dict[str, Any]], metric_name: str, metric_getter) -> list[str]:
    lines = [
        "| Rank | Symbol | " + metric_name + " | Realized Trade Count | Win Rate | Avg Realized Return Pct | Profit Factor |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for idx, row in enumerate(rows, start=1):
        profit_factor = "N/A" if row["profit_factor"] is None else f"{float(row['profit_factor']):.7f}"
        lines.append(
            f"| {idx} | {row['symbol']} | {metric_getter(row)} | {row['realized_trade_count']} | "
            f"{float(row['win_rate']) * 100:.2f}% | {float(row['avg_realized_return_pct']):.7f}% | {profit_factor} |"
        )
    if not rows:
        lines.append("| - | - | - | - | - | - | - |")
    return lines


def render_paper_realized_ranking_report(summary: dict[str, Any]) -> str:
    rankings = summary["rankings"]
    lines = [
        "# Paper Realized Ranking Report",
        "",
        "## Summary",
        f"- Generated at: {summary['generated_at']}",
        f"- Input file path: {summary['input_path']}",
        f"- Symbol count: {summary['symbol_count']}",
        f"- Total realized trade count: {summary['total_realized_trade_count']}",
        f"- Total realized PnL: {summary['total_realized_pnl']:.2f}",
        f"- Overall win/loss/flat count: {summary['total_win_count']} / {summary['total_loss_count']} / {summary['total_flat_count']}",
        f"- Overall win rate: {summary['overall_win_rate']:.2f}%",
        f"- Cost basis method: {summary['cost_basis_method']}",
        f"- Entry basis type: {summary['entry_basis_type']}",
        f"- Lot linking status: {summary['lot_linking_status']}",
        "",
        "## Top / Worst Realized PnL Symbols",
        "",
        "### Top Realized PnL",
    ]
    lines.extend(
        _render_table(
            rankings["top_realized_pnl"],
            "Total Realized PnL",
            lambda row: f"{float(row['total_realized_pnl']):.2f}",
        )
    )
    lines.extend(["", "### Worst Realized PnL"])
    lines.extend(
        _render_table(
            rankings["worst_realized_pnl"],
            "Total Realized PnL",
            lambda row: f"{float(row['total_realized_pnl']):.2f}",
        )
    )
    lines.extend(["", "## Loss Contribution Ranking"])
    if summary["total_abs_loss"] <= 0 or not rankings["loss_contribution"]:
        lines.append("- No realized loss symbols")
    else:
        lines.extend(
            _render_table(
                rankings["loss_contribution"],
                "Loss Contribution Pct",
                lambda row: f"{abs(float(row['total_realized_pnl'])) / summary['total_abs_loss'] * 100.0:.2f}%",
            )
        )
    lines.extend(["", "## Win Rate Ranking"])
    lines.extend(
        _render_table(
            rankings["win_rate"],
            "Win Rate",
            lambda row: f"{float(row['win_rate']) * 100:.2f}%",
        )
    )
    lines.extend(["", "## Profit Factor Ranking"])
    if not rankings["profit_factor"]:
        lines.append("- No comparable profit factor symbols")
    else:
        lines.extend(
            _render_table(
                rankings["profit_factor"],
                "Profit Factor",
                lambda row: f"{float(row['profit_factor']):.7f}",
            )
        )
    lines.extend(["", "## Trade Count Ranking"])
    lines.extend(
        _render_table(
            rankings["trade_count"],
            "Realized Trade Count",
            lambda row: str(row["realized_trade_count"]),
        )
    )
    lines.extend(["", "## Warnings"])
    if summary["warnings"]:
        lines.extend(f"- {warning}" for warning in summary["warnings"])
    else:
        lines.append("- None")
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def write_paper_realized_ranking_report(markdown: str, output_path: Path) -> None:
    assert_paper_path(output_path, PAPER_TEST_DIR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
