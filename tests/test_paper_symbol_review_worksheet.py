from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from core.paper_symbol_review_worksheet import (
    PAPER_SYMBOL_REVIEW_WORKSHEET_COLUMNS,
    build_paper_symbol_review_worksheet,
    load_paper_symbol_review_bucket_rows,
    render_paper_symbol_review_worksheet_summary,
    summarize_paper_symbol_review_worksheet,
    write_paper_symbol_review_worksheet_csv,
    write_paper_symbol_review_worksheet_markdown,
)
from core.paths import PAPER_TEST_DIR


REVIEW_BUCKET_COLUMNS = [
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


@pytest.fixture
def tmp_path() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_symbol_review_worksheet_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield path
    finally:
        if path.exists():
            shutil.rmtree(path)


def _row(
    symbol: str = "CF",
    review_bucket: str = "review_loss",
    review_priority: str = "high",
    sample_size_flag: str = "low_sample",
    total_pnl: str = "-100.00",
) -> dict[str, str]:
    row = {column: "" for column in REVIEW_BUCKET_COLUMNS}
    row.update(
        {
            "symbol": symbol,
            "symbol_status": "realized_only",
            "review_bucket": review_bucket,
            "review_priority": review_priority,
            "is_actionable": "false",
            "sample_size_flag": sample_size_flag,
            "review_reason": "test",
            "realized_pnl": "-100.00",
            "unrealized_pnl": "0.00",
            "total_pnl": total_pnl,
            "realized_trade_count": "1",
            "win_rate": "0.0000000",
            "avg_realized_return_pct": "-1.0000000",
            "open_shares": "0",
            "open_market_value": "0.00",
            "open_unrealized_return_pct": "0.0000000",
            "position_weight_market": "0.0000000",
            "neutral_threshold_pct": "0.5000000",
        }
    )
    return row


def _paper_test_path(prefix: str, tmp_path: Path, suffix: str) -> Path:
    return PAPER_TEST_DIR / f"{prefix}_{tmp_path.name}{suffix}"


def _cleanup(path: Path) -> None:
    if path.exists():
        path.unlink()


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_review_loss_questions_generated():
    _, question_rows, _, _ = build_paper_symbol_review_worksheet([_row(review_bucket="review_loss")])
    assert any("진입 신호가 원래 전략 조건과 일치했는가?" == row["question_text"] for row in question_rows)


def test_track_realized_gain_questions_generated():
    _, question_rows, _, _ = build_paper_symbol_review_worksheet([_row(review_bucket="track_realized_gain", review_priority="medium")])
    assert any("수익 거래의 진입 조건은 재현 가능한가?" == row["question_text"] for row in question_rows)


def test_monitor_open_gain_questions_generated():
    _, question_rows, _, _ = build_paper_symbol_review_worksheet([_row(review_bucket="monitor_open_gain", review_priority="medium")])
    assert any("현재 평가이익이 exit rule 또는 trailing stop과 어떤 관계인가?" == row["question_text"] for row in question_rows)


def test_monitor_open_loss_questions_generated():
    _, question_rows, _, _ = build_paper_symbol_review_worksheet([_row(review_bucket="monitor_open_loss")])
    assert any("현재 평가손실이 stop 기준에 가까운가?" == row["question_text"] for row in question_rows)


def test_neutral_questions_generated():
    _, question_rows, _, _ = build_paper_symbol_review_worksheet([_row(review_bucket="neutral", review_priority="low", sample_size_flag="no_realized_trades")])
    assert any("손익이 중립 범위에 있는 이유가 무엇인가?" == row["question_text"] for row in question_rows)


def test_priority_sort_order():
    symbol_rows, _, _, _ = build_paper_symbol_review_worksheet(
        [
            _row(symbol="N", review_bucket="neutral", review_priority="low", total_pnl="0.00"),
            _row(symbol="M", review_bucket="monitor_open_gain", review_priority="medium", total_pnl="-10.00"),
            _row(symbol="R", review_bucket="review_loss", review_priority="high", total_pnl="-50.00"),
        ]
    )
    assert [row["symbol"] for row in symbol_rows] == ["R", "M", "N"]


def test_is_actionable_always_false():
    symbol_rows, question_rows, _, _ = build_paper_symbol_review_worksheet([_row()])
    assert symbol_rows[0]["is_actionable"] == "false"
    assert all(row["is_actionable"] == "false" for row in question_rows)


def test_sample_size_flag_is_shown_and_warning_added():
    symbol_rows, _, _, warnings = build_paper_symbol_review_worksheet([_row(sample_size_flag="low_sample")])
    assert symbol_rows[0]["sample_size_flag"] == "low_sample"
    assert any("low_sample worksheet interpretation requires caution" in warning for warning in warnings)


def test_markdown_includes_checklist_and_non_actionable_text():
    symbol_rows, _, summary_data, warnings = build_paper_symbol_review_worksheet([_row()])
    summary = summarize_paper_symbol_review_worksheet(
        summary_data,
        warnings,
        input_path=Path("in.csv"),
        markdown_output_path=Path("out.md"),
        csv_output_path=Path("out.csv"),
    )
    markdown = render_paper_symbol_review_worksheet_summary(summary, symbol_rows)
    assert "### Review Checklist" in markdown
    assert "- [ ] 진입 신호가 원래 전략 조건과 일치했는가?" in markdown
    assert "This worksheet is non-actionable." in markdown
    assert "It does not recommend buy/sell/hold actions." in markdown


def test_csv_question_rows_are_created(tmp_path: Path):
    output_csv_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".csv")
    output_md_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".md")
    try:
        symbol_rows, question_rows, summary_data, warnings = build_paper_symbol_review_worksheet([_row()])
        write_paper_symbol_review_worksheet_csv(question_rows, output_csv_path)
        summary = summarize_paper_symbol_review_worksheet(
            summary_data,
            warnings,
            input_path=Path("in.csv"),
            markdown_output_path=output_md_path,
            csv_output_path=output_csv_path,
        )
        write_paper_symbol_review_worksheet_markdown(
            render_paper_symbol_review_worksheet_summary(summary, symbol_rows),
            output_md_path,
        )
        with output_csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            written_rows = list(csv.DictReader(handle))
        assert list(written_rows[0].keys()) == PAPER_SYMBOL_REVIEW_WORKSHEET_COLUMNS
        assert len(written_rows) >= 5
        assert output_md_path.exists()
    finally:
        _cleanup(output_csv_path)
        _cleanup(output_md_path)


def test_missing_required_columns_detected(tmp_path: Path):
    input_path = _paper_test_path("paper_symbol_review_buckets_test", tmp_path, ".csv")
    try:
        _write_csv(input_path, ["symbol"], [{"symbol": "CF"}])
        with pytest.raises(ValueError, match="Missing paper symbol review bucket columns"):
            load_paper_symbol_review_bucket_rows(input_path)
    finally:
        _cleanup(input_path)


def test_empty_input_handling(tmp_path: Path):
    output_csv_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".csv")
    output_md_path = _paper_test_path("paper_symbol_review_worksheet_test", tmp_path, ".md")
    try:
        symbol_rows, question_rows, summary_data, warnings = build_paper_symbol_review_worksheet([])
        assert symbol_rows == []
        assert question_rows == []
        summary = summarize_paper_symbol_review_worksheet(
            summary_data,
            warnings,
            input_path=Path("in.csv"),
            markdown_output_path=output_md_path,
            csv_output_path=output_csv_path,
        )
        markdown = render_paper_symbol_review_worksheet_summary(summary, symbol_rows)
        assert "No symbols available" in markdown
    finally:
        _cleanup(output_csv_path)
        _cleanup(output_md_path)
