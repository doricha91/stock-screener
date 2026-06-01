from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

import core.paper_manual_review_append_commit as commit_module
from core.paper_account_paths import build_paper_account_paths
from core.paper_manual_review_append_commit import (
    ManualReviewAppendCommitError,
    commit_manual_review_preview,
)
from core.paths import OUTPUTS, PAPER_TEST_DIR


REVIEW_COLUMNS = [
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


def _unique_path(prefix: str, suffix: str) -> Path:
    return PAPER_TEST_DIR / f"{prefix}_{uuid4().hex}{suffix}"


def _unique_output_dir(prefix: str) -> Path:
    path = PAPER_TEST_DIR / prefix / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _preview_candidate(
    *,
    review_date: str = "2026-05-25",
    symbol: str = "AAPL",
    question_id: str = "Q001",
    question_text: str = "진입 신호가 전략 조건과 일치했는가?",
    manual_answer: str = "예, 조건과 일치했다.",
    review_status: str = "reviewed",
    follow_up_needed: str = "false",
    review_tag: str = "",
    reviewer_note: str = "",
    source_template_key: str = "template-key",
    validation_status: str = "PASS",
    validation_issues: list[dict] | None = None,
    page_id: str = "page-1",
) -> dict:
    return {
        "page_id": page_id,
        "name": f"{symbol} {question_id}",
        "review_date": review_date,
        "symbol": symbol,
        "question_id": question_id,
        "question_text": question_text,
        "manual_answer": manual_answer,
        "review_status": review_status,
        "follow_up_needed": follow_up_needed,
        "review_tag": review_tag,
        "reviewer_note": reviewer_note,
        "source_template_key": source_template_key,
        "notion_external_key": None,
        "validation_status_raw": None,
        "validation_message_raw": None,
        "import_status_raw": "READY",
        "imported_at_raw": None,
        "synced_at_raw": None,
        "created_at": "2026-05-25T10:00:00",
        "canonical_key": f"manual_review:{review_date}:{symbol}:{question_id}",
        "validation_issues": validation_issues or [],
        "validation_status": validation_status,
    }


def _preview_payload(
    *,
    review_date: str = "2026-05-25",
    append_allowed: str = "true",
    fail_count: int = 0,
    warning_count: int = 0,
    candidates: list[dict] | None = None,
) -> dict:
    candidates = candidates or []
    return {
        "review_date": review_date,
        "account_id": "paper_default",
        "candidate_count": len(candidates),
        "pass_count": sum(1 for item in candidates if item["validation_status"] == "PASS"),
        "warning_count": warning_count,
        "fail_count": fail_count,
        "append_allowed": append_allowed,
        "source_data_source_id": "ds-manual-review",
        "json_path": "",
        "markdown_path": "",
        "duplicate_candidates": [],
        "candidates": candidates,
    }


@pytest.fixture
def review_commit_env():
    review_root = _unique_output_dir("paper_manual_review_commit_test")
    review_log_path = review_root / "paper_manual_review_log.csv"
    template_path = review_root / "paper_manual_review_log_template.csv"
    reports_dir = review_root / "reports"
    backup_dir = OUTPUTS / "dev_backups_manual_review_commit_test" / uuid4().hex
    preview_path = review_root / "manual_review_preview.json"
    reports_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)

    _write_csv(review_log_path, [])
    _write_csv(
        template_path,
        [
            {
                "review_date": "2026-05-25",
                "symbol": "AAPL",
                "review_bucket": "review_loss",
                "review_priority": "high",
                "sample_size_flag": "low_sample",
                "symbol_status": "realized_only",
                "question_id": "Q001",
                "question_text": "진입 신호가 전략 조건과 일치했는가?",
                "question_category": "review_loss",
                "is_actionable": "false",
                "manual_answer": "",
                "review_status": "pending",
                "follow_up_needed": "false",
                "review_tag": "",
                "reviewer_note": "",
                "source_worksheet_path": "worksheet.csv",
                "created_at": "2026-05-25T09:00:00",
            }
        ],
    )

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(commit_module, "paper_reviews_dir", lambda: review_root)
    monkeypatch.setattr(commit_module, "paper_reports_dir", lambda: reports_dir)
    monkeypatch.setattr(commit_module, "dev_backups_dir", lambda: backup_dir)

    try:
        yield {
            "review_root": review_root,
            "review_log_path": review_log_path,
            "template_path": template_path,
            "reports_dir": reports_dir,
            "backup_dir": backup_dir,
            "preview_path": preview_path,
        }
    finally:
        monkeypatch.undo()
        if review_root.exists():
            shutil.rmtree(review_root, ignore_errors=True)
        if backup_dir.exists():
            shutil.rmtree(backup_dir, ignore_errors=True)


def test_fail_preview_is_rejected(review_commit_env):
    payload = _preview_payload(
        append_allowed="false",
        fail_count=1,
        candidates=[_preview_candidate(validation_status="FAIL")],
    )
    review_commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManualReviewAppendCommitError, match="FAIL rows"):
        commit_manual_review_preview(
            review_date="2026-05-25",
            preview_json_path=review_commit_env["preview_path"],
        )


def test_warning_preview_requires_allow_warnings(review_commit_env):
    payload = _preview_payload(
        append_allowed="true_with_warnings",
        warning_count=1,
        candidates=[
            _preview_candidate(
                validation_status="WARNING",
                validation_issues=[{"severity": "WARNING", "code": "missing_review_tag", "message": "Review Tag is blank."}],
            )
        ],
    )
    review_commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManualReviewAppendCommitError, match="--allow-warnings"):
        commit_manual_review_preview(
            review_date="2026-05-25",
            preview_json_path=review_commit_env["preview_path"],
        )


def test_warning_preview_appends_with_allow_warnings(review_commit_env):
    payload = _preview_payload(
        append_allowed="true_with_warnings",
        warning_count=1,
        candidates=[
            _preview_candidate(
                validation_status="WARNING",
                validation_issues=[{"severity": "WARNING", "code": "missing_review_tag", "message": "Review Tag is blank."}],
            )
        ],
    )
    review_commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    result = commit_manual_review_preview(
        review_date="2026-05-25",
        preview_json_path=review_commit_env["preview_path"],
        allow_warnings=True,
    )
    assert result.account_id == "paper_default"
    assert result.appended_count == 1
    with review_commit_env["review_log_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["manual_answer"] == "예, 조건과 일치했다."
    assert rows[0]["review_status"] == "reviewed"
    sidecar = json.loads(Path(result.commit_json_path).read_text(encoding="utf-8"))
    assert sidecar["account_id"] == "paper_default"
    assert sidecar["rows"][0]["account_id"] == "paper_default"
    assert sidecar["rows"][0]["canonical_key"] == "manual_review:paper_default:2026-05-25:AAPL:Q001"
    assert sidecar["rows"][0]["legacy_canonical_key"] == "manual_review:2026-05-25:AAPL:Q001"
    assert sidecar["rows"][0]["legacy_key_compatible"] is True
    assert sidecar["appended_count"] == 1
    assert sidecar["rows"][0]["append_status"] == "APPENDED"


def test_pass_preview_is_appended(review_commit_env):
    payload = _preview_payload(candidates=[_preview_candidate()])
    review_commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    result = commit_manual_review_preview(
        review_date="2026-05-25",
        preview_json_path=review_commit_env["preview_path"],
    )
    assert result.appended_count == 1


def test_preview_date_mismatch_is_rejected(review_commit_env):
    payload = _preview_payload(review_date="2026-05-24", candidates=[_preview_candidate(review_date="2026-05-24")])
    review_commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManualReviewAppendCommitError, match="Preview date mismatch"):
        commit_manual_review_preview(
            review_date="2026-05-25",
            preview_json_path=review_commit_env["preview_path"],
        )


def test_existing_review_log_duplicate_blocks_append(review_commit_env):
    _write_csv(
        review_commit_env["review_log_path"],
        [
            {
                "review_date": "2026-05-25",
                "symbol": "AAPL",
                "review_bucket": "review_loss",
                "review_priority": "high",
                "sample_size_flag": "low_sample",
                "symbol_status": "realized_only",
                "question_id": "Q001",
                "question_text": "진입 신호가 전략 조건과 일치했는가?",
                "question_category": "review_loss",
                "is_actionable": "false",
                "manual_answer": "기존 답변",
                "review_status": "reviewed",
                "follow_up_needed": "false",
                "review_tag": "",
                "reviewer_note": "",
                "source_worksheet_path": "worksheet.csv",
                "created_at": "2026-05-25T09:00:00",
            }
        ],
    )
    payload = _preview_payload(candidates=[_preview_candidate()])
    review_commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ManualReviewAppendCommitError, match="duplicate review key"):
        commit_manual_review_preview(
            review_date="2026-05-25",
            preview_json_path=review_commit_env["preview_path"],
        )


def test_review_log_schema_is_preserved(review_commit_env):
    payload = _preview_payload(candidates=[_preview_candidate()])
    review_commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    commit_manual_review_preview(
        review_date="2026-05-25",
        preview_json_path=review_commit_env["preview_path"],
    )
    with review_commit_env["review_log_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == REVIEW_COLUMNS


def test_commit_report_json_and_markdown_are_created(review_commit_env):
    payload = _preview_payload(candidates=[_preview_candidate()])
    review_commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")
    result = commit_manual_review_preview(
        review_date="2026-05-25",
        preview_json_path=review_commit_env["preview_path"],
    )
    assert Path(result.commit_json_path).exists()
    assert Path(result.commit_markdown_path).exists()


def test_append_failure_rolls_back(review_commit_env, monkeypatch):
    payload = _preview_payload(candidates=[_preview_candidate()])
    review_commit_env["preview_path"].write_text(json.dumps(payload), encoding="utf-8")

    def _raise_write(*args, **kwargs):
        raise RuntimeError("boom_write_review_log")

    monkeypatch.setattr(commit_module, "write_paper_manual_review_log", _raise_write)

    with pytest.raises(ManualReviewAppendCommitError, match="boom_write_review_log"):
        commit_manual_review_preview(
            review_date="2026-05-25",
            preview_json_path=review_commit_env["preview_path"],
        )

    with review_commit_env["review_log_path"].open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows == []


def test_non_default_review_append_writes_under_account_root(tmp_path, monkeypatch):
    account_root = tmp_path / "paper_accounts" / "paper_growth"
    account_paths = build_paper_account_paths(
        "paper_growth",
        account_root=account_root,
        allow_legacy_default=False,
        create=True,
    )
    review_log_path = account_paths.reviews_dir / "paper_manual_review_log.csv"
    template_path = account_paths.reviews_dir / "paper_manual_review_log_template.csv"
    preview_path = tmp_path / "manual_review_preview_non_default.json"

    _write_csv(review_log_path, [])
    _write_csv(
        template_path,
        [
            {
                "review_date": "2026-05-25",
                "symbol": "AAPL",
                "review_bucket": "review_loss",
                "review_priority": "high",
                "sample_size_flag": "low_sample",
                "symbol_status": "realized_only",
                "question_id": "Q001",
                "question_text": "Question text",
                "question_category": "review_loss",
                "is_actionable": "false",
                "manual_answer": "",
                "review_status": "pending",
                "follow_up_needed": "false",
                "review_tag": "",
                "reviewer_note": "",
                "source_worksheet_path": "worksheet.csv",
                "created_at": "2026-05-25T09:00:00",
            }
        ],
    )

    payload = _preview_payload(candidates=[_preview_candidate()])
    payload["account_id"] = "paper_growth"
    payload["candidates"][0]["account_id"] = "paper_growth"
    payload["candidates"][0]["canonical_key"] = "manual_review:paper_growth:2026-05-25:AAPL:Q001"
    preview_path.write_text(json.dumps(payload), encoding="utf-8")

    result = commit_manual_review_preview(
        review_date="2026-05-25",
        preview_json_path=preview_path,
        account_paths=account_paths,
    )

    assert result.account_id == "paper_growth"
    sidecar = json.loads(Path(result.commit_json_path).read_text(encoding="utf-8"))
    row = sidecar["rows"][0]
    assert row["account_id"] == "paper_growth"
    assert row["canonical_key"] == "manual_review:paper_growth:2026-05-25:AAPL:Q001"
    assert row["legacy_canonical_key"] is None
    assert row["legacy_key_compatible"] is False
    assert Path(result.commit_json_path).is_relative_to(account_paths.reports_dir.resolve())
    with review_log_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
