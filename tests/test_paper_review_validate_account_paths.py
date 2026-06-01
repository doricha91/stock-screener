from __future__ import annotations

import csv
from pathlib import Path

from core.paper_account_paths import build_paper_account_paths
from scripts.append_paper_manual_review_log import append_paper_manual_review_log_from_template
from scripts.generate_paper_manual_review_log_template import generate_paper_manual_review_log_template
from scripts.validate_paper_manual_review_log import validate_paper_manual_review_log


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_review_template_validate_append_share_same_non_default_root(tmp_path: Path):
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

    template_result = generate_paper_manual_review_log_template(account_paths=account_paths)
    validation_result = validate_paper_manual_review_log(account_paths=account_paths)

    template_path = template_result["csv_output_path"]
    rows: list[dict[str, str]]
    with template_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows[0]["manual_answer"] = "Reviewed"
    rows[0]["review_status"] = "reviewed"
    with template_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    append_result = append_paper_manual_review_log_from_template(account_paths=account_paths)

    assert template_result["csv_output_path"].is_relative_to(account_paths.reviews_dir.resolve())
    assert validation_result["report_output_path"].is_relative_to(account_paths.reviews_dir.resolve())
    assert validation_result["issues_output_path"].is_relative_to(account_paths.reviews_dir.resolve())
    assert append_result["target_log_path"].is_relative_to(account_paths.reviews_dir.resolve())
    assert append_result["append_report_path"].is_relative_to(account_paths.reviews_dir.resolve())
    assert not (tmp_path / "paper_test").exists()
