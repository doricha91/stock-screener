from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paper_manual_review_log_validator import (
    ISSUE_COLUMNS,
    load_paper_manual_review_log_rows,
    render_paper_manual_review_log_validation_report,
    summarize_paper_manual_review_log_validation,
    validate_paper_manual_review_log_rows,
    write_markdown,
    write_validation_issues_csv,
)
from core.paths import PAPER_TEST_DIR


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_manual_review_log_validator_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _paper_test_path(prefix: str, tmp_path: Path, suffix: str) -> Path:
    return PAPER_TEST_DIR / "reviews" / f"{prefix}_{tmp_path.name}{suffix}"


def _cleanup(path: Path) -> None:
    if path.exists():
        path.unlink()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _row(**overrides: str) -> dict[str, str]:
    row = {column: "" for column in PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS}
    row.update(
        {
            "review_date": "2026-05-19",
            "symbol": "CF",
            "review_bucket": "review_loss",
            "review_priority": "high",
            "sample_size_flag": "low_sample",
            "symbol_status": "realized_only",
            "question_id": "review_loss_1",
            "question_text": "Did the entry signal match the strategy rule?",
            "question_category": "review_loss",
            "is_actionable": "false",
            "manual_answer": "",
            "review_status": "pending",
            "follow_up_needed": "false",
            "review_tag": "",
            "reviewer_note": "",
            "source_worksheet_path": "D:/python/StockScreener/outputs/paper_test/reports/paper_symbol_review_worksheet.csv",
            "created_at": "2026-05-19T12:28:33",
        }
    )
    row.update(overrides)
    return row


def test_valid_template_passes():
    issues, summary = validate_paper_manual_review_log_rows([_row()])
    assert issues == []
    assert summary["validation_result"] == "PASS"
    assert summary["error_count"] == 0


def test_missing_required_columns_detected(tmp_path: Path):
    input_path = _paper_test_path("paper_manual_review_log_test", tmp_path, ".csv")
    try:
        _write_csv(input_path, ["symbol"], [{"symbol": "CF"}])
        with pytest.raises(ValueError, match="Missing paper manual review log columns"):
            load_paper_manual_review_log_rows(input_path)
    finally:
        _cleanup(input_path)


def test_invalid_review_status_detected():
    issues, summary = validate_paper_manual_review_log_rows([_row(review_status="done")])
    assert summary["validation_result"] == "FAIL"
    assert any(issue["issue_code"] == "invalid_review_status" for issue in issues)


def test_reviewed_without_manual_answer_is_error():
    issues, _ = validate_paper_manual_review_log_rows([_row(review_status="reviewed", manual_answer="")])
    assert any(issue["issue_code"] == "blank_manual_answer_for_reviewed" for issue in issues)


def test_deferred_without_note_or_tag_is_warning():
    issues, summary = validate_paper_manual_review_log_rows([_row(review_status="deferred")])
    assert summary["warning_count"] == 1
    assert any(issue["issue_code"] == "deferred_without_context" for issue in issues)


def test_invalid_follow_up_needed_detected():
    issues, _ = validate_paper_manual_review_log_rows([_row(follow_up_needed="maybe")])
    assert any(issue["issue_code"] == "invalid_follow_up_needed" for issue in issues)


def test_follow_up_true_without_note_or_tag_is_warning():
    issues, _ = validate_paper_manual_review_log_rows([_row(follow_up_needed="true")])
    assert any(issue["issue_code"] == "follow_up_without_context" for issue in issues)


def test_invalid_review_tag_is_warning():
    issues, _ = validate_paper_manual_review_log_rows([_row(review_tag="bad_tag")])
    assert any(issue["issue_code"] == "invalid_review_tag" for issue in issues)


def test_is_actionable_true_is_error():
    issues, _ = validate_paper_manual_review_log_rows([_row(is_actionable="true")])
    assert any(issue["issue_code"] == "invalid_is_actionable" for issue in issues)


def test_duplicate_key_is_error():
    issues, summary = validate_paper_manual_review_log_rows([_row(), _row()])
    assert summary["duplicate_key_count"] == 1
    assert sum(1 for issue in issues if issue["issue_code"] == "duplicate_review_key") == 2


def test_blank_symbol_question_id_and_question_text_are_errors():
    issues, _ = validate_paper_manual_review_log_rows([_row(symbol="", question_id="", question_text="")])
    codes = {issue["issue_code"] for issue in issues}
    assert "blank_symbol" in codes
    assert "blank_question_id" in codes
    assert "blank_question_text" in codes


def test_issues_csv_and_report_are_generated(tmp_path: Path):
    issues_output_path = _paper_test_path("paper_manual_review_log_validation_issues_test", tmp_path, ".csv")
    report_output_path = _paper_test_path("paper_manual_review_log_validation_report_test", tmp_path, ".md")
    try:
        issues, summary_data = validate_paper_manual_review_log_rows([_row(review_status="deferred")])
        summary = summarize_paper_manual_review_log_validation(
            input_path=Path("in.csv"),
            issues=issues,
            summary_data=summary_data,
            report_output_path=report_output_path,
            issues_output_path=issues_output_path,
        )
        write_validation_issues_csv(issues, issues_output_path)
        write_markdown(report_output_path, render_paper_manual_review_log_validation_report(summary))
        with issues_output_path.open("r", encoding="utf-8-sig", newline="") as handle:
            written_rows = list(csv.DictReader(handle))
        assert issues_output_path.exists()
        assert report_output_path.exists()
        assert list(written_rows[0].keys()) == ISSUE_COLUMNS
        assert "Validation result" in report_output_path.read_text(encoding="utf-8")
    finally:
        _cleanup(issues_output_path)
        _cleanup(report_output_path)


def test_original_csv_is_not_modified(tmp_path: Path):
    input_path = _paper_test_path("paper_manual_review_log_test", tmp_path, ".csv")
    try:
        _write_csv(input_path, PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS, [_row()])
        before = input_path.read_text(encoding="utf-8-sig")
        rows = load_paper_manual_review_log_rows(input_path)
        validate_paper_manual_review_log_rows(rows)
        after = input_path.read_text(encoding="utf-8-sig")
        assert before == after
    finally:
        _cleanup(input_path)
