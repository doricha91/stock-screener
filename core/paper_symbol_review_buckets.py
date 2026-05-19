from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


PAPER_SYMBOL_REVIEW_BUCKET_COLUMNS = [
    "symbol",
    "symbol_status",
    "review_bucket",
    "review_priority",
    "is_actionable",
    "sample_size_flag",
    "review_reason",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "realized_trade_count",
    "win_rate",
    "avg_realized_return_pct",
    "open_shares",
    "open_market_value",
    "open_unrealized_return_pct",
    "position_weight_market",
    "neutral_threshold_pct",
]

REQUIRED_SIDE_BY_SIDE_COLUMNS = [
    "symbol",
    "symbol_status",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "realized_trade_count",
    "win_rate",
    "avg_realized_return_pct",
    "open_shares",
    "open_market_value",
    "open_unrealized_return_pct",
    "position_weight_market",
]

NEUTRAL_THRESHOLD_PCT = 0.5


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


def load_paper_symbol_side_by_side_performance_rows(path: Path) -> list[dict[str, str]]:
    assert_paper_path(path, PAPER_TEST_DIR)
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    missing = [column for column in REQUIRED_SIDE_BY_SIDE_COLUMNS if column not in rows[0]]
    if missing:
        raise ValueError("Missing paper symbol side-by-side performance columns: " + ", ".join(missing))
    return rows


def _sample_size_flag(realized_trade_count: int) -> str:
    if realized_trade_count == 0:
        return "no_realized_trades"
    if realized_trade_count < 3:
        return "low_sample"
    return "enough_sample"


def _review_priority(review_bucket: str) -> str:
    if review_bucket in {"review_loss", "monitor_open_loss"}:
        return "high"
    if review_bucket in {"monitor_open_gain", "track_realized_gain"}:
        return "medium"
    return "low"


def _bucket_and_reason(
    open_market_value: float,
    open_unrealized_return_pct: float,
    realized_pnl: float,
    avg_realized_return_pct: float,
    neutral_threshold_pct: float,
) -> tuple[str, str]:
    if open_market_value > 0 and open_unrealized_return_pct > neutral_threshold_pct:
        return "monitor_open_gain", "open position has unrealized gain above neutral threshold"
    if open_market_value > 0 and open_unrealized_return_pct < -neutral_threshold_pct:
        return "monitor_open_loss", "open position has unrealized loss below neutral threshold"
    if open_market_value > 0:
        return "neutral", "performance is within neutral threshold or lacks strong signal"
    if realized_pnl > 0 and avg_realized_return_pct > neutral_threshold_pct:
        return "track_realized_gain", "realized gain exceeds neutral threshold; review repeatable signal pattern"
    if realized_pnl < 0 and avg_realized_return_pct < -neutral_threshold_pct:
        return "review_loss", "realized loss exceeds neutral threshold; review entry/exit quality"
    return "neutral", "performance is within neutral threshold or lacks strong signal"


def build_paper_symbol_review_buckets(
    rows: list[dict[str, str]],
    neutral_threshold_pct: float = NEUTRAL_THRESHOLD_PCT,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    warnings: list[str] = []
    output_rows: list[dict[str, Any]] = []

    for raw_row in rows:
        symbol = str(raw_row.get("symbol", "")).strip()
        if not symbol:
            raise ValueError("symbol is required")
        realized_pnl = _parse_float(raw_row.get("realized_pnl", ""), "realized_pnl")
        unrealized_pnl = _parse_float(raw_row.get("unrealized_pnl", ""), "unrealized_pnl")
        total_pnl = _parse_float(raw_row.get("total_pnl", ""), "total_pnl")
        realized_trade_count = _parse_int(raw_row.get("realized_trade_count", ""), "realized_trade_count")
        win_rate = _parse_float(raw_row.get("win_rate", ""), "win_rate")
        avg_realized_return_pct = _parse_float(raw_row.get("avg_realized_return_pct", ""), "avg_realized_return_pct")
        open_shares = _parse_int(raw_row.get("open_shares", ""), "open_shares")
        open_market_value = _parse_float(raw_row.get("open_market_value", ""), "open_market_value")
        open_unrealized_return_pct = _parse_float(raw_row.get("open_unrealized_return_pct", ""), "open_unrealized_return_pct")
        position_weight_market = _parse_float(raw_row.get("position_weight_market", ""), "position_weight_market")

        review_bucket, review_reason = _bucket_and_reason(
            open_market_value,
            open_unrealized_return_pct,
            realized_pnl,
            avg_realized_return_pct,
            neutral_threshold_pct,
        )
        sample_size_flag = _sample_size_flag(realized_trade_count)
        if sample_size_flag == "low_sample":
            warnings.append(f"{symbol}: low_sample realized trade count ({realized_trade_count})")

        output_rows.append(
            {
                "symbol": symbol,
                "symbol_status": str(raw_row.get("symbol_status", "")).strip(),
                "review_bucket": review_bucket,
                "review_priority": _review_priority(review_bucket),
                "is_actionable": "false",
                "sample_size_flag": sample_size_flag,
                "review_reason": review_reason,
                "realized_pnl": realized_pnl,
                "unrealized_pnl": unrealized_pnl,
                "total_pnl": total_pnl,
                "realized_trade_count": realized_trade_count,
                "win_rate": win_rate,
                "avg_realized_return_pct": avg_realized_return_pct,
                "open_shares": open_shares,
                "open_market_value": open_market_value,
                "open_unrealized_return_pct": open_unrealized_return_pct,
                "position_weight_market": position_weight_market,
                "neutral_threshold_pct": neutral_threshold_pct,
            }
        )

    bucket_counts = Counter(row["review_bucket"] for row in output_rows)
    priority_counts = Counter(row["review_priority"] for row in output_rows)
    high_priority_symbols = [row["symbol"] for row in output_rows if row["review_priority"] == "high"]
    low_sample_symbols = [row["symbol"] for row in output_rows if row["sample_size_flag"] == "low_sample"]
    summary_data = {
        "neutral_threshold_pct": neutral_threshold_pct,
        "bucket_counts": dict(bucket_counts),
        "priority_counts": dict(priority_counts),
        "high_priority_symbols": high_priority_symbols,
        "low_sample_symbols": low_sample_symbols,
        "is_actionable": "false",
    }
    output_rows.sort(key=lambda row: str(row["symbol"]))
    return output_rows, summary_data, warnings


def _serialize_csv_value(column: str, value: Any) -> Any:
    if column in {
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
    } and value != "":
        return f"{float(value):.2f}"
    if column in {
        "win_rate",
        "avg_realized_return_pct",
        "open_market_value",
        "open_unrealized_return_pct",
        "position_weight_market",
        "neutral_threshold_pct",
    } and value != "":
        return f"{float(value):.7f}"
    return value


def write_paper_symbol_review_buckets(rows: list[dict[str, Any]], output_path: Path) -> None:
    assert_paper_path(output_path, PAPER_TEST_DIR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_SYMBOL_REVIEW_BUCKET_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {column: _serialize_csv_value(column, row.get(column, "")) for column in PAPER_SYMBOL_REVIEW_BUCKET_COLUMNS}
            )


def summarize_paper_symbol_review_buckets(
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
            "This is a non-actionable review classification report.",
            "It does not recommend buy/sell/hold actions.",
            "Realized PnL is average-cost SELL-event based.",
            "Unrealized PnL is current open-position snapshot based.",
            "total_pnl is a reference metric only.",
            "FIFO/LIFO/lot ledger accounting is not implemented.",
            "open_date and holding_days are excluded.",
        ],
        **summary_data,
    }


def render_paper_symbol_review_buckets_summary(summary: dict[str, Any]) -> str:
    bucket_counts = summary["bucket_counts"]
    priority_counts = summary["priority_counts"]
    lines = [
        "# Paper Symbol Review Buckets Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Input file path: {summary['input_path']}",
        f"- Output CSV path: {summary['output_path']}",
        f"- neutral_threshold_pct: {float(summary['neutral_threshold_pct']):.1f}",
        f"- review_loss count: {bucket_counts.get('review_loss', 0)}",
        f"- track_realized_gain count: {bucket_counts.get('track_realized_gain', 0)}",
        f"- monitor_open_gain count: {bucket_counts.get('monitor_open_gain', 0)}",
        f"- monitor_open_loss count: {bucket_counts.get('monitor_open_loss', 0)}",
        f"- neutral count: {bucket_counts.get('neutral', 0)}",
        f"- high priority count: {priority_counts.get('high', 0)}",
        f"- medium priority count: {priority_counts.get('medium', 0)}",
        f"- low priority count: {priority_counts.get('low', 0)}",
        f"- high priority symbols: {'|'.join(summary['high_priority_symbols']) if summary['high_priority_symbols'] else '-'}",
        f"- low_sample symbols: {'|'.join(summary['low_sample_symbols']) if summary['low_sample_symbols'] else '-'}",
        f"- is_actionable: {summary['is_actionable']}",
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


def write_paper_symbol_review_buckets_summary(markdown: str, output_path: Path) -> None:
    assert_paper_path(output_path, PAPER_TEST_DIR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
