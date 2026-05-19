from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS = [
    "review_date",
    "symbol",
    "review_bucket",
    "review_priority",
    "sample_size_flag",
    "symbol_status",
    "question_id",
    "question_text",
    "question_category",
    "is_actionable",
    "manual_answer",
    "review_status",
    "follow_up_needed",
    "review_tag",
    "reviewer_note",
    "source_worksheet_path",
    "created_at",
]

REQUIRED_WORKSHEET_COLUMNS = [
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

REQUIRED_BUCKET_COLUMNS = [
    "symbol",
    "review_bucket",
    "review_priority",
    "sample_size_flag",
    "symbol_status",
    "is_actionable",
]


def load_csv_rows(path: Path, required_columns: list[str], label: str) -> list[dict[str, str]]:
    assert_paper_path(path, PAPER_TEST_DIR)
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    missing = [column for column in required_columns if column not in rows[0]]
    if missing:
        raise ValueError(f"Missing {label} columns: " + ", ".join(missing))
    return rows


def build_paper_manual_review_log_template(
    worksheet_rows: list[dict[str, str]],
    review_bucket_rows: list[dict[str, str]],
    source_worksheet_path: Path,
    review_date: str | None = None,
    created_at: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    normalized_review_date = review_date or datetime.now().strftime("%Y-%m-%d")
    created_at_value = created_at or datetime.now().isoformat(timespec="seconds")
    bucket_by_symbol = {
        str(row.get("symbol", "")).strip(): row
        for row in review_bucket_rows
    }
    warnings: list[str] = []
    output_rows: list[dict[str, Any]] = []

    for row in worksheet_rows:
        symbol = str(row.get("symbol", "")).strip()
        question_category = str(row.get("question_category", "")).strip()
        if not symbol:
            raise ValueError("symbol is required")
        bucket_row = bucket_by_symbol.get(symbol)
        if bucket_row is None:
            raise ValueError(f"Missing review bucket row for symbol: {symbol}")

        output_rows.append(
            {
                "review_date": normalized_review_date,
                "symbol": symbol,
                "review_bucket": str(bucket_row.get("review_bucket", "")).strip(),
                "review_priority": str(bucket_row.get("review_priority", "")).strip(),
                "sample_size_flag": str(bucket_row.get("sample_size_flag", "")).strip(),
                "symbol_status": str(bucket_row.get("symbol_status", "")).strip(),
                "question_id": str(row.get("question_id", "")).strip(),
                "question_text": str(row.get("question_text", "")).strip(),
                "question_category": question_category,
                "is_actionable": "false",
                "manual_answer": "",
                "review_status": "pending",
                "follow_up_needed": "false",
                "review_tag": "",
                "reviewer_note": "",
                "source_worksheet_path": str(source_worksheet_path),
                "created_at": created_at_value,
            }
        )

    summary_data = {
        "review_template_row_count": len(output_rows),
        "symbol_count": len({row["symbol"] for row in output_rows}),
        "bucket_counts": dict(Counter(row["review_bucket"] for row in output_rows)),
        "priority_counts": dict(Counter(row["review_priority"] for row in output_rows)),
        "high_priority_symbols": sorted({row["symbol"] for row in output_rows if row["review_priority"] == "high"}),
        "is_actionable": "false",
        "review_date": normalized_review_date,
        "source_worksheet_path": str(source_worksheet_path),
    }
    return output_rows, summary_data, warnings


def write_paper_manual_review_log_template_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    assert_paper_path(output_path, PAPER_TEST_DIR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def summarize_paper_manual_review_log_template(
    summary_data: dict[str, Any],
    warnings: list[str],
    worksheet_csv_path: Path,
    review_bucket_csv_path: Path,
    csv_output_path: Path,
    markdown_output_path: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "worksheet_csv_path": str(worksheet_csv_path),
        "review_bucket_csv_path": str(review_bucket_csv_path),
        "csv_output_path": str(csv_output_path),
        "markdown_output_path": str(markdown_output_path),
        "warnings": warnings,
        "limitations": [
            "This is a manual review log template.",
            "It does not recommend buy/sell/hold actions.",
            "is_actionable = false",
            "This template is for manual review logging only.",
            "Validation, append workflow, weekly rollup, and backlog integration are not implemented in this MFU.",
        ],
        **summary_data,
    }


def render_paper_manual_review_log_template_markdown(summary: dict[str, Any]) -> str:
    bucket_counts = summary["bucket_counts"]
    priority_counts = summary["priority_counts"]
    lines = [
        "# Paper Manual Review Log Template",
        "",
        "## Header",
        f"- Generated at: {summary['generated_at']}",
        f"- Worksheet CSV input path: {summary['worksheet_csv_path']}",
        f"- Review bucket CSV input path: {summary['review_bucket_csv_path']}",
        f"- CSV output path: {summary['csv_output_path']}",
        f"- Markdown output path: {summary['markdown_output_path']}",
        "- This is a manual review log template.",
        "- It does not recommend buy/sell/hold actions.",
        f"- is_actionable = {summary['is_actionable']}",
        "",
        "## Purpose",
        "- Capture manual answers to worksheet questions in a structured CSV format.",
        "- Preserve a non-actionable post-trade review workflow.",
        "",
        "## How to Use",
        "1. Fill in `manual_answer` in the CSV.",
        "2. Enter `review_status` manually using one of: pending, reviewed, deferred, not_applicable.",
        "3. Set `follow_up_needed` to true when additional review is required.",
        "4. Use `review_tag` for manual tags such as entry_rule, exit_rule, position_sizing, market_regime, or data_quality.",
        "5. This template is for review logging only, not for trade instructions.",
        "",
        "## Review Log Fields",
        "- Auto-generated fields: review_date, symbol, review_bucket, review_priority, sample_size_flag, symbol_status, question_id, question_text, question_category, is_actionable, source_worksheet_path, created_at",
        "- Manual input fields: manual_answer, review_status, follow_up_needed, review_tag, reviewer_note",
        "",
        "## Pending Review Items",
        f"- Template row count: {summary['review_template_row_count']}",
        f"- Symbol count: {summary['symbol_count']}",
        f"- review_loss rows: {bucket_counts.get('review_loss', 0)}",
        f"- track_realized_gain rows: {bucket_counts.get('track_realized_gain', 0)}",
        f"- monitor_open_gain rows: {bucket_counts.get('monitor_open_gain', 0)}",
        f"- monitor_open_loss rows: {bucket_counts.get('monitor_open_loss', 0)}",
        f"- neutral rows: {bucket_counts.get('neutral', 0)}",
        f"- high priority rows: {priority_counts.get('high', 0)}",
        f"- medium priority rows: {priority_counts.get('medium', 0)}",
        f"- low priority rows: {priority_counts.get('low', 0)}",
        f"- High priority symbols: {'|'.join(summary['high_priority_symbols']) if summary['high_priority_symbols'] else '-'}",
        f"- Review date default: {summary['review_date']}",
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


def write_markdown(path: Path, markdown: str) -> None:
    assert_paper_path(path, PAPER_TEST_DIR)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
