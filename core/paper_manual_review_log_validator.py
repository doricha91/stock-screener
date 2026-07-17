from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_guard import assert_path_under_account_root
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


REQUIRED_MANUAL_REVIEW_LOG_COLUMNS = PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS

ALLOWED_REVIEW_STATUS = {
    "pending",
    "reviewed",
    "deferred",
    "not_applicable",
}
ALLOWED_FOLLOW_UP_NEEDED = {
    "true",
    "false",
    "TRUE",
    "FALSE",
    "1",
    "0",
}
TRUTHY_FOLLOW_UP_NEEDED = {"true", "TRUE", "1"}
ALLOWED_REVIEW_TAGS = {
    "",
    "entry_rule",
    "exit_rule",
    "position_sizing",
    "market_regime",
    "risk_management",
    "data_quality",
    "execution_quality",
    "signal_quality",
    "psychology",
    "other",
}
ISSUE_COLUMNS = [
    "severity",
    "row_number",
    "symbol",
    "question_id",
    "field",
    "issue_code",
    "message",
]


def validate_manual_review_log_columns(fieldnames: list[str] | None) -> None:
    normalized = [str(column or "").replace("\ufeff", "").strip() for column in (fieldnames or [])]
    missing = [column for column in REQUIRED_MANUAL_REVIEW_LOG_COLUMNS if column not in normalized]
    if missing:
        raise ValueError("Missing paper manual review log columns: " + ", ".join(missing))


def load_paper_manual_review_log_rows(path: Path, allowed_root: Path | None = None) -> list[dict[str, str]]:
    if allowed_root is None:
        assert_paper_path(path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(path, allowed_root)
    if not path.exists():
        raise FileNotFoundError(f"paper manual review log not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        validate_manual_review_log_columns(reader.fieldnames)
        return list(reader)


def _issue(
    severity: str,
    row_number: int,
    row: dict[str, str],
    field: str,
    issue_code: str,
    message: str,
) -> dict[str, str]:
    return {
        "severity": severity,
        "row_number": str(row_number),
        "symbol": str(row.get("symbol", "")).strip(),
        "question_id": str(row.get("question_id", "")).strip(),
        "field": field,
        "issue_code": issue_code,
        "message": message,
    }


def validate_paper_manual_review_log_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    issues: list[dict[str, str]] = []
    review_status_counts: Counter[str] = Counter()
    follow_up_counts: Counter[str] = Counter()
    review_tag_counts: Counter[str] = Counter()
    duplicate_counts: Counter[tuple[str, str, str]] = Counter()

    for row in rows:
        duplicate_counts[
            (
                str(row.get("review_date", "")).strip(),
                str(row.get("symbol", "")).strip(),
                str(row.get("question_id", "")).strip(),
            )
        ] += 1

    duplicate_keys = {key for key, count in duplicate_counts.items() if count > 1}

    for index, row in enumerate(rows, start=2):
        review_date = str(row.get("review_date", "")).strip()
        symbol = str(row.get("symbol", "")).strip()
        question_id = str(row.get("question_id", "")).strip()
        question_text = str(row.get("question_text", "")).strip()
        review_status = str(row.get("review_status", "")).strip()
        is_actionable = str(row.get("is_actionable", "")).strip()
        manual_answer = str(row.get("manual_answer", "")).strip()
        follow_up_needed = str(row.get("follow_up_needed", "")).strip()
        review_tag = str(row.get("review_tag", "")).strip()
        reviewer_note = str(row.get("reviewer_note", "")).strip()
        source_worksheet_path = str(row.get("source_worksheet_path", "")).strip()
        created_at = str(row.get("created_at", "")).strip()

        review_status_counts[review_status] += 1
        follow_up_counts[follow_up_needed] += 1
        review_tag_counts[review_tag] += 1

        if not symbol:
            issues.append(_issue("error", index, row, "symbol", "blank_symbol", "symbol must not be blank"))
        if not question_id:
            issues.append(_issue("error", index, row, "question_id", "blank_question_id", "question_id must not be blank"))
        if not question_text:
            issues.append(_issue("error", index, row, "question_text", "blank_question_text", "question_text must not be blank"))
        if not review_status:
            issues.append(_issue("error", index, row, "review_status", "blank_review_status", "review_status must not be blank"))
        if not is_actionable:
            issues.append(_issue("error", index, row, "is_actionable", "blank_is_actionable", "is_actionable must not be blank"))
        elif is_actionable != "false":
            issues.append(_issue("error", index, row, "is_actionable", "invalid_is_actionable", "is_actionable must be false"))

        if not review_date:
            issues.append(_issue("warning", index, row, "review_date", "blank_review_date", "review_date is blank"))
        if not source_worksheet_path:
            issues.append(_issue("warning", index, row, "source_worksheet_path", "blank_source_worksheet_path", "source_worksheet_path is blank"))
        if not created_at:
            issues.append(_issue("warning", index, row, "created_at", "blank_created_at", "created_at is blank"))

        if review_status and review_status not in ALLOWED_REVIEW_STATUS:
            issues.append(_issue("error", index, row, "review_status", "invalid_review_status", f"review_status must be one of: {', '.join(sorted(ALLOWED_REVIEW_STATUS))}"))
        elif review_status == "reviewed" and not manual_answer:
            issues.append(_issue("error", index, row, "manual_answer", "blank_manual_answer_for_reviewed", "manual_answer must not be blank when review_status is reviewed"))
        elif review_status == "pending" and manual_answer:
            issues.append(_issue("warning", index, row, "manual_answer", "manual_answer_present_for_pending", "manual_answer is present while review_status is pending"))
        elif review_status == "deferred" and not reviewer_note and not review_tag:
            issues.append(_issue("warning", index, row, "review_status", "deferred_without_context", "deferred review should include reviewer_note or review_tag"))

        if follow_up_needed not in ALLOWED_FOLLOW_UP_NEEDED:
            issues.append(_issue("error", index, row, "follow_up_needed", "invalid_follow_up_needed", "follow_up_needed must be one of: true, false, TRUE, FALSE, 1, 0"))
        elif follow_up_needed in TRUTHY_FOLLOW_UP_NEEDED and not reviewer_note and not review_tag:
            issues.append(_issue("warning", index, row, "follow_up_needed", "follow_up_without_context", "follow_up_needed=true should include reviewer_note or review_tag"))

        if "," in review_tag:
            issues.append(_issue("warning", index, row, "review_tag", "multiple_review_tags_not_supported", "multiple review tags are not supported in this MFU"))
        elif review_tag not in ALLOWED_REVIEW_TAGS:
            issues.append(_issue("warning", index, row, "review_tag", "invalid_review_tag", "review_tag is outside the allowed tag list"))

        if (review_date, symbol, question_id) in duplicate_keys:
            issues.append(_issue("error", index, row, "review_date+symbol+question_id", "duplicate_review_key", "duplicate review key detected"))

    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    summary = {
        "row_count": len(rows),
        "error_count": error_count,
        "warning_count": warning_count,
        "duplicate_key_count": len(duplicate_keys),
        "review_status_counts": dict(review_status_counts),
        "follow_up_needed_counts": dict(follow_up_counts),
        "review_tag_counts": dict(review_tag_counts),
        "validation_result": "PASS" if error_count == 0 else "FAIL",
    }
    return issues, summary


def summarize_paper_manual_review_log_validation(
    input_path: Path,
    issues: list[dict[str, str]],
    summary_data: dict[str, Any],
    report_output_path: Path,
    issues_output_path: Path,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "input_path": str(input_path),
        "report_output_path": str(report_output_path),
        "issues_output_path": str(issues_output_path),
        "issues": issues,
        "limitations": [
            "This validation covers manual review log format only.",
            "It does not append, update, or overwrite review log rows.",
            "It does not recommend buy/sell/hold actions.",
            "This MFU does not implement weekly rollup or backlog integration.",
        ],
        **summary_data,
    }


def render_paper_manual_review_log_validation_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Paper Manual Review Log Validation Report",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Input file path: {summary['input_path']}",
        f"- Row count: {summary['row_count']}",
        f"- Error count: {summary['error_count']}",
        f"- Warning count: {summary['warning_count']}",
        f"- Duplicate key count: {summary['duplicate_key_count']}",
        f"- Validation result: {summary['validation_result']}",
        "",
        "## Distributions",
        f"- review_status: {summary['review_status_counts']}",
        f"- follow_up_needed: {summary['follow_up_needed_counts']}",
        f"- review_tag: {summary['review_tag_counts']}",
        "",
        "## Outputs",
        f"- Validation report path: {summary['report_output_path']}",
        f"- Validation issues CSV path: {summary['issues_output_path']}",
        "",
        "## Limitations",
    ]
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def write_validation_issues_csv(issues: list[dict[str, str]], output_path: Path, allowed_root: Path | None = None) -> None:
    if allowed_root is None:
        assert_paper_path(output_path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(output_path, allowed_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=ISSUE_COLUMNS)
        writer.writeheader()
        writer.writerows(issues)


def write_markdown(path: Path, markdown: str, allowed_root: Path | None = None) -> None:
    if allowed_root is None:
        assert_paper_path(path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(path, allowed_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
