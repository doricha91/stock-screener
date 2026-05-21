from __future__ import annotations

import csv
import importlib.util
import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from core.paths import (
    FRONT_TEST_DIR,
    PAPER_TEST_DIR,
    ROOT,
    market_db_path,
    paper_account_snapshot_path,
    paper_config_snapshot_path,
    paper_daily_action_plan_path,
    paper_execution_log_path,
    paper_position_snapshot_path,
)
from core.paper_safety import assert_paper_path


STAGES = {
    "plan",
    "eod",
    "reports",
    "review-template",
    "review-append",
    "all",
}
DATE_REQUIRED_STAGES = {"plan", "eod", "all"}
REPORT_WRITER_FIELDS = ["severity", "stage", "check_name", "message", "path", "suggestion"]
REPORT_PATH_NAMES = {
    "markdown": "paper_preflight_report.md",
    "issues": "paper_preflight_issues.csv",
}


@dataclass(frozen=True)
class PaperPreflightPaths:
    paper_root: Path
    front_root: Path
    reports_dir: Path
    reviews_dir: Path
    market_db: Path
    execution_log: Path
    account_snapshot: Path
    position_snapshot: Path
    daily_action_plan: Path | None
    config_snapshot: Path | None
    review_worksheet_csv: Path
    review_buckets_csv: Path
    review_template_csv: Path
    validation_report: Path
    validation_issues_csv: Path


def build_paper_preflight_paths(date_str: str | None = None) -> PaperPreflightPaths:
    reports_dir = PAPER_TEST_DIR / "reports"
    reviews_dir = PAPER_TEST_DIR / "reviews"
    clean_date = _normalize_date(date_str) if date_str else None
    return PaperPreflightPaths(
        paper_root=PAPER_TEST_DIR,
        front_root=FRONT_TEST_DIR,
        reports_dir=reports_dir,
        reviews_dir=reviews_dir,
        market_db=Path(market_db_path()),
        execution_log=paper_execution_log_path(),
        account_snapshot=paper_account_snapshot_path(),
        position_snapshot=paper_position_snapshot_path(),
        daily_action_plan=paper_daily_action_plan_path(clean_date) if clean_date else None,
        config_snapshot=paper_config_snapshot_path(clean_date) if clean_date else None,
        review_worksheet_csv=reports_dir / "paper_symbol_review_worksheet.csv",
        review_buckets_csv=reports_dir / "paper_symbol_review_buckets.csv",
        review_template_csv=reviews_dir / "paper_manual_review_log_template.csv",
        validation_report=reviews_dir / "paper_manual_review_log_validation_report.md",
        validation_issues_csv=reviews_dir / "paper_manual_review_log_validation_issues.csv",
    )


def _normalize_date(date_str: str) -> str:
    clean = str(date_str).replace("-", "").strip()
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return clean


def _parse_date_or_issue(date_str: str | None, issues: list[dict[str, str]], stage: str) -> str | None:
    if date_str is None:
        return None
    try:
        return _normalize_date(date_str)
    except ValueError:
        issues.append(
            _issue(
                "error",
                stage,
                "date_format",
                "date must be YYYYMMDD or YYYY-MM-DD",
                suggestion="Use --date 20260513 or --date 2026-05-13",
            )
        )
        return None


def _issue(
    severity: str,
    stage: str,
    check_name: str,
    message: str,
    path: Path | None = None,
    suggestion: str = "",
) -> dict[str, str]:
    return {
        "severity": severity,
        "stage": stage,
        "check_name": check_name,
        "message": message,
        "path": str(path) if path is not None else "",
        "suggestion": suggestion,
    }


def _check_imports(stage: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for module_name in ("core", "scripts", "core.paths"):
        if importlib.util.find_spec(module_name) is None:
            issues.append(
                _issue(
                    "error",
                    stage,
                    "module_import",
                    f"module spec not found: {module_name}",
                    suggestion="Run from the project root with PYTHONPATH configured",
                )
            )
    return issues


def _check_paper_path(
    target: Path | None,
    paper_root: Path,
    front_root: Path,
    stage: str,
    check_name: str,
) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if target is None:
        issues.append(_issue("error", stage, check_name, "path is missing", suggestion="Provide a valid path context"))
        return issues
    resolved_target = target.resolve()
    resolved_front = front_root.resolve()
    if resolved_target == resolved_front or resolved_front in resolved_target.parents:
        issues.append(
            _issue(
                "error",
                stage,
                check_name,
                "front_test path detected where paper path is required",
                path=target,
                suggestion="Use outputs/paper_test paths only",
            )
        )
        return issues
    try:
        assert_paper_path(target, paper_root)
    except ValueError:
        issues.append(
            _issue(
                "error",
                stage,
                check_name,
                "paper path is outside outputs/paper_test",
                path=target,
                suggestion="Route the file under outputs/paper_test",
            )
        )
    return issues


def _common_checks(
    stage: str,
    date_str: str | None,
    strict: bool,
    paths: PaperPreflightPaths,
    cwd: Path | None = None,
) -> tuple[list[dict[str, str]], str | None, list[str]]:
    issues: list[dict[str, str]] = []
    checked_paths: list[str] = []
    current_cwd = (cwd or Path.cwd()).resolve()
    if current_cwd != ROOT.resolve():
        issues.append(
            _issue(
                "warning",
                stage,
                "project_root",
                "current working directory is not the project root",
                path=current_cwd,
                suggestion=f"Run from {ROOT}",
            )
        )

    issues.extend(_check_imports(stage))

    if not paths.paper_root.exists():
        issues.append(
            _issue(
                "error",
                stage,
                "paper_root_exists",
                "outputs/paper_test does not exist",
                path=paths.paper_root,
                suggestion="Create or restore outputs/paper_test",
            )
        )
    checked_paths.append(str(paths.paper_root))
    checked_paths.append(str(paths.front_root))

    if stage in DATE_REQUIRED_STAGES and not date_str:
        issues.append(
            _issue(
                "error",
                stage,
                "date_required",
                f"--date is required for stage={stage}",
                suggestion="Provide --date YYYYMMDD or YYYY-MM-DD",
            )
        )
        return issues, None, checked_paths

    normalized_date = _parse_date_or_issue(date_str, issues, stage) if date_str else None
    if normalized_date:
        parsed_date = datetime.strptime(normalized_date, "%Y%m%d").date()
        if parsed_date > date.today():
            issues.append(
                _issue(
                    "warning",
                    stage,
                    "future_date",
                    "target date is in the future",
                    suggestion="Verify the intended paper operation date",
                )
            )

    return issues, normalized_date, checked_paths


def _stage_plan(paths: PaperPreflightPaths) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    checked_paths = [str(paths.market_db), str(paths.execution_log), str(paths.daily_action_plan), str(paths.config_snapshot)]
    if not paths.market_db.exists():
        issues.append(_issue("error", "plan", "market_db_exists", "market DB path does not exist", path=paths.market_db))
    if not paths.execution_log.exists():
        issues.append(
            _issue(
                "warning",
                "plan",
                "paper_execution_log_exists",
                "paper_execution_log.csv is missing; bootstrap paper state may be empty",
                path=paths.execution_log,
            )
        )
    issues.extend(_check_paper_path(paths.execution_log, paths.paper_root, paths.front_root, "plan", "execution_log_path"))
    issues.extend(_check_paper_path(paths.daily_action_plan, paths.paper_root, paths.front_root, "plan", "daily_action_plan_path"))
    issues.extend(_check_paper_path(paths.config_snapshot, paths.paper_root, paths.front_root, "plan", "config_snapshot_path"))
    return issues, checked_paths


def _stage_eod(paths: PaperPreflightPaths) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    checked_paths = [str(paths.daily_action_plan), str(paths.execution_log), str(paths.account_snapshot), str(paths.position_snapshot)]
    if paths.daily_action_plan is None or not paths.daily_action_plan.exists():
        issues.append(
            _issue(
                "error",
                "eod",
                "daily_action_plan_exists",
                "paper daily action plan is missing",
                path=paths.daily_action_plan,
                suggestion="Run scripts/run_paper_daily_plan.py first",
            )
        )
    issues.extend(_check_paper_path(paths.daily_action_plan, paths.paper_root, paths.front_root, "eod", "daily_action_plan_path"))
    issues.extend(_check_paper_path(paths.execution_log, paths.paper_root, paths.front_root, "eod", "execution_log_path"))
    issues.extend(_check_paper_path(paths.account_snapshot, paths.paper_root, paths.front_root, "eod", "account_snapshot_path"))
    issues.extend(_check_paper_path(paths.position_snapshot, paths.paper_root, paths.front_root, "eod", "position_snapshot_path"))
    return issues, checked_paths


def _stage_reports(paths: PaperPreflightPaths) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    checked_paths = [str(paths.execution_log), str(paths.account_snapshot), str(paths.position_snapshot), str(paths.reports_dir)]
    if not paths.execution_log.exists():
        issues.append(_issue("warning", "reports", "paper_execution_log_exists", "paper_execution_log.csv is missing", path=paths.execution_log))
    if not paths.account_snapshot.exists():
        issues.append(_issue("error", "reports", "paper_account_snapshot_exists", "paper_account_snapshot.csv is missing", path=paths.account_snapshot))
    if not paths.position_snapshot.exists():
        issues.append(_issue("error", "reports", "paper_position_snapshot_exists", "paper_position_snapshot.csv is missing", path=paths.position_snapshot))
    if not paths.reports_dir.exists():
        issues.append(_issue("error", "reports", "reports_dir_exists", "reports directory is missing", path=paths.reports_dir))
    issues.extend(_check_paper_path(paths.execution_log, paths.paper_root, paths.front_root, "reports", "execution_log_path"))
    issues.extend(_check_paper_path(paths.account_snapshot, paths.paper_root, paths.front_root, "reports", "account_snapshot_path"))
    issues.extend(_check_paper_path(paths.position_snapshot, paths.paper_root, paths.front_root, "reports", "position_snapshot_path"))
    issues.extend(_check_paper_path(paths.reports_dir, paths.paper_root, paths.front_root, "reports", "reports_dir"))
    return issues, checked_paths


def _stage_review_template(paths: PaperPreflightPaths) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    checked_paths = [str(paths.review_worksheet_csv), str(paths.review_buckets_csv), str(paths.reviews_dir)]
    if not paths.review_worksheet_csv.exists():
        issues.append(_issue("error", "review-template", "review_worksheet_exists", "paper_symbol_review_worksheet.csv is missing", path=paths.review_worksheet_csv))
    if not paths.review_buckets_csv.exists():
        issues.append(_issue("error", "review-template", "review_buckets_exists", "paper_symbol_review_buckets.csv is missing", path=paths.review_buckets_csv))
    if not paths.reviews_dir.exists():
        issues.append(_issue("error", "review-template", "reviews_dir_exists", "reviews directory is missing", path=paths.reviews_dir))
    issues.extend(_check_paper_path(paths.review_worksheet_csv, paths.paper_root, paths.front_root, "review-template", "review_worksheet_path"))
    issues.extend(_check_paper_path(paths.review_buckets_csv, paths.paper_root, paths.front_root, "review-template", "review_buckets_path"))
    issues.extend(_check_paper_path(paths.reviews_dir, paths.paper_root, paths.front_root, "review-template", "reviews_dir"))
    return issues, checked_paths


def _parse_validation_result(report_path: Path) -> str | None:
    if not report_path.exists():
        return None
    text = report_path.read_text(encoding="utf-8")
    match = re.search(r"Validation result:\s*(PASS|FAIL|PASS_WITH_WARNINGS)", text)
    if match:
        return match.group(1)
    return None


def _stage_review_append(paths: PaperPreflightPaths) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    checked_paths = [str(paths.review_template_csv), str(paths.validation_report), str(paths.validation_issues_csv), str(paths.reviews_dir)]
    if not paths.review_template_csv.exists():
        issues.append(_issue("error", "review-append", "review_template_exists", "paper_manual_review_log_template.csv is missing", path=paths.review_template_csv))
    if not paths.validation_report.exists():
        issues.append(_issue("warning", "review-append", "validation_report_exists", "paper manual review validation report is missing", path=paths.validation_report))
    else:
        validation_result = _parse_validation_result(paths.validation_report)
        if validation_result == "FAIL":
            issues.append(_issue("error", "review-append", "validation_report_status", "validation report indicates FAIL", path=paths.validation_report))
        elif validation_result is None:
            issues.append(_issue("warning", "review-append", "validation_report_parse", "validation report status could not be parsed", path=paths.validation_report))
    if not paths.validation_issues_csv.exists():
        issues.append(_issue("warning", "review-append", "validation_issues_exists", "paper manual review validation issues CSV is missing", path=paths.validation_issues_csv))
    issues.extend(_check_paper_path(paths.review_template_csv, paths.paper_root, paths.front_root, "review-append", "review_template_path"))
    issues.extend(_check_paper_path(paths.validation_report, paths.paper_root, paths.front_root, "review-append", "validation_report_path"))
    issues.extend(_check_paper_path(paths.validation_issues_csv, paths.paper_root, paths.front_root, "review-append", "validation_issues_path"))
    return issues, checked_paths


def _escalate_warnings_if_strict(issues: list[dict[str, str]], strict: bool) -> list[dict[str, str]]:
    if not strict:
        return issues
    escalated: list[dict[str, str]] = []
    for issue in issues:
        if issue["severity"] == "warning":
            escalated.append({**issue, "severity": "error", "message": f"[strict] {issue['message']}"})
        else:
            escalated.append(issue)
    return escalated


def summarize_paper_preflight(
    stage: str,
    date_str: str | None,
    strict: bool,
    issues: list[dict[str, str]],
    checked_paths: list[str],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    final_issues = _escalate_warnings_if_strict(issues, strict)
    error_count = sum(1 for issue in final_issues if issue["severity"] == "error")
    warning_count = sum(1 for issue in final_issues if issue["severity"] == "warning")
    if error_count > 0:
        result = "FAIL"
    elif warning_count > 0:
        result = "PASS_WITH_WARNINGS"
    else:
        result = "PASS"
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "stage": stage,
        "date": date_str or "",
        "strict": strict,
        "result": result,
        "error_count": error_count,
        "warning_count": warning_count,
        "checked_paths": checked_paths,
        "issues": final_issues,
        "limitations": [
            "This preflight check is read-only.",
            "It does not run paper daily plan, EOD commit, report regeneration, or review append.",
            "It does not validate investment decisions.",
            "It only checks operational readiness for paper workflow.",
        ],
    }


def render_paper_preflight_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Paper Preflight Report",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Stage: {summary['stage']}",
        f"- Date: {summary['date'] or '-'}",
        f"- Strict mode: {summary['strict']}",
        f"- Result: {summary['result']}",
        f"- Error count: {summary['error_count']}",
        f"- Warning count: {summary['warning_count']}",
        "",
        "## Checked Paths",
    ]
    lines.extend(f"- {path}" for path in summary["checked_paths"])
    lines.extend(["", "## Issues", "| Severity | Stage | Check | Message | Path | Suggestion |", "| :--- | :--- | :--- | :--- | :--- | :--- |"])
    if not summary["issues"]:
        lines.append("| - | - | - | No issues | - | - |")
    else:
        for issue in summary["issues"]:
            lines.append(
                f"| {issue['severity']} | {issue['stage']} | {issue['check_name']} | {issue['message']} | {issue['path'] or '-'} | {issue['suggestion'] or '-'} |"
            )
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def write_paper_preflight_issues_csv(issues: list[dict[str, str]], output_path: Path) -> None:
    assert_paper_path(output_path, PAPER_TEST_DIR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_WRITER_FIELDS)
        writer.writeheader()
        writer.writerows(issues)


def write_markdown(path: Path, markdown: str) -> None:
    assert_paper_path(path, PAPER_TEST_DIR)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")


def run_paper_preflight_check(
    stage: str,
    date_str: str | None = None,
    strict: bool = False,
    paths: PaperPreflightPaths | None = None,
    cwd: Path | None = None,
) -> dict[str, Any]:
    if stage not in STAGES:
        raise ValueError(f"Unsupported stage: {stage}")

    effective_paths = paths or build_paper_preflight_paths(date_str)
    issues, normalized_date, checked_paths = _common_checks(stage, date_str, strict, effective_paths, cwd=cwd)
    stage_sequence = ["plan", "eod", "reports", "review-template", "review-append"] if stage == "all" else [stage]

    if stage == "all" and normalized_date:
        effective_paths = paths or build_paper_preflight_paths(normalized_date)

    for current_stage in stage_sequence:
        if current_stage == "plan":
            stage_issues, stage_paths = _stage_plan(effective_paths)
        elif current_stage == "eod":
            stage_issues, stage_paths = _stage_eod(effective_paths)
        elif current_stage == "reports":
            stage_issues, stage_paths = _stage_reports(effective_paths)
        elif current_stage == "review-template":
            stage_issues, stage_paths = _stage_review_template(effective_paths)
        else:
            stage_issues, stage_paths = _stage_review_append(effective_paths)
        issues.extend(stage_issues)
        checked_paths.extend(stage_paths)

    deduped_paths = list(dict.fromkeys(path for path in checked_paths if path))
    return summarize_paper_preflight(stage, normalized_date or date_str, strict, issues, deduped_paths)
