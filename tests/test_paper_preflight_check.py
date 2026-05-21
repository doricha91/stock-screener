from __future__ import annotations

import csv
import shutil
from pathlib import Path
from uuid import uuid4

from core.paper_preflight_check import (
    PaperPreflightPaths,
    REPORT_PATH_NAMES,
    render_paper_preflight_report,
    run_paper_preflight_check,
    write_markdown,
    write_paper_preflight_issues_csv,
)
from core.paths import PAPER_TEST_DIR


def _tmp_dir() -> Path:
    root = Path("_tmp_test_artifacts")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"paper_preflight_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _cleanup_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def _write_text(path: Path, text: str = "ok") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_paths(tmp: Path, include_front_intrusion: bool = False, validation_result: str = "PASS") -> PaperPreflightPaths:
    paper_root = PAPER_TEST_DIR / f"preflight_{tmp.name}"
    front_root = PAPER_TEST_DIR / f"front_shadow_{tmp.name}" if include_front_intrusion else PAPER_TEST_DIR.parent / f"front_shadow_{tmp.name}"
    reports_dir = paper_root / "reports"
    reviews_dir = paper_root / "reviews"
    daily_action_plan = paper_root / "daily_action_plan_20260513.md"
    config_snapshot = paper_root / "config_snapshots" / "paper_config_snapshot_20260513.json"
    market_db = paper_root / "market_data.db"
    execution_log = paper_root / "paper_execution_log.csv"
    account_snapshot = paper_root / "paper_account_snapshot.csv"
    position_snapshot = paper_root / "paper_position_snapshot.csv"
    worksheet = reports_dir / "paper_symbol_review_worksheet.csv"
    buckets = reports_dir / "paper_symbol_review_buckets.csv"
    template = reviews_dir / "paper_manual_review_log_template.csv"
    validation_report = reviews_dir / "paper_manual_review_log_validation_report.md"
    validation_issues = reviews_dir / "paper_manual_review_log_validation_issues.csv"

    for directory in (paper_root, reports_dir, reviews_dir, config_snapshot.parent):
        directory.mkdir(parents=True, exist_ok=True)
    _write_text(market_db)
    _write_text(daily_action_plan)
    _write_text(config_snapshot)
    _write_text(execution_log)
    _write_text(account_snapshot)
    _write_text(position_snapshot)
    _write_text(worksheet)
    _write_text(buckets)
    _write_text(template)
    _write_text(validation_report, f"- Validation result: {validation_result}\n")
    _write_text(validation_issues, "severity,row_number,symbol,question_id,field,issue_code,message\n")

    return PaperPreflightPaths(
        paper_root=paper_root,
        front_root=front_root,
        reports_dir=reports_dir,
        reviews_dir=reviews_dir,
        market_db=market_db,
        execution_log=execution_log,
        account_snapshot=account_snapshot,
        position_snapshot=position_snapshot,
        daily_action_plan=daily_action_plan,
        config_snapshot=config_snapshot,
        review_worksheet_csv=worksheet,
        review_buckets_csv=buckets,
        review_template_csv=template,
        validation_report=validation_report,
        validation_issues_csv=validation_issues,
    )


def test_plan_stage_pass_or_warning():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        summary = run_paper_preflight_check("plan", "20260513", paths=paths, cwd=Path.cwd())
        assert summary["result"] in {"PASS", "PASS_WITH_WARNINGS"}
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_invalid_date_format_is_error():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        summary = run_paper_preflight_check("plan", "2026/05/13", paths=paths, cwd=Path.cwd())
        assert summary["result"] == "FAIL"
        assert any(issue["check_name"] == "date_format" for issue in summary["issues"])
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_missing_date_for_required_stage_is_error():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        summary = run_paper_preflight_check("plan", None, paths=paths, cwd=Path.cwd())
        assert summary["result"] == "FAIL"
        assert any(issue["check_name"] == "date_required" for issue in summary["issues"])
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_path_outside_paper_root_is_error():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        bad_paths = PaperPreflightPaths(**{**paths.__dict__, "execution_log": Path.cwd() / "outside.csv"})
        summary = run_paper_preflight_check("plan", "20260513", paths=bad_paths, cwd=Path.cwd())
        assert summary["result"] == "FAIL"
        assert any(issue["check_name"] == "execution_log_path" for issue in summary["issues"])
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_front_test_path_detected_is_error():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp, include_front_intrusion=True)
        bad_paths = PaperPreflightPaths(**{**paths.__dict__, "daily_action_plan": paths.front_root / "daily_action_plan_20260513.md"})
        summary = run_paper_preflight_check("plan", "20260513", paths=bad_paths, cwd=Path.cwd())
        assert summary["result"] == "FAIL"
        assert any("front_test path detected" in issue["message"] for issue in summary["issues"])
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_plan_stage_missing_execution_log_is_warning():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        paths.execution_log.unlink()
        summary = run_paper_preflight_check("plan", "20260513", paths=paths, cwd=Path.cwd())
        assert summary["result"] == "PASS_WITH_WARNINGS"
        assert any(issue["check_name"] == "paper_execution_log_exists" for issue in summary["issues"])
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_eod_stage_missing_daily_action_plan_is_error():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        paths.daily_action_plan.unlink()
        summary = run_paper_preflight_check("eod", "20260513", paths=paths, cwd=Path.cwd())
        assert summary["result"] == "FAIL"
        assert any(issue["check_name"] == "daily_action_plan_exists" for issue in summary["issues"])
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_reports_stage_missing_account_snapshot_is_error():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        paths.account_snapshot.unlink()
        summary = run_paper_preflight_check("reports", paths=paths, cwd=Path.cwd())
        assert summary["result"] == "FAIL"
        assert any(issue["check_name"] == "paper_account_snapshot_exists" for issue in summary["issues"])
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_review_template_stage_missing_worksheet_is_error():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        paths.review_worksheet_csv.unlink()
        summary = run_paper_preflight_check("review-template", paths=paths, cwd=Path.cwd())
        assert summary["result"] == "FAIL"
        assert any(issue["check_name"] == "review_worksheet_exists" for issue in summary["issues"])
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_review_append_stage_missing_template_is_error():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        paths.review_template_csv.unlink()
        summary = run_paper_preflight_check("review-append", paths=paths, cwd=Path.cwd())
        assert summary["result"] == "FAIL"
        assert any(issue["check_name"] == "review_template_exists" for issue in summary["issues"])
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_review_append_validation_fail_is_error():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp, validation_result="FAIL")
        summary = run_paper_preflight_check("review-append", paths=paths, cwd=Path.cwd())
        assert summary["result"] == "FAIL"
        assert any(issue["check_name"] == "validation_report_status" for issue in summary["issues"])
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_warning_only_results_in_pass_with_warnings():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        paths.validation_report.unlink()
        summary = run_paper_preflight_check("review-append", paths=paths, cwd=Path.cwd())
        assert summary["result"] == "PASS_WITH_WARNINGS"
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_error_results_in_fail():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        paths.review_buckets_csv.unlink()
        summary = run_paper_preflight_check("review-template", paths=paths, cwd=Path.cwd())
        assert summary["result"] == "FAIL"
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_no_report_written_without_write_report():
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        summary = run_paper_preflight_check("plan", "20260513", paths=paths, cwd=Path.cwd())
        markdown_path = paths.reports_dir / REPORT_PATH_NAMES["markdown"]
        issues_path = paths.reports_dir / REPORT_PATH_NAMES["issues"]
        assert not markdown_path.exists()
        assert not issues_path.exists()
        assert summary["result"] in {"PASS", "PASS_WITH_WARNINGS"}
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)


def test_report_writers_create_outputs(tmp_path: Path | None = None):
    tmp = _tmp_dir()
    try:
        paths = _build_paths(tmp)
        summary = run_paper_preflight_check("plan", "20260513", paths=paths, cwd=Path.cwd())
        markdown_path = paths.reports_dir / REPORT_PATH_NAMES["markdown"]
        issues_path = paths.reports_dir / REPORT_PATH_NAMES["issues"]
        write_markdown(markdown_path, render_paper_preflight_report(summary))
        write_paper_preflight_issues_csv(summary["issues"], issues_path)
        assert markdown_path.exists()
        assert issues_path.exists()
        with issues_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if rows:
            assert "severity" in rows[0]
    finally:
        _cleanup_dir(tmp)
        _cleanup_dir(paths.paper_root)
