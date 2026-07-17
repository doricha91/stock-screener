from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_manual_review_log_template import (
    PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS,
    REQUIRED_BUCKET_COLUMNS,
    REQUIRED_WORKSHEET_COLUMNS,
    build_paper_manual_review_log_template,
    load_csv_rows,
    render_paper_manual_review_log_template_markdown,
    summarize_paper_manual_review_log_template,
    write_markdown,
    write_paper_manual_review_log_template_csv,
)
from core.paper_manual_review_log_validator import ALLOWED_REVIEW_TAGS
from core.paths import PAPER_TEST_DIR, paper_reviews_dir


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_manual_review_log_template_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _paper_test_path(prefix: str, tmp_path: Path, suffix: str, directory: str = "reports") -> Path:
    return PAPER_TEST_DIR / directory / f"{prefix}_{tmp_path.name}{suffix}"


def _cleanup(path: Path) -> None:
    if path.exists():
        path.unlink()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _worksheet_row(symbol: str = "CF", bucket: str = "review_loss") -> dict[str, str]:
    row = {column: "" for column in REQUIRED_WORKSHEET_COLUMNS}
    row.update(
        {
            "symbol": symbol,
            "review_bucket": bucket,
            "review_priority": "high",
            "sample_size_flag": "low_sample",
            "symbol_status": "realized_only",
            "is_actionable": "false",
            "question_id": f"{bucket}_1",
            "question_text": "Did the entry signal match the strategy rule?",
            "question_category": bucket,
            "requires_manual_answer": "true",
        }
    )
    return row


def _bucket_row(symbol: str = "CF", bucket: str = "review_loss") -> dict[str, str]:
    row = {column: "" for column in REQUIRED_BUCKET_COLUMNS}
    row.update(
        {
            "symbol": symbol,
            "review_bucket": bucket,
            "review_priority": "high",
            "sample_size_flag": "low_sample",
            "symbol_status": "realized_only",
            "is_actionable": "false",
        }
    )
    return row


def test_review_log_template_csv_and_markdown_are_generated(tmp_path: Path):
    worksheet_csv_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".csv")
    bucket_csv_path = _paper_test_path("paper_symbol_review_buckets_test", tmp_path, ".csv")
    csv_output_path = _paper_test_path("paper_manual_review_log_template_test", tmp_path, ".csv", directory="reviews")
    markdown_output_path = _paper_test_path("paper_manual_review_log_template_test", tmp_path, ".md", directory="reviews")
    try:
        _write_csv(worksheet_csv_path, REQUIRED_WORKSHEET_COLUMNS, [_worksheet_row()])
        _write_csv(bucket_csv_path, REQUIRED_BUCKET_COLUMNS, [_bucket_row()])
        worksheet_rows = load_csv_rows(worksheet_csv_path, REQUIRED_WORKSHEET_COLUMNS, "paper_symbol_review_worksheet.csv")
        bucket_rows = load_csv_rows(bucket_csv_path, REQUIRED_BUCKET_COLUMNS, "paper_symbol_review_buckets.csv")
        output_rows, summary_data, warnings = build_paper_manual_review_log_template(
            worksheet_rows,
            bucket_rows,
            source_worksheet_path=worksheet_csv_path,
            review_date="2026-05-19",
            created_at="2026-05-19T09:00:00",
        )
        write_paper_manual_review_log_template_csv(output_rows, csv_output_path)
        summary = summarize_paper_manual_review_log_template(
            summary_data,
            warnings,
            worksheet_csv_path=worksheet_csv_path,
            review_bucket_csv_path=bucket_csv_path,
            csv_output_path=csv_output_path,
            markdown_output_path=markdown_output_path,
        )
        write_markdown(markdown_output_path, render_paper_manual_review_log_template_markdown(summary))
        assert csv_output_path.exists()
        assert markdown_output_path.exists()
        assert str(csv_output_path.parent).endswith("reviews")
        assert str(markdown_output_path.parent).endswith("reviews")
    finally:
        for path in [worksheet_csv_path, bucket_csv_path, csv_output_path, markdown_output_path]:
            _cleanup(path)


def test_worksheet_question_rows_are_converted_to_template_rows():
    output_rows, summary_data, _ = build_paper_manual_review_log_template(
        [_worksheet_row()],
        [_bucket_row()],
        source_worksheet_path=Path("outputs/paper_test/reports/paper_symbol_review_worksheet.csv"),
        review_date="2026-05-19",
        created_at="2026-05-19T09:00:00",
    )
    assert len(output_rows) == 4
    assert output_rows[0]["symbol"] == "CF"
    assert output_rows[0]["question_id"] == "execution_review_1"
    assert output_rows[0]["question_category"] == "execution_review"
    assert output_rows[0]["review_tag"] == "execution_quality"
    assert [row["symbol"] for row in output_rows[-3:]] == ["ACCOUNT", "ACCOUNT", "ACCOUNT"]
    assert [(row["question_id"], row["review_tag"]) for row in output_rows[-3:]] == [
        ("account_review_1", "position_sizing"),
        ("account_review_2", "execution_quality"),
        ("account_review_3", "risk_management"),
    ]
    assert {row["review_tag"] for row in output_rows}.issubset(ALLOWED_REVIEW_TAGS)
    assert summary_data["review_template_row_count"] == 4
    assert summary_data["symbol_count"] == 1
    assert summary_data["account_question_count"] == 3


def test_no_action_empty_symbol_inputs_create_empty_review_template() -> None:
    output_rows, summary_data, warnings = build_paper_manual_review_log_template(
        [],
        [],
        source_worksheet_path=Path("outputs/paper_test/reports/paper_symbol_review_worksheet.csv"),
        review_date="2026-06-15",
        created_at="2026-06-15T09:00:00",
    )

    assert output_rows == []
    assert summary_data["review_template_row_count"] == 0
    assert summary_data["symbol_count"] == 0
    assert summary_data["account_question_count"] == 0
    assert warnings == []


def test_review_log_template_limits_questions_to_one_per_symbol_plus_account_rows():
    symbols = [f"SYM{i}" for i in range(1, 9)]
    output_rows, summary_data, _ = build_paper_manual_review_log_template(
        [_worksheet_row(symbol=symbol) for symbol in symbols],
        [_bucket_row(symbol=symbol) for symbol in symbols],
        source_worksheet_path=Path("outputs/paper_test/reports/paper_symbol_review_worksheet.csv"),
        review_date="2026-06-08",
        created_at="2026-06-08T09:00:00",
    )

    assert len(output_rows) == 11
    assert summary_data["review_template_row_count"] == 11
    assert summary_data["symbol_count"] == 8
    assert summary_data["account_question_count"] == 3
    symbol_rows = [row for row in output_rows if row["symbol"] != "ACCOUNT"]
    assert len(symbol_rows) == 8
    assert {row["question_id"] for row in symbol_rows} == {"execution_review_1"}
    assert {row["review_tag"] for row in symbol_rows} == {"execution_quality"}
    assert {row["review_tag"] for row in output_rows}.issubset(ALLOWED_REVIEW_TAGS)
    assert {row["review_date"] for row in output_rows} == {"2026-06-08"}
    keys = {(row["review_date"], row["symbol"], row["question_id"]) for row in output_rows}
    assert len(keys) == len(output_rows)


def test_manual_fields_default_values_are_set():
    output_rows, _, _ = build_paper_manual_review_log_template(
        [_worksheet_row()],
        [_bucket_row()],
        source_worksheet_path=Path("outputs/paper_test/reports/paper_symbol_review_worksheet.csv"),
        review_date="2026-05-19",
        created_at="2026-05-19T09:00:00",
    )
    row = output_rows[0]
    assert row["manual_answer"] == ""
    assert row["review_status"] == "pending"
    assert row["follow_up_needed"] == "false"
    assert row["review_tag"] == "execution_quality"
    assert row["reviewer_note"] == ""


def test_is_actionable_is_always_false_and_source_path_is_included():
    output_rows, _, _ = build_paper_manual_review_log_template(
        [_worksheet_row()],
        [_bucket_row()],
        source_worksheet_path=Path("outputs/paper_test/reports/paper_symbol_review_worksheet.csv"),
    )
    assert output_rows[0]["is_actionable"] == "false"
    assert output_rows[0]["source_worksheet_path"].endswith("paper_symbol_review_worksheet.csv")


def test_non_actionable_text_is_in_markdown():
    _, summary_data, warnings = build_paper_manual_review_log_template(
        [_worksheet_row()],
        [_bucket_row()],
        source_worksheet_path=Path("outputs/paper_test/reports/paper_symbol_review_worksheet.csv"),
        review_date="2026-05-19",
        created_at="2026-05-19T09:00:00",
    )
    summary = summarize_paper_manual_review_log_template(
        summary_data,
        warnings,
        worksheet_csv_path=Path("in.csv"),
        review_bucket_csv_path=Path("buckets.csv"),
        csv_output_path=paper_reviews_dir() / "out.csv",
        markdown_output_path=paper_reviews_dir() / "out.md",
    )
    markdown = render_paper_manual_review_log_template_markdown(summary)
    assert "This is a manual review log template." in markdown
    assert "It does not recommend buy/sell/hold actions." in markdown
    assert "is_actionable = false" in markdown


def test_missing_required_input_raises_clear_error(tmp_path: Path):
    worksheet_csv_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".csv")
    try:
        _write_csv(worksheet_csv_path, ["symbol"], [{"symbol": "CF"}])
        with pytest.raises(ValueError, match="Missing paper_symbol_review_worksheet.csv columns"):
            load_csv_rows(worksheet_csv_path, REQUIRED_WORKSHEET_COLUMNS, "paper_symbol_review_worksheet.csv")
    finally:
        _cleanup(worksheet_csv_path)


def test_original_report_csv_is_not_modified(tmp_path: Path):
    worksheet_csv_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".csv")
    bucket_csv_path = _paper_test_path("paper_symbol_review_buckets_test", tmp_path, ".csv")
    try:
        _write_csv(worksheet_csv_path, REQUIRED_WORKSHEET_COLUMNS, [_worksheet_row()])
        _write_csv(bucket_csv_path, REQUIRED_BUCKET_COLUMNS, [_bucket_row()])
        before = worksheet_csv_path.read_text(encoding="utf-8-sig")
        worksheet_rows = load_csv_rows(worksheet_csv_path, REQUIRED_WORKSHEET_COLUMNS, "paper_symbol_review_worksheet.csv")
        bucket_rows = load_csv_rows(bucket_csv_path, REQUIRED_BUCKET_COLUMNS, "paper_symbol_review_buckets.csv")
        build_paper_manual_review_log_template(
            worksheet_rows,
            bucket_rows,
            source_worksheet_path=worksheet_csv_path,
        )
        after = worksheet_csv_path.read_text(encoding="utf-8-sig")
        assert before == after
    finally:
        _cleanup(worksheet_csv_path)
        _cleanup(bucket_csv_path)


def test_written_csv_contains_expected_columns(tmp_path: Path):
    csv_output_path = _paper_test_path("paper_manual_review_log_template_test", tmp_path, ".csv", directory="reviews")
    try:
        output_rows, _, _ = build_paper_manual_review_log_template(
            [_worksheet_row()],
            [_bucket_row()],
            source_worksheet_path=Path("outputs/paper_test/reports/paper_symbol_review_worksheet.csv"),
            review_date="2026-05-19",
            created_at="2026-05-19T09:00:00",
        )
        write_paper_manual_review_log_template_csv(output_rows, csv_output_path)
        with csv_output_path.open("r", encoding="utf-8-sig", newline="") as handle:
            written_rows = list(csv.DictReader(handle))
        assert list(written_rows[0].keys()) == PAPER_MANUAL_REVIEW_LOG_TEMPLATE_COLUMNS
    finally:
        _cleanup(csv_output_path)
