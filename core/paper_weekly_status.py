from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import PAPER_TEST_DIR, paper_account_snapshot_path, paper_execution_log_path, paper_position_snapshot_path, paper_reports_dir
from core.paper_status import (
    WORKFLOW_COMMITTED,
    WORKFLOW_NO_PLAN,
    WORKFLOW_PLAN_READY,
    WORKFLOW_REVIEW_READY,
    WORKFLOW_UNKNOWN,
)

SCHEMA_VERSION = "paper_weekly_status.v1"
WEEKLY_STATUS_MARKDOWN = "paper_weekly_status_summary.md"
WEEKLY_STATUS_JSON = "paper_weekly_status_summary.json"
LIMITATIONS = [
    "This report is generated from paper snapshots and local artifacts.",
    "Latest overwrite reports are used only as auxiliary sources.",
    "No-trade days are not treated as errors when snapshots are complete.",
    "This report does not validate investment correctness.",
]
SEVERITIES = {"HIGH", "MEDIUM", "LOW"}


def _normalize_date(date_str: str) -> str:
    clean = str(date_str).replace("-", "").strip()
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return f"{clean[:4]}-{clean[4:6]}-{clean[6:]}"


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized: dict[str, str] = {}
            for key, value in row.items():
                normalized[(key or "").replace("\ufeff", "").strip()] = value or ""
            rows.append(normalized)
        return rows


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _relative_to_project(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _parse_validation_result(path: Path) -> str | None:
    if not path.exists():
        return None
    content = path.read_text(encoding="utf-8")
    match = re.search(r"Validation result:\s*(PASS|FAIL)", content)
    return match.group(1) if match else None


def _pick_snapshot_dates(
    account_rows: list[dict[str, str]],
    *,
    days: int,
    start: str | None,
    end: str | None,
) -> list[str]:
    dates = sorted({row.get("snapshot_date", "") for row in account_rows if row.get("snapshot_date")})
    if start or end:
        start_date = _normalize_date(start) if start else min(dates, default="")
        end_date = _normalize_date(end) if end else max(dates, default="")
        return [value for value in dates if start_date <= value <= end_date]
    if days <= 0:
        raise ValueError("--days must be positive")
    return dates[-days:]


def _rows_by_date(rows: list[dict[str, str]], field: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        key = row.get(field, "")
        if not key:
            continue
        grouped.setdefault(key, []).append(row)
    return grouped


def _coverage_status(
    *,
    total_available: int,
    selected_count: int,
    days: int,
    requested_start: str | None,
    requested_end: str | None,
    actual_start: str | None,
    actual_end: str | None,
) -> str:
    if selected_count == 0:
        return "EMPTY"
    if requested_start or requested_end:
        normalized_start = _normalize_date(requested_start) if requested_start else actual_start
        normalized_end = _normalize_date(requested_end) if requested_end else actual_end
        if actual_start == normalized_start and actual_end == normalized_end:
            return "FULL"
        return "PARTIAL"
    if total_available >= days and selected_count == days:
        return "FULL"
    return "PARTIAL"


def _latest_date(rows: list[dict[str, str]], field: str) -> str | None:
    values = [row.get(field, "") for row in rows if row.get(field)]
    return max(values) if values else None


def _source_files_metadata(
    *,
    root: Path,
    account_rows: list[dict[str, str]],
    position_rows: list[dict[str, str]],
    execution_rows: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    account_path = root / paper_account_snapshot_path().name
    position_path = root / paper_position_snapshot_path().name
    execution_path = root / paper_execution_log_path().name
    daily_review_summary = root / "reports" / "paper_daily_review_summary.md"
    performance_summary = root / "reports" / "paper_performance_summary.md"
    review_template = root / "reviews" / "paper_manual_review_log_template.csv"
    review_validation = root / "reviews" / "paper_manual_review_log_validation_report.md"
    return {
        "account_snapshot": {
            "path": _relative_to_project(account_path),
            "exists": account_path.exists(),
            "latest_date": _latest_date(account_rows, "snapshot_date"),
            "row_count": len(account_rows),
        },
        "position_snapshot": {
            "path": _relative_to_project(position_path),
            "exists": position_path.exists(),
            "latest_date": _latest_date(position_rows, "snapshot_date"),
            "row_count": len(position_rows),
        },
        "execution_log": {
            "path": _relative_to_project(execution_path),
            "exists": execution_path.exists(),
            "latest_date": _latest_date(execution_rows, "date"),
            "row_count": len(execution_rows),
        },
        "daily_review_summary": {
            "path": _relative_to_project(daily_review_summary),
            "exists": daily_review_summary.exists(),
        },
        "performance_summary": {
            "path": _relative_to_project(performance_summary),
            "exists": performance_summary.exists(),
        },
        "review_template": {
            "path": _relative_to_project(review_template),
            "exists": review_template.exists(),
        },
        "review_validation_report": {
            "path": _relative_to_project(review_validation),
            "exists": review_validation.exists(),
        },
    }


def _gap(date: str | None, code: str, severity: str, message: str) -> dict[str, Any]:
    if severity not in SEVERITIES:
        raise ValueError(f"Unsupported severity: {severity}")
    return {
        "date": date,
        "code": code,
        "severity": severity,
        "message": message,
    }


def _build_operation_coverage(
    snapshot_dates: list[str],
    *,
    paper_root: Path,
    latest_snapshot_date: str | None,
    account_by_date: dict[str, list[dict[str, str]]],
    position_by_date: dict[str, list[dict[str, str]]],
    execution_by_date: dict[str, list[dict[str, str]]],
    reports_ready: bool,
    review_template_exists: bool,
    review_validation_result: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    coverage: list[dict[str, Any]] = []
    gaps: list[dict[str, Any]] = []
    for date in snapshot_dates:
        compact = date.replace("-", "")
        plan_exists = (paper_root / f"daily_action_plan_{compact}.md").exists()
        current_state_exists = (paper_root / f"paper_current_state_{compact}.json").exists()
        account_exists = bool(account_by_date.get(date))
        position_exists = bool(position_by_date.get(date))
        execution_rows = len(execution_by_date.get(date, []))
        reports_exist_for_date = bool(reports_ready and latest_snapshot_date == date)
        review_template_for_date = bool(review_template_exists and latest_snapshot_date == date)
        validation_for_date = review_validation_result if latest_snapshot_date == date else None

        missing_steps: list[str] = []
        if not plan_exists:
            missing_steps.append("MISSING_PLAN")
        if not current_state_exists:
            missing_steps.append("MISSING_CURRENT_STATE")
        if not account_exists:
            missing_steps.append("MISSING_ACCOUNT_SNAPSHOT")
        if not position_exists:
            missing_steps.append("MISSING_POSITION_SNAPSHOT")
        if current_state_exists and (not account_exists or not position_exists):
            missing_steps.append("INCOMPLETE_COMMIT_SNAPSHOT")
        if account_exists and not position_exists:
            missing_steps.append("SNAPSHOT_WITHOUT_POSITION")

        if account_exists and position_exists and current_state_exists:
            workflow_status = WORKFLOW_COMMITTED
            if reports_exist_for_date and review_template_for_date and validation_for_date == "PASS":
                workflow_status = WORKFLOW_REVIEW_READY
        elif plan_exists and not any([current_state_exists, account_exists, position_exists]):
            workflow_status = WORKFLOW_PLAN_READY
        elif not plan_exists:
            workflow_status = WORKFLOW_NO_PLAN
        else:
            workflow_status = WORKFLOW_UNKNOWN

        gap_severity = None
        if "INCOMPLETE_COMMIT_SNAPSHOT" in missing_steps:
            gap_severity = "HIGH"
            gaps.append(_gap(date, "INCOMPLETE_COMMIT_SNAPSHOT", "HIGH", "Current state exists but account/position snapshot set is incomplete"))
        elif "SNAPSHOT_WITHOUT_POSITION" in missing_steps:
            gap_severity = "HIGH"
            gaps.append(_gap(date, "MISSING_POSITION_SNAPSHOT", "HIGH", "Account snapshot exists but same-date position snapshot is missing"))
        elif workflow_status == WORKFLOW_UNKNOWN:
            gap_severity = "HIGH"
            gaps.append(_gap(date, "UNKNOWN_OR_INCOMPLETE", "HIGH", "Workflow state is incomplete or inconsistent"))
        elif validation_for_date == "FAIL":
            gap_severity = "HIGH"
            missing_steps.append("REVIEW_VALIDATION_FAILED")
            gaps.append(_gap(date, "REVIEW_VALIDATION_FAILED", "HIGH", "Review validation failed for latest review artifacts"))
        elif workflow_status == WORKFLOW_COMMITTED and not reports_exist_for_date:
            gap_severity = "MEDIUM"
            missing_steps.append("MISSING_REPORTS")
            gaps.append(_gap(date, "MISSING_REPORTS", "MEDIUM", "Committed snapshot exists but latest reports do not reflect this date"))
        elif workflow_status in {WORKFLOW_COMMITTED, WORKFLOW_REVIEW_READY} and not review_template_for_date:
            gap_severity = "MEDIUM"
            missing_steps.append("MISSING_REVIEW_TEMPLATE")
            gaps.append(_gap(date, "MISSING_REVIEW_TEMPLATE", "MEDIUM", "Committed snapshot exists but latest review template does not reflect this date"))
        elif execution_rows == 0:
            gap_severity = "LOW"
            gaps.append(_gap(date, "NO_TRADES_RECORDED", "LOW", "No execution log rows exist for this snapshot date"))

        next_command = "inspect status details manually"
        if workflow_status == WORKFLOW_NO_PLAN:
            next_command = f"paper.py preview --date {compact}"
        elif workflow_status == WORKFLOW_PLAN_READY:
            next_command = f"paper.py commit --date {compact}"
        elif workflow_status == WORKFLOW_COMMITTED:
            next_command = "paper.py review"
        elif workflow_status == WORKFLOW_REVIEW_READY:
            next_command = "no immediate action"

        coverage.append(
            {
                "date": date,
                "daily_action_plan_exists": plan_exists,
                "current_state_exists": current_state_exists,
                "account_snapshot_exists": account_exists,
                "position_snapshot_exists": position_exists,
                "execution_log_rows": execution_rows,
                "workflow_status": workflow_status,
                "missing_steps": missing_steps,
                "operation_gap_severity": gap_severity,
                "next_recommended_command": next_command,
            }
        )
    return coverage, gaps


def _compute_account_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    if not rows:
        return {
            "currency": None,
            "valuation_basis": "market_value",
            "start_equity_market_value": None,
            "end_equity_market_value": None,
            "equity_change": None,
            "equity_change_pct": None,
            "start_cash": None,
            "end_cash": None,
            "cash_change": None,
            "start_cash_ratio_market_value": None,
            "end_cash_ratio_market_value": None,
            "cash_ratio_change": None,
            "start_unrealized_pnl": None,
            "end_unrealized_pnl": None,
            "unrealized_pnl_change": None,
            "position_count_start": None,
            "position_count_end": None,
        }
    start_row = rows[0]
    end_row = rows[-1]
    start_equity = _safe_float(start_row.get("total_equity_market_value"))
    end_equity = _safe_float(end_row.get("total_equity_market_value"))
    valuation_basis = "market_value"
    if start_equity is None or end_equity is None:
        start_equity = _safe_float(start_row.get("total_equity_cost_basis"))
        end_equity = _safe_float(end_row.get("total_equity_cost_basis"))
        valuation_basis = "cost_basis_fallback"

    def delta(end_value: float | None, start_value: float | None) -> float | None:
        if end_value is None or start_value is None:
            return None
        return end_value - start_value

    equity_change = delta(end_equity, start_equity)
    equity_change_pct = None
    if equity_change is not None and start_equity not in (None, 0):
        equity_change_pct = equity_change / start_equity

    start_cash = _safe_float(start_row.get("cash"))
    end_cash = _safe_float(end_row.get("cash"))
    start_cash_ratio = _safe_float(start_row.get("cash_ratio_market_value")) or _safe_float(start_row.get("cash_ratio_cost_basis"))
    end_cash_ratio = _safe_float(end_row.get("cash_ratio_market_value")) or _safe_float(end_row.get("cash_ratio_cost_basis"))
    start_unrealized = _safe_float(start_row.get("unrealized_pnl"))
    end_unrealized = _safe_float(end_row.get("unrealized_pnl"))
    return {
        "currency": end_row.get("currency") or start_row.get("currency") or "USD",
        "valuation_basis": valuation_basis,
        "start_equity_market_value": start_equity,
        "end_equity_market_value": end_equity,
        "equity_change": equity_change,
        "equity_change_pct": equity_change_pct,
        "start_cash": start_cash,
        "end_cash": end_cash,
        "cash_change": delta(end_cash, start_cash),
        "start_cash_ratio_market_value": start_cash_ratio,
        "end_cash_ratio_market_value": end_cash_ratio,
        "cash_ratio_change": delta(end_cash_ratio, start_cash_ratio),
        "start_unrealized_pnl": start_unrealized,
        "end_unrealized_pnl": end_unrealized,
        "unrealized_pnl_change": delta(end_unrealized, start_unrealized),
        "position_count_start": _safe_int(start_row.get("position_count")),
        "position_count_end": _safe_int(end_row.get("position_count")),
    }


def _build_position_summary(start_rows: list[dict[str, str]], end_rows: list[dict[str, str]]) -> dict[str, Any]:
    start_symbols = sorted({row.get("symbol", "") for row in start_rows if row.get("symbol")})
    end_symbols = sorted({row.get("symbol", "") for row in end_rows if row.get("symbol")})
    start_set = set(start_symbols)
    end_set = set(end_symbols)

    def ranked(
        rows: list[dict[str, str]],
        key_name: str,
        *,
        reverse: bool,
        positive_only: bool = False,
        negative_only: bool = False,
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for row in rows:
            value = _safe_float(row.get(key_name))
            if value is None:
                continue
            if positive_only and value <= 0:
                continue
            if negative_only and value >= 0:
                continue
            items.append(
                {
                    "symbol": row.get("symbol"),
                    key_name: value,
                    "market_value": _safe_float(row.get("market_value")),
                    "shares": _safe_int(row.get("shares")),
                }
            )
        items.sort(key=lambda item: item.get(key_name) or 0.0, reverse=reverse)
        return items[:5]

    missing_valuation = sorted(
        {
            row.get("symbol", "")
            for row in end_rows
            if row.get("symbol") and (_safe_float(row.get("market_value")) is None or not row.get("close_price"))
        }
    )
    return {
        "start_symbols": start_symbols,
        "end_symbols": end_symbols,
        "added_symbols": sorted(end_set - start_set),
        "removed_symbols": sorted(start_set - end_set),
        "held_symbols": sorted(start_set & end_set),
        "top_positions_by_market_value": ranked(end_rows, "market_value", reverse=True),
        "top_unrealized_gain": ranked(end_rows, "unrealized_pnl", reverse=True, positive_only=True),
        "top_unrealized_loss": ranked(end_rows, "unrealized_pnl", reverse=False, negative_only=True),
        "positions_with_missing_valuation": missing_valuation,
    }


def _build_trade_summary(snapshot_dates: list[str], execution_rows: list[dict[str, str]]) -> dict[str, Any]:
    if not snapshot_dates:
        return {"trade_count": 0, "buy_count": 0, "sell_count": 0, "no_trade_days": [], "trade_dates": []}
    start = snapshot_dates[0]
    end = snapshot_dates[-1]
    filtered = [row for row in execution_rows if start <= row.get("date", "") <= end]
    by_date = _rows_by_date(filtered, "date")
    return {
        "trade_count": len(filtered),
        "buy_count": sum(1 for row in filtered if row.get("side") == "BUY"),
        "sell_count": sum(1 for row in filtered if row.get("side") == "SELL"),
        "no_trade_days": [date for date in snapshot_dates if len(by_date.get(date, [])) == 0],
        "trade_dates": sorted({row.get("date", "") for row in filtered if row.get("date")}),
    }


def _build_review_summary(
    *,
    period_start: str,
    period_end: str,
    review_bucket_rows: list[dict[str, str]],
    template_rows: list[dict[str, str]],
    manual_log_rows: list[dict[str, str]],
    validation_status: str | None,
) -> dict[str, Any]:
    bucket_counts: dict[str, int] = {}
    for row in review_bucket_rows:
        bucket = row.get("review_bucket", "")
        if bucket:
            bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1
    template_period_rows = [row for row in template_rows if period_start <= row.get("review_date", "") <= period_end]
    log_period_rows = [row for row in manual_log_rows if period_start <= row.get("review_date", "") <= period_end]
    return {
        "review_data_available": bool(review_bucket_rows or template_rows or manual_log_rows or validation_status),
        "review_bucket_counts": bucket_counts,
        "high_priority_symbols": sorted(
            {row.get("symbol", "") for row in review_bucket_rows if row.get("review_priority") == "high" and row.get("symbol")}
        ),
        "manual_review_rows": len(log_period_rows),
        "pending_review_rows": sum(1 for row in template_period_rows if row.get("review_status") == "pending"),
        "reviewed_rows": sum(1 for row in log_period_rows if row.get("review_status") == "reviewed"),
        "validation_status": validation_status,
    }


def _overall_status(gaps: list[dict[str, Any]]) -> str:
    severities = {gap["severity"] for gap in gaps}
    if "HIGH" in severities:
        return "FAIL"
    if severities & {"MEDIUM", "LOW"}:
        return "PASS_WITH_WARNINGS"
    return "PASS"


def _recommended_next_actions(
    coverage: list[dict[str, Any]],
    review_summary: dict[str, Any],
    gaps: list[dict[str, Any]],
) -> list[str]:
    actions: list[str] = []
    for gap in gaps:
        if gap["severity"] == "HIGH":
            actions.append(f"{gap['date']}: resolve HIGH gap ({gap['code']})")
    latest = coverage[-1] if coverage else None
    if latest and latest["workflow_status"] == WORKFLOW_COMMITTED:
        actions.append("paper.py review")
    elif latest and latest["workflow_status"] == WORKFLOW_PLAN_READY:
        actions.append(f"paper.py commit --date {latest['date'].replace('-', '')}")
    elif latest and latest["workflow_status"] == WORKFLOW_NO_PLAN:
        actions.append(f"paper.py preview --date {latest['date'].replace('-', '')}")
    if review_summary["high_priority_symbols"]:
        actions.append("review high priority symbols: " + "|".join(review_summary["high_priority_symbols"]))
    if review_summary["pending_review_rows"] > 0:
        actions.append("manual_review_append_needed after manual answers are completed")
    if review_summary["validation_status"] == "FAIL":
        actions.append("fix review validation errors before append")
    return actions or ["no immediate action"]


def _fmt_money(value: float | None) -> str:
    return "-" if value is None else f"${value:,.2f}"


def _fmt_ratio(value: float | None) -> str:
    return "-" if value is None else f"{value * 100:.2f}%"


def _render_markdown(summary: dict[str, Any]) -> str:
    period = summary["period"]
    account = summary["account_summary"]
    position = summary["position_summary"]
    trade = summary["trade_summary"]
    review = summary["review_summary"]
    lines = [
        "# Paper Weekly Status Summary",
        "",
        "## 1. Period",
        f"- Schema version: {summary['schema_version']}",
        f"- Basis: {period['basis']}",
        f"- Requested start: {period['requested_start'] or '-'}",
        f"- Requested end: {period['requested_end'] or '-'}",
        f"- Actual start: {period['actual_start'] or '-'}",
        f"- Actual end: {period['actual_end'] or '-'}",
        f"- Generated at: {summary['generated_at']}",
        f"- Snapshot count: {period['snapshot_count']}",
        f"- Coverage status: {period['coverage_status']}",
        f"- Included snapshot dates: {'|'.join(period['included_snapshot_dates']) or '-'}",
        f"- Latest snapshot date: {summary['latest_snapshot_date']}",
        "",
        "## 2. Overall Status",
        f"- Status: {summary['overall_status']}",
        "",
        "## 3. Operation Coverage",
        "| Date | Plan | Current State | Account Snapshot | Position Snapshot | Execution Rows | Workflow Status | Gap Severity | Missing Steps | Next Command |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for row in summary["operation_coverage"]:
        lines.append(
            f"| {row['date']} | {str(row['daily_action_plan_exists']).lower()} | {str(row['current_state_exists']).lower()} | "
            f"{str(row['account_snapshot_exists']).lower()} | {str(row['position_snapshot_exists']).lower()} | "
            f"{row['execution_log_rows']} | {row['workflow_status']} | {row['operation_gap_severity'] or '-'} | "
            f"{', '.join(row['missing_steps']) or '-'} | {row['next_recommended_command']} |"
        )
    lines.extend(
        [
            "",
            "## 4. Account Summary",
            f"- Currency: {account['currency'] or '-'}",
            f"- Valuation basis: {account['valuation_basis']}",
            f"- Start equity: {_fmt_money(account['start_equity_market_value'])}",
            f"- End equity: {_fmt_money(account['end_equity_market_value'])}",
            f"- Equity change: {_fmt_money(account['equity_change'])}",
            f"- Equity change pct: {_fmt_ratio(account['equity_change_pct'])}",
            f"- Start cash: {_fmt_money(account['start_cash'])}",
            f"- End cash: {_fmt_money(account['end_cash'])}",
            f"- Cash change: {_fmt_money(account['cash_change'])}",
            f"- Start cash ratio: {_fmt_ratio(account['start_cash_ratio_market_value'])}",
            f"- End cash ratio: {_fmt_ratio(account['end_cash_ratio_market_value'])}",
            f"- Cash ratio change: {_fmt_ratio(account['cash_ratio_change'])}",
            f"- Start unrealized pnl: {_fmt_money(account['start_unrealized_pnl'])}",
            f"- End unrealized pnl: {_fmt_money(account['end_unrealized_pnl'])}",
            f"- Unrealized pnl change: {_fmt_money(account['unrealized_pnl_change'])}",
            f"- Position count start/end: {account['position_count_start']} -> {account['position_count_end']}",
            "",
            "## 5. Position Summary",
            f"- Start symbols: {'|'.join(position['start_symbols']) or '-'}",
            f"- End symbols: {'|'.join(position['end_symbols']) or '-'}",
            f"- Added symbols: {'|'.join(position['added_symbols']) or '-'}",
            f"- Removed symbols: {'|'.join(position['removed_symbols']) or '-'}",
            f"- Held symbols: {'|'.join(position['held_symbols']) or '-'}",
            f"- Positions with missing valuation: {'|'.join(position['positions_with_missing_valuation']) or '-'}",
            "",
            "### Top Positions By Market Value",
        ]
    )
    if position["top_positions_by_market_value"]:
        for item in position["top_positions_by_market_value"]:
            lines.append(f"- {item['symbol']}: market_value={_fmt_money(item['market_value'])}")
    else:
        lines.append("- None")
    lines.extend(["", "### Top Unrealized Gain"])
    if position["top_unrealized_gain"]:
        for item in position["top_unrealized_gain"]:
            lines.append(f"- {item['symbol']}: unrealized_pnl={_fmt_money(item['unrealized_pnl'])}")
    else:
        lines.append("- None")
    lines.extend(["", "### Top Unrealized Loss"])
    if position["top_unrealized_loss"]:
        for item in position["top_unrealized_loss"]:
            lines.append(f"- {item['symbol']}: unrealized_pnl={_fmt_money(item['unrealized_pnl'])}")
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## 6. Trade Summary",
            f"- Trade count: {trade['trade_count']}",
            f"- Buy count: {trade['buy_count']}",
            f"- Sell count: {trade['sell_count']}",
            f"- Trade dates: {'|'.join(trade['trade_dates']) or '-'}",
            f"- No-trade days: {'|'.join(trade['no_trade_days']) or '-'}",
            "",
            "## 7. Review / Warning Summary",
            f"- Review data available: {str(review['review_data_available']).lower()}",
            f"- Validation status: {review['validation_status'] or '-'}",
            f"- High priority symbols: {'|'.join(review['high_priority_symbols']) or '-'}",
            f"- Manual review rows: {review['manual_review_rows']}",
            f"- Pending review rows: {review['pending_review_rows']}",
            f"- Reviewed rows: {review['reviewed_rows']}",
            f"- Review bucket counts: {review['review_bucket_counts'] or {}}",
            "",
            "## 8. Operation Gaps",
        ]
    )
    if summary["operation_gaps"]:
        for gap in summary["operation_gaps"]:
            lines.append(f"- [{gap['severity']}] {gap['date']} {gap['code']}: {gap['message']}")
    else:
        lines.append("- None")
    lines.extend(["", "## 9. Recommended Next Actions"])
    for action in summary["recommended_next_actions"]:
        lines.append(f"- {action}")
    lines.extend(["", "## 10. Source Files"])
    for key, meta in summary["source_files"].items():
        lines.append(
            f"- {key}: path={meta.get('path')}, exists={str(meta.get('exists')).lower()}, "
            f"latest_date={meta.get('latest_date') or '-'}, row_count={meta.get('row_count', '-')}"
        )
    lines.extend(["", "## 11. Limitations"])
    for item in summary["limitations"]:
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def build_paper_weekly_status_summary(
    *,
    days: int = 5,
    start: str | None = None,
    end: str | None = None,
    paper_root: Path | None = None,
) -> dict[str, Any]:
    root = Path(paper_root) if paper_root is not None else PAPER_TEST_DIR
    reports_dir = root / "reports"
    reviews_dir = root / "reviews"
    account_rows = _read_csv_rows(root / paper_account_snapshot_path().name)
    position_rows = _read_csv_rows(root / paper_position_snapshot_path().name)
    execution_rows = _read_csv_rows(root / paper_execution_log_path().name)
    if not account_rows:
        raise ValueError("paper_account_snapshot.csv is required and cannot be empty")

    all_snapshot_dates = sorted({row.get("snapshot_date", "") for row in account_rows if row.get("snapshot_date")})
    snapshot_dates = _pick_snapshot_dates(account_rows, days=days, start=start, end=end)
    latest_snapshot_date = max(all_snapshot_dates) if all_snapshot_dates else None
    requested_start = _normalize_date(start) if start else None
    requested_end = _normalize_date(end) if end else None
    actual_start = snapshot_dates[0] if snapshot_dates else None
    actual_end = snapshot_dates[-1] if snapshot_dates else None

    period = {
        "basis": "snapshot_date",
        "requested_start": requested_start,
        "requested_end": requested_end,
        "actual_start": actual_start,
        "actual_end": actual_end,
        "included_snapshot_dates": snapshot_dates,
        "snapshot_count": len(snapshot_dates),
        "coverage_status": _coverage_status(
            total_available=len(all_snapshot_dates),
            selected_count=len(snapshot_dates),
            days=days,
            requested_start=start,
            requested_end=end,
            actual_start=actual_start,
            actual_end=actual_end,
        ),
    }

    account_by_date = _rows_by_date(account_rows, "snapshot_date")
    position_by_date = _rows_by_date(position_rows, "snapshot_date")
    execution_by_date = _rows_by_date(execution_rows, "date")
    review_bucket_rows = _read_csv_rows(reports_dir / "paper_symbol_review_buckets.csv")
    template_rows = _read_csv_rows(reviews_dir / "paper_manual_review_log_template.csv")
    manual_log_rows = _read_csv_rows(reviews_dir / "paper_manual_review_log.csv")
    validation_status = _parse_validation_result(reviews_dir / "paper_manual_review_log_validation_report.md")
    reports_ready = (reports_dir / "paper_daily_review_summary.md").exists() and (reports_dir / "paper_performance_summary.md").exists()
    source_files = _source_files_metadata(
        root=root,
        account_rows=account_rows,
        position_rows=position_rows,
        execution_rows=execution_rows,
    )

    if not snapshot_dates:
        review_summary = _build_review_summary(
            period_start=requested_start or "",
            period_end=requested_end or "",
            review_bucket_rows=review_bucket_rows,
            template_rows=template_rows,
            manual_log_rows=manual_log_rows,
            validation_status=validation_status,
        )
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "period": period,
            "latest_snapshot_date": latest_snapshot_date,
            "overall_status": "FAIL",
            "operation_coverage": [],
            "account_summary": _compute_account_summary([]),
            "position_summary": _build_position_summary([], []),
            "trade_summary": _build_trade_summary([], execution_rows),
            "review_summary": review_summary,
            "operation_gaps": [_gap(requested_start or latest_snapshot_date, "NO_SNAPSHOTS_IN_RANGE", "HIGH", "No snapshot_date rows matched the requested range")],
            "recommended_next_actions": ["inspect status details manually"],
            "source_files": source_files,
            "limitations": LIMITATIONS,
        }
        return summary

    coverage, gaps = _build_operation_coverage(
        snapshot_dates,
        paper_root=root,
        latest_snapshot_date=latest_snapshot_date,
        account_by_date=account_by_date,
        position_by_date=position_by_date,
        execution_by_date=execution_by_date,
        reports_ready=reports_ready,
        review_template_exists=(reviews_dir / "paper_manual_review_log_template.csv").exists(),
        review_validation_result=validation_status,
    )
    selected_account_rows = [account_by_date[date][-1] for date in snapshot_dates if account_by_date.get(date)]
    account_summary = _compute_account_summary(selected_account_rows)
    position_summary = _build_position_summary(position_by_date.get(snapshot_dates[0], []), position_by_date.get(snapshot_dates[-1], []))
    trade_summary = _build_trade_summary(snapshot_dates, execution_rows)
    review_summary = _build_review_summary(
        period_start=snapshot_dates[0],
        period_end=snapshot_dates[-1],
        review_bucket_rows=review_bucket_rows,
        template_rows=template_rows,
        manual_log_rows=manual_log_rows,
        validation_status=validation_status,
    )
    if review_summary["validation_status"] == "FAIL":
        gaps.append(_gap(snapshot_dates[-1], "REVIEW_VALIDATION_FAILED", "HIGH", "Review validation failed for latest review artifacts"))
    if review_summary["high_priority_symbols"] and review_summary["manual_review_rows"] == 0:
        gaps.append(_gap(snapshot_dates[-1], "HIGH_PRIORITY_REVIEW_PENDING", "MEDIUM", "High priority review items exist without manual review rows"))

    summary = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "period": period,
        "latest_snapshot_date": latest_snapshot_date,
        "overall_status": _overall_status(gaps),
        "operation_coverage": coverage,
        "account_summary": account_summary,
        "position_summary": position_summary,
        "trade_summary": trade_summary,
        "review_summary": review_summary,
        "operation_gaps": gaps,
        "recommended_next_actions": _recommended_next_actions(coverage, review_summary, gaps),
        "source_files": source_files,
        "limitations": LIMITATIONS,
    }
    return summary


def write_paper_weekly_status_outputs(summary: dict[str, Any], *, reports_dir: Path | None = None) -> tuple[Path, Path]:
    target_dir = Path(reports_dir) if reports_dir is not None else paper_reports_dir()
    markdown_path = target_dir / WEEKLY_STATUS_MARKDOWN
    json_path = target_dir / WEEKLY_STATUS_JSON
    _write_text(markdown_path, _render_markdown(summary))
    _write_text(json_path, json.dumps(summary, ensure_ascii=False, indent=2))
    return markdown_path, json_path


def generate_paper_weekly_status(
    *,
    days: int = 5,
    start: str | None = None,
    end: str | None = None,
    paper_root: Path | None = None,
) -> dict[str, Any]:
    summary = build_paper_weekly_status_summary(days=days, start=start, end=end, paper_root=paper_root)
    reports_dir = (Path(paper_root) if paper_root is not None else PAPER_TEST_DIR) / "reports"
    markdown_path, json_path = write_paper_weekly_status_outputs(summary, reports_dir=reports_dir)
    return {"summary": summary, "markdown_path": markdown_path, "json_path": json_path}
