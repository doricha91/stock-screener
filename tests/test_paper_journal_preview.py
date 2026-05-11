from pathlib import Path
import uuid

from scripts.run_paper_eod_update import parse_journal_preview_from_markdown


def write_report(rows: list[str]) -> Path:
    report = Path("tests") / f"_tmp_paper_report_{uuid.uuid4().hex}.md"
    content = "\n".join(
        [
            "# Report",
            "## 5. 📝 프론트테스트 실행 기록 (Copy & Paste to Journal)",
            "| Date | Regime | Symbol | Type | Rec_Shares | Rec_Price | Act_Shares | Act_Price | Reason | Notes |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
            *rows,
            "",
        ]
    )
    report.write_text(content, encoding="utf-8")
    return report


def test_journal_preview_parser_reads_buy_sell_rows():
    report = write_report(
        [
            "| 2026-05-07 | BULL | AAPL | BUY | 10 | 185.20 | 10 | 185.30 | PAPER_FILLED | ok |",
            "| 2026-05-07 | BULL | TSLA | SELL | 3 | 240.00 | 3 | 240.10 | PAPER_FILLED | ok |",
        ],
    )
    try:
        rows = parse_journal_preview_from_markdown(report)
        assert len(rows) == 2
        assert rows[0]["symbol"] == "AAPL"
        assert rows[0]["type"] == "BUY"
        assert rows[1]["symbol"] == "TSLA"
        assert rows[1]["type"] == "SELL"
    finally:
        if report.exists():
            report.unlink()


def test_empty_act_fields_are_pending():
    report = write_report(
        [
            "| 2026-05-07 | BULL | AAPL | BUY | 10 | 185.20 |  |  |  |  |",
        ],
    )
    try:
        rows = parse_journal_preview_from_markdown(report)
        assert len(rows) == 1
        assert rows[0]["status"] == "PENDING_ACTUAL_FILL"
    finally:
        if report.exists():
            report.unlink()


def test_filled_act_fields_are_ready():
    report = write_report(
        [
            "| 2026-05-07 | BULL | AAPL | BUY | 10 | 185.20 | 10 | 185.30 | PAPER_FILLED | ok |",
        ],
    )
    try:
        rows = parse_journal_preview_from_markdown(report)
        assert len(rows) == 1
        assert rows[0]["status"] == "READY_FOR_PAPER_TRADE"
    finally:
        if report.exists():
            report.unlink()


def test_review_and_warning_rows_are_excluded():
    report = write_report(
        [
            "| 2026-05-07 | BULL | AAPL | SELL | 10 | 185.20 |  |  | REVIEW_EXIT | note |",
            "| 2026-05-07 | BULL | TSLA | SELL | 10 | 185.20 |  |  | WARNING_HIGHEST_PRICE_STALE | note |",
            "| 2026-05-07 | BULL | MSFT | BUY | 5 | 400.00 |  |  |  |  |",
        ],
    )
    try:
        rows = parse_journal_preview_from_markdown(report)
        assert len(rows) == 1
        assert rows[0]["symbol"] == "MSFT"
    finally:
        if report.exists():
            report.unlink()
