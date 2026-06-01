from __future__ import annotations

import csv
from pathlib import Path

from core.paper_account_paths import build_paper_account_paths
from scripts.generate_paper_manual_review_log_template import generate_paper_manual_review_log_template


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_non_default_review_template_writes_under_reviews_root(tmp_path: Path):
    account_paths = build_paper_account_paths(
        "paper_growth",
        account_root=tmp_path / "paper_accounts" / "paper_growth",
        allow_legacy_default=False,
        create=True,
    )
    reports_dir = account_paths.reports_dir
    _write_csv(
        reports_dir / "paper_symbol_review_worksheet.csv",
        [
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
        ],
        [
            {
                "symbol": "AAPL",
                "review_bucket": "review_loss",
                "review_priority": "high",
                "sample_size_flag": "low_sample",
                "symbol_status": "realized_only",
                "is_actionable": "false",
                "question_id": "review_loss_1",
                "question_text": "Question",
                "question_category": "review_loss",
                "requires_manual_answer": "true",
            }
        ],
    )
    _write_csv(
        reports_dir / "paper_symbol_review_buckets.csv",
        [
            "symbol",
            "review_bucket",
            "review_priority",
            "sample_size_flag",
            "symbol_status",
            "is_actionable",
        ],
        [
            {
                "symbol": "AAPL",
                "review_bucket": "review_loss",
                "review_priority": "high",
                "sample_size_flag": "low_sample",
                "symbol_status": "realized_only",
                "is_actionable": "false",
            }
        ],
    )

    result = generate_paper_manual_review_log_template(account_paths=account_paths)
    assert result["csv_output_path"].is_relative_to(account_paths.reviews_dir.resolve())
    assert result["markdown_output_path"].is_relative_to(account_paths.reviews_dir.resolve())
    assert not (tmp_path / "paper_test").exists()

