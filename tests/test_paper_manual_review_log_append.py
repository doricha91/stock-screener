from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_manual_review_log_append import (
    APPEND_ISSUE_COLUMNS,
    append_paper_manual_review_log,
    build_paper_manual_review_log_append_plan,
    load_existing_paper_manual_review_log_rows,
    render_paper_manual_review_log_append_report,
    summarize_paper_manual_review_log_append,
    write_append_issues_csv,
    write_markdown,
    write_paper_manual_review_log,
)
from core.paper_manual_review_log_template import PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
from core.paths import PAPER_TEST_DIR


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_manual_review_log_append_{uuid4().hex}"
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


def _row(
    symbol: str = "CF",
    question_id: str = "review_loss_1",
    review_status: str = "reviewed",
    manual_answer: str = "Checked entry rule.",
    **overrides: str,
) -> dict[str, str]:
    row = {column: "" for column in PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS}
    row.update(
        {
            "review_date": "2026-05-19",
            "symbol": symbol,
            "review_bucket": "review_loss",
            "review_priority": "high",
            "sample_size_flag": "low_sample",
            "symbol_status": "realized_only",
            "question_id": question_id,
            "question_text": "Did the entry signal match the strategy rule?",
            "question_category": "review_loss",
            "is_actionable": "false",
            "manual_answer": manual_answer,
            "review_status": review_status,
            "follow_up_needed": "false",
            "review_tag": "",
            "reviewer_note": "",
            "source_worksheet_path": "D:/python/StockScreener/outputs/paper_test/reports/paper_symbol_review_worksheet.csv",
            "created_at": "2026-05-19T12:28:33",
        }
    )
    row.update(overrides)
    return row


def test_log_is_created_when_missing(tmp_path: Path):
    output_path = _paper_test_path("paper_manual_review_log_test", tmp_path, ".csv")
    try:
        final_rows, _, summary = append_paper_manual_review_log([_row()], [])
        write_paper_manual_review_log(final_rows, output_path)
        assert output_path.exists()
        assert summary["rows_appended"] == 1
    finally:
        _cleanup(output_path)


def test_existing_log_is_appended(tmp_path: Path):
    output_path = _paper_test_path("paper_manual_review_log_test", tmp_path, ".csv")
    try:
        existing_rows = [_row(symbol="OLD", question_id="old_1")]
        write_paper_manual_review_log(existing_rows, output_path)
        loaded_existing = load_existing_paper_manual_review_log_rows(output_path)
        final_rows, _, summary = append_paper_manual_review_log([_row(symbol="NEW", question_id="new_1")], loaded_existing)
        assert summary["existing_log_row_count_before"] == 1
        assert summary["final_log_row_count_after"] == 2
        assert len(final_rows) == 2
    finally:
        _cleanup(output_path)


def test_pending_rows_are_excluded_from_append():
    final_rows, append_issues, summary = append_paper_manual_review_log([_row(review_status="pending", manual_answer="")], [])
    assert final_rows == []
    assert summary["rows_skipped_pending"] == 1
    assert any(issue["issue_code"] == "skipped_pending" for issue in append_issues)


def test_reviewed_rows_are_appended():
    final_rows, _, summary = append_paper_manual_review_log([_row(review_status="reviewed")], [])
    assert len(final_rows) == 1
    assert summary["rows_appended"] == 1


def test_deferred_rows_are_appended():
    final_rows, _, summary = append_paper_manual_review_log([_row(review_status="deferred", manual_answer="")], [])
    assert len(final_rows) == 1
    assert summary["rows_appended"] == 1


def test_not_applicable_rows_are_appended():
    final_rows, _, summary = append_paper_manual_review_log([_row(review_status="not_applicable", manual_answer="")], [])
    assert len(final_rows) == 1
    assert summary["rows_appended"] == 1


def test_duplicate_key_is_skipped_against_existing_log():
    existing = [_row(symbol="CF", question_id="review_loss_1")]
    final_rows, append_issues, summary = append_paper_manual_review_log([_row(symbol="CF", question_id="review_loss_1")], existing)
    assert len(final_rows) == 1
    assert summary["rows_skipped_duplicate"] == 1
    assert any(issue["issue_code"] == "skipped_duplicate" for issue in append_issues)


def test_batch_duplicate_is_skipped():
    append_rows, append_issues, summary = build_paper_manual_review_log_append_plan(
        [_row(symbol="CF", question_id="review_loss_1"), _row(symbol="CF", question_id="review_loss_1")],
        [],
    )
    assert len(append_rows) == 1
    assert summary["rows_skipped_duplicate"] == 1
    assert any(issue["issue_code"] == "skipped_duplicate" for issue in append_issues)


def test_existing_manual_answer_is_not_overwritten():
    existing = [_row(symbol="CF", question_id="review_loss_1", manual_answer="Original answer")]
    final_rows, _, _ = append_paper_manual_review_log(
        [_row(symbol="CF", question_id="review_loss_1", manual_answer="New answer")],
        existing,
    )
    assert final_rows[0]["manual_answer"] == "Original answer"


def test_validator_error_aborts_append():
    final_rows, append_issues, summary = append_paper_manual_review_log(
        [_row(review_status="reviewed", manual_answer="")],
        [],
    )
    assert final_rows == []
    assert summary["append_executed"] is False
    assert summary["validation_result"] == "FAIL"
    assert any(issue["issue_code"] == "append_aborted_validation_error" for issue in append_issues)


def test_validator_warning_does_not_block_append():
    final_rows, _, summary = append_paper_manual_review_log(
        [_row(review_status="deferred", manual_answer="")],
        [],
    )
    assert summary["validation_result"] == "PASS"
    assert summary["validation_warning_count"] == 1
    assert summary["rows_appended"] == 1
    assert len(final_rows) == 1


def test_append_report_and_issues_csv_are_generated(tmp_path: Path):
    report_path = _paper_test_path("paper_manual_review_log_append_report_test", tmp_path, ".md")
    issues_path = _paper_test_path("paper_manual_review_log_append_issues_test", tmp_path, ".csv")
    try:
        _, append_issues, summary_data = append_paper_manual_review_log([_row(review_status="pending", manual_answer="")], [])
        summary = summarize_paper_manual_review_log_append(
            template_path=Path("template.csv"),
            target_log_path=Path("log.csv"),
            append_report_path=report_path,
            append_issues_path=issues_path,
            summary_data=summary_data,
        )
        write_append_issues_csv(append_issues, issues_path)
        write_markdown(report_path, render_paper_manual_review_log_append_report(summary))
        with issues_path.open("r", encoding="utf-8-sig", newline="") as handle:
            written_rows = list(csv.DictReader(handle))
        assert report_path.exists()
        assert issues_path.exists()
        assert list(written_rows[0].keys()) == APPEND_ISSUE_COLUMNS
        assert "Rows skipped pending" in report_path.read_text(encoding="utf-8")
    finally:
        _cleanup(report_path)
        _cleanup(issues_path)


def test_template_csv_is_not_modified(tmp_path: Path):
    template_path = _paper_test_path("paper_manual_review_log_template_test", tmp_path, ".csv")
    try:
        _write_csv(template_path, PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS, [_row()])
        before = template_path.read_text(encoding="utf-8-sig")
        template_rows = load_existing_paper_manual_review_log_rows(template_path)
        append_paper_manual_review_log(template_rows, [])
        after = template_path.read_text(encoding="utf-8-sig")
        assert before == after
    finally:
        _cleanup(template_path)


def test_is_actionable_false_is_preserved():
    final_rows, _, _ = append_paper_manual_review_log([_row(is_actionable="false")], [])
    assert final_rows[0]["is_actionable"] == "false"
