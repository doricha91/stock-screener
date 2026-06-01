from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_guard import assert_path_under_account_root
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


PAPER_SYMBOL_REVIEW_WORKSHEET_COLUMNS = [
    "symbol",
    "review_bucket",
    "review_priority",
    "sample_size_flag",
    "symbol_status",
    "is_actionable",
    "question_id",
    "question_text",
    "question_category",
    "requires_manual_answer",
]

REQUIRED_REVIEW_BUCKET_COLUMNS = [
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

QUESTION_TEMPLATES = {
    "review_loss": [
        "진입 신호가 원래 전략 조건과 일치했는가?",
        "손실 발생 전 market regime 변화가 있었는가?",
        "청산 rule 또는 stop rule은 정상 작동했는가?",
        "포지션 크기가 과하지 않았는가?",
        "같은 조건이 반복되면 피해야 하는가, 아니면 표본 부족인가?",
    ],
    "track_realized_gain": [
        "수익 거래의 진입 조건은 재현 가능한가?",
        "exit rule이 너무 빠르거나 늦지 않았는가?",
        "수익이 특정 시장 국면에 의존했는가?",
        "같은 조건을 전략 규칙으로 강화할 근거가 있는가?",
        "표본 수가 충분한가?",
    ],
    "monitor_open_gain": [
        "현재 평가이익이 exit rule 또는 trailing stop과 어떤 관계인가?",
        "이익이 특정 종목에 과도하게 집중되어 있지 않은가?",
        "다음 EOD update에서 신호 변화가 있었는가?",
        "보유 근거가 아직 유효한가?",
        "평가이익을 확정 수익으로 오해하고 있지 않은가?",
    ],
    "monitor_open_loss": [
        "현재 평가손실이 stop 기준에 가까운가?",
        "손실이 market regime 변화와 관련 있는가?",
        "포지션 크기가 과하지 않은가?",
        "신규 매수 제한 또는 리스크 관리 조건에 걸리는가?",
        "손실을 과소평가하고 있지 않은가?",
    ],
    "neutral": [
        "손익이 중립 범위에 있는 이유가 무엇인가?",
        "아직 판단할 만큼 이벤트가 충분한가?",
        "다음 snapshot에서 gain/loss bucket으로 이동할 가능성이 있는가?",
        "리뷰 우선순위를 낮게 둬도 되는가?",
    ],
}

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
BUCKET_ORDER = {
    "review_loss": 0,
    "monitor_open_loss": 1,
    "monitor_open_gain": 2,
    "track_realized_gain": 3,
    "neutral": 4,
}


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


def load_paper_symbol_review_bucket_rows(
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
    missing = [column for column in REQUIRED_REVIEW_BUCKET_COLUMNS if column not in rows[0]]
    if missing:
        raise ValueError("Missing paper symbol review bucket columns: " + ", ".join(missing))
    return rows


def build_paper_symbol_review_worksheet(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[str]]:
    warnings: list[str] = []
    symbols: list[dict[str, Any]] = []

    for raw_row in rows:
        symbol = str(raw_row.get("symbol", "")).strip()
        if not symbol:
            raise ValueError("symbol is required")
        review_bucket = str(raw_row.get("review_bucket", "")).strip()
        if review_bucket not in QUESTION_TEMPLATES:
            raise ValueError(f"unsupported review_bucket: {review_bucket}")
        review_priority = str(raw_row.get("review_priority", "")).strip()
        symbols.append(
            {
                "symbol": symbol,
                "symbol_status": str(raw_row.get("symbol_status", "")).strip(),
                "review_bucket": review_bucket,
                "review_priority": review_priority,
                "is_actionable": "false",
                "sample_size_flag": str(raw_row.get("sample_size_flag", "")).strip(),
                "review_reason": str(raw_row.get("review_reason", "")).strip(),
                "realized_pnl": _parse_float(raw_row.get("realized_pnl", ""), "realized_pnl"),
                "unrealized_pnl": _parse_float(raw_row.get("unrealized_pnl", ""), "unrealized_pnl"),
                "total_pnl": _parse_float(raw_row.get("total_pnl", ""), "total_pnl"),
                "realized_trade_count": _parse_int(raw_row.get("realized_trade_count", ""), "realized_trade_count"),
                "win_rate": _parse_float(raw_row.get("win_rate", ""), "win_rate"),
                "avg_realized_return_pct": _parse_float(raw_row.get("avg_realized_return_pct", ""), "avg_realized_return_pct"),
                "open_shares": _parse_int(raw_row.get("open_shares", ""), "open_shares"),
                "open_market_value": _parse_float(raw_row.get("open_market_value", ""), "open_market_value"),
                "open_unrealized_return_pct": _parse_float(raw_row.get("open_unrealized_return_pct", ""), "open_unrealized_return_pct"),
                "position_weight_market": _parse_float(raw_row.get("position_weight_market", ""), "position_weight_market"),
                "neutral_threshold_pct": _parse_float(raw_row.get("neutral_threshold_pct", ""), "neutral_threshold_pct"),
            }
        )

    symbols.sort(
        key=lambda row: (
            PRIORITY_ORDER.get(row["review_priority"], 99),
            BUCKET_ORDER.get(row["review_bucket"], 99),
            float(row["total_pnl"]),
            str(row["symbol"]),
        )
    )

    question_rows: list[dict[str, Any]] = []
    for symbol_row in symbols:
        for index, question in enumerate(QUESTION_TEMPLATES[symbol_row["review_bucket"]], start=1):
            question_rows.append(
                {
                    "symbol": symbol_row["symbol"],
                    "review_bucket": symbol_row["review_bucket"],
                    "review_priority": symbol_row["review_priority"],
                    "sample_size_flag": symbol_row["sample_size_flag"],
                    "symbol_status": symbol_row["symbol_status"],
                    "is_actionable": "false",
                    "question_id": f"{symbol_row['review_bucket']}_{index}",
                    "question_text": question,
                    "question_category": symbol_row["review_bucket"],
                    "requires_manual_answer": "true",
                }
            )
        if symbol_row["sample_size_flag"] == "low_sample":
            warnings.append(f"{symbol_row['symbol']}: low_sample worksheet interpretation requires caution")

    bucket_counts = Counter(row["review_bucket"] for row in symbols)
    priority_counts = Counter(row["review_priority"] for row in symbols)
    summary_data = {
        "symbol_count": len(symbols),
        "bucket_counts": dict(bucket_counts),
        "priority_counts": dict(priority_counts),
        "high_priority_symbols": [row["symbol"] for row in symbols if row["review_priority"] == "high"],
        "low_sample_symbols": [row["symbol"] for row in symbols if row["sample_size_flag"] == "low_sample"],
        "neutral_threshold_pct": symbols[0]["neutral_threshold_pct"] if symbols else 0.5,
        "is_actionable": "false",
    }
    return symbols, question_rows, summary_data, warnings


def write_paper_symbol_review_worksheet_csv(
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
        writer = csv.DictWriter(handle, fieldnames=PAPER_SYMBOL_REVIEW_WORKSHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def summarize_paper_symbol_review_worksheet(
    summary_data: dict[str, Any],
    warnings: list[str],
    input_path: Path,
    markdown_output_path: Path,
    csv_output_path: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "input_path": str(input_path),
        "markdown_output_path": str(markdown_output_path),
        "csv_output_path": str(csv_output_path),
        "warnings": warnings,
        "limitations": [
            "This worksheet is non-actionable.",
            "It does not recommend buy/sell/hold actions.",
            "It is designed for manual review and post-trade analysis.",
            "Realized PnL is average-cost SELL-event based.",
            "Unrealized PnL is current open-position snapshot based.",
            "total_pnl is a reference metric only.",
            "FIFO/LIFO/lot ledger accounting is not implemented.",
            "open_date and holding_days are excluded.",
        ],
        **summary_data,
    }


def render_paper_symbol_review_worksheet_summary(
    summary: dict[str, Any],
    symbol_rows: list[dict[str, Any]],
) -> str:
    bucket_counts = summary["bucket_counts"]
    priority_counts = summary["priority_counts"]
    lines = [
        "# Paper Symbol Review Worksheet",
        "",
        "## Header",
        f"- Generated at: {summary['generated_at']}",
        f"- Input file path: {summary['input_path']}",
        f"- Markdown output file path: {summary['markdown_output_path']}",
        f"- CSV output file path: {summary['csv_output_path']}",
        f"- is_actionable: {summary['is_actionable']}",
        f"- neutral_threshold_pct: {float(summary['neutral_threshold_pct']):.1f}",
        "",
        "## Summary",
        f"- Total symbol count: {summary['symbol_count']}",
        f"- review_loss count: {bucket_counts.get('review_loss', 0)}",
        f"- track_realized_gain count: {bucket_counts.get('track_realized_gain', 0)}",
        f"- monitor_open_gain count: {bucket_counts.get('monitor_open_gain', 0)}",
        f"- monitor_open_loss count: {bucket_counts.get('monitor_open_loss', 0)}",
        f"- neutral count: {bucket_counts.get('neutral', 0)}",
        f"- high priority count: {priority_counts.get('high', 0)}",
        f"- medium priority count: {priority_counts.get('medium', 0)}",
        f"- low priority count: {priority_counts.get('low', 0)}",
        f"- High priority symbols: {'|'.join(summary['high_priority_symbols']) if summary['high_priority_symbols'] else '-'}",
        f"- low_sample symbols: {'|'.join(summary['low_sample_symbols']) if summary['low_sample_symbols'] else '-'}",
        "",
        "## Review Queue",
    ]
    if not symbol_rows:
        lines.append("- No symbols available")
    else:
        lines.extend(
            [
                "| Symbol | Bucket | Priority | Sample Size | Status | Realized PnL | Unrealized PnL | Total PnL | Realized Trade Count | Open Market Value | Actionable |",
                "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for row in symbol_rows:
            lines.append(
                f"| {row['symbol']} | {row['review_bucket']} | {row['review_priority']} | {row['sample_size_flag']} | "
                f"{row['symbol_status']} | {float(row['realized_pnl']):.2f} | {float(row['unrealized_pnl']):.2f} | "
                f"{float(row['total_pnl']):.2f} | {row['realized_trade_count']} | {float(row['open_market_value']):.2f} | "
                f"{row['is_actionable']} |"
            )

    lines.extend(["", "## Symbol Worksheets"])
    for row in symbol_rows:
        lines.extend(
            [
                "",
                f"## {row['symbol']}",
                "",
                f"- Bucket: {row['review_bucket']}",
                f"- Priority: {row['review_priority']}",
                f"- Sample Size: {row['sample_size_flag']}",
                f"- Actionable: {row['is_actionable']}",
                f"- Realized PnL: {float(row['realized_pnl']):.2f}",
                f"- Unrealized PnL: {float(row['unrealized_pnl']):.2f}",
                f"- Total PnL: {float(row['total_pnl']):.2f}",
                "",
                "### Review Checklist",
            ]
        )
        for question in QUESTION_TEMPLATES[row["review_bucket"]]:
            lines.append(f"- [ ] {question}")
        if row["sample_size_flag"] == "low_sample":
            lines.append("- [ ] 표본 부족으로 과잉해석하고 있지 않은가?")
        lines.extend(["", "### Notes", "", "- "])

    lines.extend(["", "## Warnings"])
    if summary["warnings"]:
        lines.extend(f"- {warning}" for warning in summary["warnings"])
    else:
        lines.append("- None")
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def write_paper_symbol_review_worksheet_markdown(
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
