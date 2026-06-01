from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_guard import assert_path_under_account_root
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_manual_review_log_validator import (
    load_paper_manual_review_log_rows,
    validate_paper_manual_review_log_rows,
)
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


APPENDABLE_REVIEW_STATUS = {"reviewed", "deferred", "not_applicable"}
APPEND_ISSUE_COLUMNS = [
    "severity",
    "row_number",
    "symbol",
    "question_id",
    "issue_code",
    "message",
]


def load_existing_paper_manual_review_log_rows(path: Path, allowed_root: Path | None = None) -> list[dict[str, str]]:
    if allowed_root is None:
        assert_paper_path(path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(path, allowed_root)
    if not path.exists():
        return []
    return load_paper_manual_review_log_rows(path, allowed_root=allowed_root)


def _append_issue(
    severity: str,
    row_number: int,
    row: dict[str, str],
    issue_code: str,
    message: str,
) -> dict[str, str]:
    return {
        "severity": severity,
        "row_number": str(row_number),
        "symbol": str(row.get("symbol", "")).strip(),
        "question_id": str(row.get("question_id", "")).strip(),
        "issue_code": issue_code,
        "message": message,
    }


def _review_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        str(row.get("review_date", "")).strip(),
        str(row.get("symbol", "")).strip(),
        str(row.get("question_id", "")).strip(),
    )


def build_paper_manual_review_log_append_plan(
    template_rows: list[dict[str, str]],
    existing_log_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    existing_keys = {_review_key(row) for row in existing_log_rows}
    seen_batch_keys: set[tuple[str, str, str]] = set()
    append_rows: list[dict[str, str]] = []
    append_issues: list[dict[str, str]] = []
    appended_symbols: set[str] = set()
    skipped_duplicate_keys: list[str] = []
    rows_skipped_pending = 0
    rows_skipped_duplicate = 0
    rows_skipped_invalid = 0

    for row_number, row in enumerate(template_rows, start=2):
        review_status = str(row.get("review_status", "")).strip()
        key = _review_key(row)
        key_display = "|".join(key)

        if review_status == "pending":
            rows_skipped_pending += 1
            append_issues.append(
                _append_issue(
                    "warning",
                    row_number,
                    row,
                    "skipped_pending",
                    "pending rows are intentionally excluded from append",
                )
            )
            continue

        if review_status not in APPENDABLE_REVIEW_STATUS:
            rows_skipped_invalid += 1
            append_issues.append(
                _append_issue(
                    "warning",
                    row_number,
                    row,
                    "skipped_invalid_review_status",
                    "row is not appendable because review_status is outside the allowed append set",
                )
            )
            continue

        if key in existing_keys or key in seen_batch_keys:
            rows_skipped_duplicate += 1
            skipped_duplicate_keys.append(key_display)
            append_issues.append(
                _append_issue(
                    "warning",
                    row_number,
                    row,
                    "skipped_duplicate",
                    "duplicate append key detected; existing rows are not overwritten",
                )
            )
            continue

        seen_batch_keys.add(key)
        append_rows.append({column: str(row.get(column, "")) for column in PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS})
        appended_symbols.add(str(row.get("symbol", "")).strip())

    summary = {
        "rows_considered_for_append": sum(
            1 for row in template_rows if str(row.get("review_status", "")).strip() in APPENDABLE_REVIEW_STATUS
        ),
        "rows_appended": len(append_rows),
        "rows_skipped_pending": rows_skipped_pending,
        "rows_skipped_duplicate": rows_skipped_duplicate,
        "rows_skipped_invalid": rows_skipped_invalid,
        "appended_symbols": sorted(symbol for symbol in appended_symbols if symbol),
        "skipped_duplicate_keys": skipped_duplicate_keys,
    }
    return append_rows, append_issues, summary


def append_paper_manual_review_log(
    template_rows: list[dict[str, str]],
    existing_log_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]], dict[str, Any]]:
    validation_issues, validation_summary = validate_paper_manual_review_log_rows(template_rows)
    existing_count = len(existing_log_rows)
    summary: dict[str, Any] = {
        "validation_result": validation_summary["validation_result"],
        "validation_error_count": validation_summary["error_count"],
        "validation_warning_count": validation_summary["warning_count"],
        "total_template_rows": len(template_rows),
        "existing_log_row_count_before": existing_count,
        "final_log_row_count_after": existing_count,
        "rows_considered_for_append": 0,
        "rows_appended": 0,
        "rows_skipped_pending": 0,
        "rows_skipped_duplicate": 0,
        "rows_skipped_invalid": 0,
        "appended_symbols": [],
        "skipped_duplicate_keys": [],
        "append_executed": False,
    }

    if validation_summary["error_count"] > 0:
        append_issues = [
            _append_issue(
                "error",
                int(issue["row_number"]),
                {"symbol": issue["symbol"], "question_id": issue["question_id"]},
                "append_aborted_validation_error",
                issue["message"],
            )
            for issue in validation_issues
            if issue["severity"] == "error"
        ]
        return existing_log_rows[:], append_issues, summary

    append_rows, append_issues, append_summary = build_paper_manual_review_log_append_plan(
        template_rows,
        existing_log_rows,
    )
    final_rows = existing_log_rows + append_rows
    summary.update(append_summary)
    summary["append_executed"] = True
    summary["final_log_row_count_after"] = len(final_rows)
    return final_rows, append_issues, summary


def write_paper_manual_review_log(
    rows: list[dict[str, str]],
    output_path: Path,
    allowed_root: Path | None = None,
) -> None:
    if allowed_root is None:
        assert_paper_path(output_path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(output_path, allowed_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_append_issues_csv(
    issues: list[dict[str, str]],
    output_path: Path,
    allowed_root: Path | None = None,
) -> None:
    if allowed_root is None:
        assert_paper_path(output_path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(output_path, allowed_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=APPEND_ISSUE_COLUMNS)
        writer.writeheader()
        writer.writerows(issues)


def summarize_paper_manual_review_log_append(
    template_path: Path,
    target_log_path: Path,
    append_report_path: Path,
    append_issues_path: Path,
    summary_data: dict[str, Any],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "template_path": str(template_path),
        "target_log_path": str(target_log_path),
        "append_report_path": str(append_report_path),
        "append_issues_path": str(append_issues_path),
        "limitations": [
            "This append workflow does not update or overwrite existing rows.",
            "Pending rows are intentionally not appended.",
            "This is a manual review log workflow, not a buy/sell/hold recommendation system.",
            "Append duplicate key is review_date + symbol + question_id.",
        ],
        **summary_data,
    }


def render_paper_manual_review_log_append_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Paper Manual Review Log Append Report",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Input template path: {summary['template_path']}",
        f"- Target log path: {summary['target_log_path']}",
        f"- Validation result: {summary['validation_result']}",
        f"- Validation error count: {summary['validation_error_count']}",
        f"- Validation warning count: {summary['validation_warning_count']}",
        f"- Total template rows: {summary['total_template_rows']}",
        f"- Rows considered for append: {summary['rows_considered_for_append']}",
        f"- Rows appended: {summary['rows_appended']}",
        f"- Rows skipped pending: {summary['rows_skipped_pending']}",
        f"- Rows skipped duplicate: {summary['rows_skipped_duplicate']}",
        f"- Rows skipped invalid: {summary['rows_skipped_invalid']}",
        f"- Existing log row count before: {summary['existing_log_row_count_before']}",
        f"- Final log row count after: {summary['final_log_row_count_after']}",
        f"- Append executed: {summary['append_executed']}",
        "",
        "## Details",
        f"- Appended symbols: {'|'.join(summary['appended_symbols']) if summary['appended_symbols'] else '-'}",
        f"- Skipped duplicate keys: {'; '.join(summary['skipped_duplicate_keys']) if summary['skipped_duplicate_keys'] else '-'}",
        f"- Append issues CSV path: {summary['append_issues_path']}",
        "",
        "## Limitations",
    ]
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def write_markdown(path: Path, markdown: str, allowed_root: Path | None = None) -> None:
    if allowed_root is None:
        assert_paper_path(path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(path, allowed_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
