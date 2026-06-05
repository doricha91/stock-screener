from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_paths import PaperAccountPaths
from core.paths import PAPER_TEST_DIR, paper_account_snapshot_path, paper_execution_log_path, paper_position_snapshot_path


WORKFLOW_NO_PLAN = "NO_PLAN"
WORKFLOW_PLAN_READY = "PLAN_READY"
WORKFLOW_COMMITTED = "COMMITTED"
WORKFLOW_REVIEW_READY = "REVIEW_READY"
WORKFLOW_REVIEW_PARTIAL = "REVIEW_PARTIAL"
WORKFLOW_REVIEW_DONE = "REVIEW_DONE"
WORKFLOW_UNKNOWN = "UNKNOWN_OR_INCOMPLETE"


@dataclass(frozen=True)
class PaperStatusPaths:
    paper_root: Path
    reports_dir: Path
    reviews_dir: Path
    account_snapshot_csv: Path
    position_snapshot_csv: Path
    execution_log_csv: Path


def build_paper_status_paths(paper_root: Path | None = None) -> PaperStatusPaths:
    root = Path(paper_root) if paper_root is not None else PAPER_TEST_DIR
    return PaperStatusPaths(
        paper_root=root,
        reports_dir=root / "reports",
        reviews_dir=root / "reviews",
        account_snapshot_csv=root / paper_account_snapshot_path().name,
        position_snapshot_csv=root / paper_position_snapshot_path().name,
        execution_log_csv=root / paper_execution_log_path().name,
    )


def _normalize_date(date_str: str) -> str:
    clean = str(date_str).replace("-", "").strip()
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return f"{clean[:4]}-{clean[4:6]}-{clean[6:]}"


def _compact_date(date_str: str) -> str:
    return _normalize_date(date_str).replace("-", "")


def _latest_date_from_filenames(directory: Path, pattern: str) -> str | None:
    if not directory.exists():
        return None
    regex = re.compile(pattern)
    found: list[str] = []
    for path in directory.iterdir():
        match = regex.fullmatch(path.name)
        if match:
            found.append(match.group(1))
    if not found:
        return None
    latest = max(found)
    return f"{latest[:4]}-{latest[4:6]}-{latest[6:]}"


def _safe_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized: dict[str, str] = {}
            for key, value in row.items():
                normalized_key = (key or "").replace("\ufeff", "").strip()
                normalized[normalized_key] = value or ""
            rows.append(normalized)
        return rows


def _read_latest_account_snapshot(path: Path) -> dict[str, Any]:
    rows = _read_csv_rows(path)
    if not rows:
        return {"exists": False, "latest_snapshot_date": None, "row": None, "error": None}
    if "snapshot_date" not in rows[0]:
        return {"exists": True, "latest_snapshot_date": None, "row": None, "error": "snapshot_date column missing"}
    sorted_rows = sorted(rows, key=lambda row: row.get("snapshot_date", ""))
    latest = sorted_rows[-1]
    return {
        "exists": True,
        "latest_snapshot_date": latest.get("snapshot_date"),
        "row": latest,
        "error": None,
    }


def _read_position_snapshot(path: Path) -> dict[str, Any]:
    rows = _read_csv_rows(path)
    if not rows:
        return {"exists": False, "latest_snapshot_date": None, "rows": [], "error": None}
    if "snapshot_date" not in rows[0]:
        return {"exists": True, "latest_snapshot_date": None, "rows": [], "error": "snapshot_date column missing"}
    latest_date = max((row.get("snapshot_date", "") for row in rows), default=None)
    return {
        "exists": True,
        "latest_snapshot_date": latest_date,
        "rows": rows,
        "error": None,
    }


def _read_execution_log(path: Path) -> dict[str, Any]:
    rows = _read_csv_rows(path)
    if not rows:
        return {"exists": False, "row_count": 0, "latest_trade_date": None, "rows": [], "error": None}
    if "date" not in rows[0]:
        return {"exists": True, "row_count": len(rows), "latest_trade_date": None, "rows": rows, "error": "date column missing"}
    latest_date = max((row.get("date", "") for row in rows), default=None)
    return {
        "exists": True,
        "row_count": len(rows),
        "latest_trade_date": latest_date,
        "rows": rows,
        "error": None,
    }


def _parse_validation_result(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "validation_result": None}
    content = path.read_text(encoding="utf-8")
    match = re.search(r"Validation result:\s*(PASS|FAIL)", content)
    return {
        "exists": True,
        "validation_result": match.group(1) if match else None,
    }


def _resolve_target_date(date_str: str | None, paths: PaperStatusPaths) -> str | None:
    if date_str:
        return _normalize_date(date_str)
    account_latest = _read_latest_account_snapshot(paths.account_snapshot_csv).get("latest_snapshot_date")
    position_latest = _read_position_snapshot(paths.position_snapshot_csv).get("latest_snapshot_date")
    current_state_latest = _latest_date_from_filenames(paths.paper_root, r"paper_current_state_(\d{8})\.json")
    plan_latest = _latest_date_from_filenames(paths.paper_root, r"daily_action_plan_(\d{8})\.md")
    candidates = [value for value in [account_latest, position_latest, current_state_latest, plan_latest] if value]
    return max(candidates) if candidates else None


def _bool_to_label(value: bool) -> str:
    return "exists" if value else "missing"


def _is_review_row_answered(row: dict[str, str]) -> bool:
    review_status = row.get("review_status", "").strip().lower()
    manual_answer = row.get("manual_answer", "").strip()
    if review_status in {"reviewed", "deferred", "not_applicable", "done", "complete", "completed"}:
        return True
    return bool(manual_answer)


def _review_row_key(row: dict[str, str]) -> tuple[str, str, str] | None:
    review_date = str(row.get("review_date") or "").strip()
    symbol = str(row.get("symbol") or "").strip().upper()
    question_id = str(row.get("question_id") or "").strip()
    if not review_date or not symbol or not question_id:
        return None
    return (review_date, symbol, question_id)


def _summarize_review_progress(
    review_template_rows: list[dict[str, str]],
    review_log_rows: list[dict[str, str]],
) -> dict[str, Any]:
    template_row_count = len(review_template_rows)
    log_row_count = len(review_log_rows)
    if template_row_count == 0:
        return {
            "review_answered_row_count": 0,
            "review_pending_row_count": 0,
            "review_done_row_count": 0,
            "review_completion_ratio": 0.0,
            "review_progress_status": "NOT_APPLICABLE",
        }

    template_keys = {
        key
        for row in review_template_rows
        if (key := _review_row_key(row)) is not None
    }
    answered_keys = {
        key
        for row in review_log_rows
        if (key := _review_row_key(row)) is not None and key in template_keys and _is_review_row_answered(row)
    }
    answered_row_count = len(answered_keys)
    pending_row_count = max(template_row_count - answered_row_count, 0)
    completion_ratio = answered_row_count / template_row_count if template_row_count else 0.0

    if log_row_count == 0:
        progress_status = "NOT_STARTED"
    elif pending_row_count == 0:
        progress_status = "DONE"
    else:
        progress_status = "PARTIAL"

    return {
        "review_answered_row_count": answered_row_count,
        "review_pending_row_count": pending_row_count,
        "review_done_row_count": answered_row_count,
        "review_completion_ratio": round(completion_ratio, 4),
        "review_progress_status": progress_status,
    }


def _detect_workflow_status(status: dict[str, Any]) -> str:
    if not status["date"]:
        return WORKFLOW_UNKNOWN
    if not status["plan_exists"]:
        return WORKFLOW_NO_PLAN
    if not status["same_date_snapshot_exists"]:
        return WORKFLOW_PLAN_READY
    if status["reports_ready"] and status["review_template_exists"] and status["review_validation_result"] == "PASS":
        if status["manual_review_log_row_count"] > 0:
            if status["review_pending_row_count"] == 0:
                return WORKFLOW_REVIEW_DONE
            return WORKFLOW_REVIEW_PARTIAL
        return WORKFLOW_REVIEW_READY
    if status["current_state_exists"] and status["account_snapshot_exists"] and status["position_snapshot_exists"]:
        return WORKFLOW_COMMITTED
    return WORKFLOW_UNKNOWN


def _next_recommended_command(
    workflow_status: str,
    date_str: str | None,
    account_id: str = "paper_default",
) -> str:
    account_suffix = "" if account_id == "paper_default" else f" --account-id {account_id}"
    if workflow_status == WORKFLOW_NO_PLAN:
        if account_id != "paper_default":
            return (
                f"paper.py plan --date {date_str.replace('-', '')}{account_suffix}"
                if date_str
                else f"paper.py plan --date YYYYMMDD{account_suffix}"
            )
        return (
            f"paper.py preview --date {date_str.replace('-', '')}{account_suffix}"
            if date_str
            else f"paper.py preview --date YYYYMMDD{account_suffix}"
        )
    if workflow_status == WORKFLOW_PLAN_READY:
        return (
            f"paper.py commit --date {date_str.replace('-', '')}{account_suffix}"
            if date_str
            else f"paper.py commit --date YYYYMMDD{account_suffix}"
        )
    if workflow_status == WORKFLOW_COMMITTED:
        return f"paper.py review{account_suffix}"
    if workflow_status == WORKFLOW_REVIEW_READY:
        return f"paper.py review-append{account_suffix}"
    if workflow_status == WORKFLOW_REVIEW_PARTIAL:
        return f"complete pending review rows then paper.py review-append{account_suffix}"
    if workflow_status == WORKFLOW_REVIEW_DONE:
        return "no immediate action"
    return "inspect status details manually"


def run_paper_status(
    date_str: str | None = None,
    *,
    paper_root: Path | None = None,
    account_paths: PaperAccountPaths | None = None,
) -> dict[str, Any]:
    resolved_root = account_paths.root if account_paths is not None else paper_root
    paths = build_paper_status_paths(resolved_root)
    target_date = _resolve_target_date(date_str, paths)
    compact_date = target_date.replace("-", "") if target_date else None

    plan_path = paths.paper_root / f"daily_action_plan_{compact_date}.md" if compact_date else None
    current_state_path = paths.paper_root / f"paper_current_state_{compact_date}.json" if compact_date else None
    daily_review_summary_path = paths.reports_dir / "paper_daily_review_summary.md"
    performance_summary_path = paths.reports_dir / "paper_performance_summary.md"
    review_template_path = paths.reviews_dir / "paper_manual_review_log_template.csv"
    review_validation_path = paths.reviews_dir / "paper_manual_review_log_validation_report.md"
    review_log_path = paths.reviews_dir / "paper_manual_review_log.csv"

    account = _read_latest_account_snapshot(paths.account_snapshot_csv)
    positions = _read_position_snapshot(paths.position_snapshot_csv)
    execution = _read_execution_log(paths.execution_log_csv)
    review_validation = _parse_validation_result(review_validation_path)

    account_row = account.get("row") or {}
    position_rows = positions.get("rows") or []
    execution_rows = execution.get("rows") or []
    position_rows_for_date = [row for row in position_rows if row.get("snapshot_date") == target_date]
    execution_rows_for_date = [row for row in execution_rows if row.get("date") == target_date]
    review_template_rows = _read_csv_rows(review_template_path) if review_template_path.exists() else []
    review_log_rows = _read_csv_rows(review_log_path) if review_log_path.exists() else []
    review_progress = _summarize_review_progress(review_template_rows, review_log_rows)

    current_state_exists = bool(current_state_path and current_state_path.exists())
    account_snapshot_exists = bool(target_date and account_row.get("snapshot_date") == target_date)
    position_snapshot_exists = bool(position_rows_for_date)
    plan_exists = bool(plan_path and plan_path.exists())
    same_date_snapshot_exists = current_state_exists or account_snapshot_exists or position_snapshot_exists
    reports_ready = daily_review_summary_path.exists() and performance_summary_path.exists()

    status = {
        "account_id": account_paths.account_id if account_paths is not None else "paper_default",
        "account_root": str(paths.paper_root),
        "legacy_default_used": bool(account_paths.legacy_default_used) if account_paths is not None else False,
        "date": target_date,
        "workflow_status": WORKFLOW_UNKNOWN,
        "latest_plan_date": _latest_date_from_filenames(paths.paper_root, r"daily_action_plan_(\d{8})\.md"),
        "latest_current_state_date": _latest_date_from_filenames(paths.paper_root, r"paper_current_state_(\d{8})\.json"),
        "latest_account_snapshot_date": account.get("latest_snapshot_date"),
        "latest_position_snapshot_date": positions.get("latest_snapshot_date"),
        "latest_execution_trade_date": execution.get("latest_trade_date"),
        "daily_action_plan": str(plan_path) if plan_path else None,
        "daily_action_plan_exists": plan_exists,
        "plan_exists": plan_exists,
        "current_state_exists": current_state_exists,
        "account_snapshot_exists": account_snapshot_exists,
        "position_snapshot_exists": position_snapshot_exists,
        "same_date_snapshot_exists": same_date_snapshot_exists,
        "execution_log_row_count": execution.get("row_count", 0),
        "execution_log_rows_for_date": len(execution_rows_for_date),
        "account_snapshot_cash": account_row.get("cash"),
        "account_snapshot_total_equity_market_value": account_row.get("total_equity_market_value"),
        "account_snapshot_unrealized_pnl": account_row.get("unrealized_pnl"),
        "account_snapshot_position_count": account_row.get("position_count"),
        "account_snapshot_symbols": account_row.get("symbols"),
        "position_snapshot_row_count_for_date": len(position_rows_for_date),
        "position_snapshot_symbols_for_date": "|".join(sorted({row.get("symbol", "") for row in position_rows_for_date if row.get("symbol")})),
        "reports_exists": reports_ready,
        "paper_daily_review_summary_exists": daily_review_summary_path.exists(),
        "paper_performance_summary_exists": performance_summary_path.exists(),
        "paper_daily_review_summary_mtime": _safe_mtime(daily_review_summary_path),
        "paper_performance_summary_mtime": _safe_mtime(performance_summary_path),
        "review_template_exists": review_template_path.exists(),
        "review_template_row_count": len(review_template_rows),
        "review_validation_exists": review_validation["exists"],
        "review_validation_result": review_validation["validation_result"],
        "manual_review_log_exists": review_log_path.exists(),
        "manual_review_log_row_count": len(review_log_rows),
        "review_answered_row_count": review_progress["review_answered_row_count"],
        "review_pending_row_count": review_progress["review_pending_row_count"],
        "review_done_row_count": review_progress["review_done_row_count"],
        "review_completion_ratio": review_progress["review_completion_ratio"],
        "review_progress_status": review_progress["review_progress_status"],
        "errors": [item for item in [account.get("error"), positions.get("error"), execution.get("error")] if item],
        "reports_ready": reports_ready,
        "paths": {
            "paper_root": str(paths.paper_root),
            "reports_dir": str(paths.reports_dir),
            "reviews_dir": str(paths.reviews_dir),
        },
    }
    status["workflow_status"] = _detect_workflow_status(status)
    status["next_recommended_command"] = _next_recommended_command(
        status["workflow_status"],
        target_date,
        status["account_id"],
    )
    return status


def format_paper_status(status: dict[str, Any], *, verbose: bool = False) -> str:
    lines = [
        "PAPER STATUS",
        f"  account_id: {status.get('account_id') or '-'}",
        f"  account_root: {status.get('account_root') or '-'}",
        f"  legacy_default_used: {str(bool(status.get('legacy_default_used'))).lower()}",
        f"  date: {status['date'] or '-'}",
        f"  workflow_status: {status['workflow_status']}",
        f"  latest_snapshot_date: {status['latest_account_snapshot_date'] or status['latest_current_state_date'] or '-'}",
        f"  daily_action_plan: {_bool_to_label(status['daily_action_plan_exists'])}",
        f"  current_state: {_bool_to_label(status['current_state_exists'])}",
        f"  account_snapshot: {_bool_to_label(status['account_snapshot_exists'])}",
        f"  position_snapshot: {_bool_to_label(status['position_snapshot_exists'])}",
        f"  execution_log_rows_for_date: {status['execution_log_rows_for_date']}",
        f"  reports: {_bool_to_label(status['reports_exists'])}",
        f"  review_template: {_bool_to_label(status['review_template_exists'])}",
        f"  review_validation: {status['review_validation_result'] or ('missing' if not status['review_validation_exists'] else 'unknown')}",
        f"  review_progress_status: {status.get('review_progress_status') or '-'}",
        f"  review_pending_row_count: {status.get('review_pending_row_count', 0)}",
        f"  manual_review_log_row_count: {status['manual_review_log_row_count']}",
        f"  same_date_snapshot_exists: {str(status['same_date_snapshot_exists']).lower()}",
        f"  next_recommended_command: {status['next_recommended_command']}",
    ]
    if verbose:
        lines.extend(
            [
                f"  latest_plan_date: {status['latest_plan_date'] or '-'}",
                f"  latest_current_state_date: {status['latest_current_state_date'] or '-'}",
                f"  latest_position_snapshot_date: {status['latest_position_snapshot_date'] or '-'}",
                f"  latest_execution_trade_date: {status['latest_execution_trade_date'] or '-'}",
                f"  review_template_row_count: {status['review_template_row_count']}",
                f"  review_answered_row_count: {status.get('review_answered_row_count', 0)}",
                f"  review_done_row_count: {status.get('review_done_row_count', 0)}",
                f"  review_completion_ratio: {status.get('review_completion_ratio', 0.0)}",
            ]
        )
        if status["errors"]:
            lines.append("  errors:")
            lines.extend([f"    - {error}" for error in status["errors"]])
    return "\n".join(lines)


def paper_status_to_json(status: dict[str, Any]) -> str:
    return json.dumps(status, ensure_ascii=False, indent=2)
