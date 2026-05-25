from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.paths import (
    paper_account_snapshot_path,
    paper_current_state_snapshot_path,
    paper_execution_log_path,
    paper_position_snapshot_path,
    paper_reports_dir,
)


class DailyReviewSummaryError(RuntimeError):
    pass


@dataclass(frozen=True)
class DailyReviewTradeItem:
    symbol: str
    side: str
    quantity: int
    actual_price: float
    trade_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "actual_price": self.actual_price,
            "trade_id": self.trade_id,
        }


def build_daily_review_summary(
    *,
    review_date: str,
    paper_root: Path | None = None,
) -> dict[str, Any]:
    root = Path(paper_root) if paper_root is not None else paper_execution_log_path().parent
    reports_dir = root / "reports"
    compact_date = review_date.replace("-", "")
    commit_report_path = reports_dir / f"manual_execution_import_commit_{compact_date}.json"
    preview_report_path = reports_dir / f"manual_execution_import_preview_{compact_date}.json"
    execution_log_path = root / paper_execution_log_path().name
    account_snapshot_csv_path = root / paper_account_snapshot_path().name
    position_snapshot_csv_path = root / paper_position_snapshot_path().name
    current_state_path = root / paper_current_state_snapshot_path(review_date).name

    commit_report = _read_json_optional(commit_report_path)
    preview_report = _read_json_optional(preview_report_path)
    ledger_rows = _read_csv_rows(execution_log_path)
    account_rows = _read_csv_rows(account_snapshot_csv_path)
    position_rows = _read_csv_rows(position_snapshot_csv_path)
    current_state = _read_json_optional(current_state_path)

    manual_rows = [
        row
        for row in ledger_rows
        if (row.get("date") or "").strip() == review_date
        and (row.get("source") or "").strip() == "notion_manual_execution"
    ]

    if commit_report:
        committed_trade_items = [
            DailyReviewTradeItem(
                symbol=str(item.get("symbol") or "").strip().upper(),
                side=str(item.get("side") or "").strip().upper(),
                quantity=int(item.get("quantity") or 0),
                actual_price=float(item.get("actual_price") or 0.0),
                trade_id=str(item.get("committed_trade_id") or "").strip(),
            )
            for item in commit_report.get("committed_rows", [])
        ]
        warning_items = _collect_warning_messages_from_commit_report(commit_report)
        committed_trade_count = len(committed_trade_items)
        warning_count = len(warning_items)
        fail_count = 0
        if committed_trade_count == 0:
            availability_status = "NO_MANUAL_EXECUTIONS"
            review_status = "NO_ACTIVITY"
        else:
            availability_status = "AVAILABLE"
            review_status = "PASS_WITH_WARNINGS" if warning_count > 0 else "PASS"
    elif manual_rows:
        committed_trade_items = [
            DailyReviewTradeItem(
                symbol=str(row.get("symbol") or "").strip().upper(),
                side=str(row.get("side") or "").strip().upper(),
                quantity=abs(int(float(row.get("shares") or 0))),
                actual_price=float(row.get("price") or 0.0),
                trade_id=str(row.get("trade_id") or "").strip(),
            )
            for row in manual_rows
        ]
        committed_trade_count = len(committed_trade_items)
        warning_items = ["Commit report missing; built review summary from execution log fallback."]
        warning_count = 1
        fail_count = 0
        availability_status = "NO_COMMIT_REPORT"
        review_status = "PASS_WITH_WARNINGS"
    else:
        committed_trade_items = []
        committed_trade_count = 0
        warning_items = []
        warning_count = 0
        fail_count = 0
        availability_status = "NO_MANUAL_EXECUTIONS" if not commit_report else "NO_ACTIVITY"
        review_status = "NO_ACTIVITY"

    if preview_report:
        fail_count = int(preview_report.get("fail_count") or 0)
        if fail_count > 0:
            review_status = "FAIL"

    latest_account_row = _latest_snapshot_row(account_rows, review_date)
    cash_end = _safe_float((latest_account_row or {}).get("cash")) or 0.0
    cash_start = _infer_cash_start(cash_end, commit_report, preview_report, committed_trade_items)
    cash_impact = cash_end - cash_start
    latest_snapshot_date = (latest_account_row or {}).get("snapshot_date") or review_date

    position_impact_summary = _build_position_impact_summary(committed_trade_items)
    position_impact_lines = _build_position_impact_lines(committed_trade_items, position_rows, review_date)

    source_paths = {
        "commit_report_path": _relative_or_empty(commit_report_path, exists=commit_report is not None),
        "preview_report_path": _relative_or_empty(preview_report_path, exists=preview_report is not None),
        "execution_log_path": _relative_or_empty(execution_log_path, exists=execution_log_path.exists()),
        "account_snapshot_path": _relative_or_empty(account_snapshot_csv_path, exists=account_snapshot_csv_path.exists()),
        "position_snapshot_path": _relative_or_empty(position_snapshot_csv_path, exists=position_snapshot_csv_path.exists()),
        "current_state_path": _relative_or_empty(current_state_path, exists=current_state is not None),
    }

    return {
        "schema_version": "daily_review_summary.v1",
        "review_date": review_date,
        "review_status": review_status,
        "availability_status": availability_status,
        "committed_trade_count": committed_trade_count,
        "warning_count": warning_count,
        "fail_count": fail_count,
        "cash_start": cash_start,
        "cash_end": cash_end,
        "cash_impact": cash_impact,
        "position_impact_summary": position_impact_summary,
        "latest_snapshot_date": latest_snapshot_date,
        "commit_report_path": source_paths["commit_report_path"],
        "preview_report_path": source_paths["preview_report_path"],
        "source_paths": source_paths,
        "committed_trade_items": [item.to_dict() for item in committed_trade_items],
        "warning_items": warning_items,
        "position_impact_lines": position_impact_lines,
    }


def build_daily_review_summary_external_key(review_date: str) -> str:
    return f"daily_review_summary:{review_date}"


def _read_json_optional(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise DailyReviewSummaryError(f"Expected JSON object: {path}")
    return payload


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows: list[dict[str, str]] = []
        for row in csv.DictReader(handle):
            normalized: dict[str, str] = {}
            for key, value in row.items():
                normalized[(key or "").replace("\ufeff", "").strip()] = value or ""
            rows.append(normalized)
    return rows


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _latest_snapshot_row(rows: list[dict[str, str]], review_date: str) -> dict[str, str] | None:
    same_day = [row for row in rows if (row.get("snapshot_date") or "").strip() == review_date]
    if same_day:
        return same_day[-1]
    earlier = [row for row in rows if (row.get("snapshot_date") or "").strip() <= review_date]
    if earlier:
        return max(earlier, key=lambda row: row.get("snapshot_date") or "")
    return None


def _infer_cash_start(
    cash_end: float,
    commit_report: dict[str, Any] | None,
    preview_report: dict[str, Any] | None,
    committed_trade_items: list[DailyReviewTradeItem],
) -> float:
    if preview_report:
        preview_cash_start = _safe_float(preview_report.get("projected_cash_start"))
        if preview_cash_start is not None:
            return preview_cash_start
    if commit_report:
        preview_path = Path(str(commit_report.get("preview_json_path") or "").strip())
        if preview_path.exists():
            preview_payload = _read_json_optional(preview_path)
            preview_cash_start = _safe_float((preview_payload or {}).get("projected_cash_start"))
            if preview_cash_start is not None:
                return preview_cash_start
    gross_cash_delta = 0.0
    for item in committed_trade_items:
        gross_cash_delta += (-item.quantity * item.actual_price) if item.side == "BUY" else (item.quantity * item.actual_price)
    return cash_end - gross_cash_delta


def _build_position_impact_summary(items: list[DailyReviewTradeItem]) -> str:
    if not items:
        return "-"
    totals: dict[str, int] = {}
    for item in items:
        delta = item.quantity if item.side == "BUY" else -item.quantity
        totals[item.symbol] = totals.get(item.symbol, 0) + delta
    ordered = [f"{symbol}:{delta:+d}" for symbol, delta in sorted(totals.items())]
    return ", ".join(ordered)


def _build_position_impact_lines(
    items: list[DailyReviewTradeItem],
    position_rows: list[dict[str, str]],
    review_date: str,
) -> list[str]:
    if not items:
        return ["No manual execution activity."]
    latest_positions = {
        (row.get("symbol") or "").strip().upper(): int(float(row.get("shares") or 0))
        for row in position_rows
        if (row.get("snapshot_date") or "").strip() == review_date
    }
    totals: dict[str, int] = {}
    for item in items:
        delta = item.quantity if item.side == "BUY" else -item.quantity
        totals[item.symbol] = totals.get(item.symbol, 0) + delta
    lines: list[str] = []
    for symbol, delta in sorted(totals.items()):
        ending = latest_positions.get(symbol)
        if ending is None:
            lines.append(f"{symbol}: {delta:+d} shares")
        else:
            lines.append(f"{symbol}: {delta:+d} shares (ending {ending})")
    return lines


def _collect_warning_messages_from_commit_report(commit_report: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    for row in commit_report.get("committed_rows", []):
        for issue in row.get("validation_issues", []):
            if str(issue.get("severity") or "").strip().upper() != "WARNING":
                continue
            code = str(issue.get("code") or "").strip()
            message = str(issue.get("message") or "").strip()
            warnings.append(f"{code}: {message}" if code else message)
    return warnings


def _relative_or_empty(path: Path, *, exists: bool) -> str:
    if not exists:
        return ""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)
