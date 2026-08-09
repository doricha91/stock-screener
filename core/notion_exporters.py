from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.daily_review_summary_exporter import (
    build_daily_review_summary,
)
from core.notion_account_keys import (
    build_account_snapshot_external_key as build_account_snapshot_external_key_with_account,
    build_benchmark_report_external_key as build_benchmark_report_external_key_with_account,
    build_daily_plan_external_key as build_daily_plan_external_key_with_account,
    build_daily_review_summary_external_key as build_daily_review_summary_external_key_with_account,
    build_legacy_account_snapshot_external_key,
    build_legacy_benchmark_report_external_key,
    build_legacy_daily_plan_external_key,
    build_legacy_daily_review_summary_external_key,
    build_legacy_weekly_report_external_key,
    build_manual_execution_canonical_key,
    build_manual_review_canonical_key,
    build_weekly_report_external_key as build_weekly_report_external_key_with_account,
    normalize_notion_account_id,
)
from core.notion_client import (
    NotionClient,
    NotionDuplicateExternalKeyError,
    notion_date,
    notion_multi_select,
    notion_number,
    notion_rich_text,
    notion_select,
    notion_title,
)
from core.notion_manual_review_schema import (
    assess_manual_review_schema,
    validate_manual_review_create_payload,
)
from core.notion_mapping import get_mapping_section, resolve_notion_property_name
from core.notion_settings import NotionSettings, get_notion_data_source_id
from core.paper_account_paths import build_paper_account_paths
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_snapshot_identity import (
    PaperSnapshotIdentityError,
    validate_snapshot_account_identity,
)
from core.paper_daily_plan_candidates import is_daily_plan_execution_candidate
from core.paper_manual_review_log_validator import validate_manual_review_log_columns
from core.paths import (
    PAPER_TEST_DIR,
    paper_account_snapshot_path,
    paper_daily_action_plan_path,
    paper_reports_dir,
)


class NotionExportError(RuntimeError):
    pass


@dataclass
class ExportResult:
    account_id: str
    target: str
    external_key: str
    legacy_external_key: str | None
    legacy_fallback_used: bool
    action: str
    page_id: str | None
    source_path: str
    data_source_key: str
    dry_run: bool


MANUAL_REVIEW_TEMPLATE_TARGET = "manual_review_template"
MANUAL_REVIEW_TEMPLATE_IMPORT_STATUS = "DRAFT"
MANUAL_EXECUTION_TEMPLATE_TARGET = "manual_execution_template"
MANUAL_EXECUTION_TEMPLATE_IMPORT_STATUS = "DRAFT"


@dataclass(frozen=True)
class ManualReviewTemplateExportCandidate:
    external_key: str
    action: str
    page_id: str | None
    symbol: str
    question_id: str
    question: str
    source_template_key: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "external_key": self.external_key,
            "action": self.action,
            "page_id": self.page_id,
            "symbol": self.symbol,
            "question_id": self.question_id,
            "question": self.question,
            "source_template_key": self.source_template_key,
        }


@dataclass(frozen=True)
class ManualExecutionTemplateExportCandidate:
    external_key: str
    action: str
    page_id: str | None
    account_id: str
    execution_date: str
    plan_date: str
    symbol: str
    side: str
    quantity: float
    plan_price: float | None
    note: str
    import_status: str = MANUAL_EXECUTION_TEMPLATE_IMPORT_STATUS

    def to_dict(self) -> dict[str, Any]:
        return {
            "external_key": self.external_key,
            "action": self.action,
            "page_id": self.page_id,
            "account_id": self.account_id,
            "execution_date": self.execution_date,
            "plan_date": self.plan_date,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "actual_price": None,
            "commission": 0,
            "currency": "USD",
            "broker": "PAPER",
            "status": "DRAFT",
            "import_status": self.import_status,
            "linked_daily_plan_key": build_daily_plan_external_key(self.execution_date, self.account_id),
            "plan_price": self.plan_price,
            "note": self.note,
        }


def _relative_to_project(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _normalize_export_date(date_str: str) -> str:
    text = str(date_str).strip()
    if not text:
        raise NotionExportError("Date must not be blank.")
    compact = text.replace("-", "")
    if len(compact) != 8 or not compact.isdigit():
        raise NotionExportError(f"Invalid date: {date_str}")
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:]}"


def _compact_date(date_str: str) -> str:
    return _normalize_export_date(date_str).replace("-", "")


def _resolve_daily_plan_export_root(
    *,
    account_id: str,
    paper_root: Path | None,
) -> Path:
    if paper_root is not None:
        return Path(paper_root)
    if account_id == "paper_default":
        return paper_daily_action_plan_path("1970-01-01").parent
    return build_paper_account_paths(
        account_id,
        allow_legacy_default=False,
        create=False,
    ).root


def _resolve_manual_review_template_root(
    *,
    account_id: str,
    paper_root: Path | None,
) -> Path:
    if paper_root is not None:
        return Path(paper_root)
    if account_id == "paper_default":
        return paper_reports_dir().parent
    return build_paper_account_paths(
        account_id,
        allow_legacy_default=False,
        create=False,
    ).root


def _resolve_snapshot_export_root(
    *,
    account_id: str,
    paper_root: Path | None,
) -> Path:
    if paper_root is not None:
        return Path(paper_root)
    if account_id == "paper_default":
        return build_paper_account_paths(
            account_id,
            account_root=PAPER_TEST_DIR,
            create=False,
        ).root
    return build_paper_account_paths(
        account_id,
        allow_legacy_default=False,
        create=False,
    ).root


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise NotionExportError(f"Missing source file: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise NotionExportError(f"Missing source file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized: dict[str, str] = {}
            for key, value in row.items():
                normalized[(key or "").replace("\ufeff", "").strip()] = value or ""
            rows.append(normalized)
        return rows


def _read_snapshot_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str] | None]:
    if not path.exists():
        raise NotionExportError(f"Missing source file: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        return rows, reader.fieldnames


def _safe_float(value: str | float | int | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (float, int)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def build_weekly_report_external_key(
    summary: dict[str, Any],
    account_id: str | None = None,
) -> str:
    period = summary.get("period") or {}
    return build_weekly_report_external_key_with_account(
        account_id,
        str(period.get("actual_start") or ""),
        str(period.get("actual_end") or ""),
    )


def build_benchmark_report_external_key(
    summary: dict[str, Any],
    account_id: str | None = None,
) -> str:
    return build_benchmark_report_external_key_with_account(
        account_id,
        str(summary.get("latest_snapshot_date") or ""),
        str(summary.get("run_mode") or ""),
    )


def build_account_snapshot_external_key(
    row: dict[str, str],
    account_id: str | None = None,
) -> str:
    return build_account_snapshot_external_key_with_account(
        account_id,
        str(row.get("snapshot_date") or ""),
    )


def build_daily_plan_external_key(plan_date: str, account_id: str | None = None) -> str:
    return build_daily_plan_external_key_with_account(account_id, plan_date)


def _paragraph_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": text},
                }
            ]
        },
    }


def _heading_block(text: str, *, level: int = 2) -> dict[str, Any]:
    heading_type = "heading_2" if level == 2 else "heading_3"
    return {
        "object": "block",
        "type": heading_type,
        heading_type: {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": text},
                }
            ]
        },
    }


def _bulleted_list_item_block(text: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [
                {
                    "type": "text",
                    "text": {"content": text},
                }
            ]
        },
    }


def _build_weekly_children(summary: dict[str, Any], markdown_path: Path, json_path: Path) -> list[dict[str, Any]]:
    period = summary["period"]
    lines = [
        f"Weekly status period: {period['actual_start']} to {period['actual_end']}",
        f"Overall status: {summary['overall_status']}",
        f"Coverage status: {period['coverage_status']}",
        f"Markdown path: {_relative_to_project(markdown_path)}",
        f"JSON path: {_relative_to_project(json_path)}",
    ]
    return [_paragraph_block("\n".join(lines))]


def _build_benchmark_children(summary: dict[str, Any], markdown_path: Path, json_path: Path) -> list[dict[str, Any]]:
    lines = [
        f"Exploratory benchmark comparison for snapshot date {summary['latest_snapshot_date']}",
        f"Run mode: {summary['run_mode']}",
        f"Official run: {summary['official_run']}",
        f"Markdown path: {_relative_to_project(markdown_path)}",
        f"JSON path: {_relative_to_project(json_path)}",
    ]
    return [_paragraph_block("\n".join(lines))]


def _build_account_snapshot_children(row: dict[str, str]) -> list[dict[str, Any]]:
    lines = [
        f"Account snapshot date: {row.get('snapshot_date')}",
        f"Symbols: {row.get('symbols') or '-'}",
        f"Valuation status: {row.get('market_valuation_status') or '-'}",
        f"Valuation price date: {row.get('valuation_price_date') or '-'}",
    ]
    return [_paragraph_block("\n".join(lines))]


def _build_daily_plan_children(summary: dict[str, Any], markdown_path: Path, json_path: Path) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = [
        _heading_block("오늘의 운영 요약"),
        _bulleted_list_item_block(f"Plan Date: {summary['plan_date']}"),
        _bulleted_list_item_block(f"Regime: {summary['regime']}"),
        _bulleted_list_item_block(f"Confirmed Trades: {summary['confirmed_trade_count']}"),
        _bulleted_list_item_block(f"Review Items: {summary['review_item_count']}"),
        _bulleted_list_item_block(f"Warnings: {summary['warning_count']}"),
    ]

    market_summary_lines = summary.get("market_summary_lines") or []
    for line in market_summary_lines:
        children.append(_bulleted_list_item_block(line))

    children.extend(
        _build_daily_plan_detail_blocks(
            title="확정 거래",
            items=summary.get("confirmed_trade_body_items") or [],
            empty_message="No confirmed trades in source markdown.",
            fallback_message=summary.get("confirmed_trade_fallback"),
        )
    )
    children.extend(
        _build_daily_plan_detail_blocks(
            title="검토 필요 항목",
            items=summary.get("review_item_body_items") or [],
            empty_message="No review-only items in source markdown.",
            fallback_message=summary.get("review_item_fallback"),
        )
    )
    children.extend(
        _build_daily_plan_detail_blocks(
            title="경고",
            items=summary.get("warning_body_items") or [],
            empty_message="No warnings in source markdown.",
            fallback_message=summary.get("warning_fallback"),
        )
    )

    parse_warnings = summary.get("parsing_warnings") or []
    if parse_warnings:
        children.append(_heading_block("파싱 참고", level=3))
        for warning in parse_warnings:
            children.append(_bulleted_list_item_block(warning))

    children.extend(
        [
            _heading_block("원천 파일"),
            _bulleted_list_item_block(f"Markdown Path: {_relative_to_project(markdown_path)}"),
            _bulleted_list_item_block(f"JSON Path: {_relative_to_project(json_path)}"),
        ]
    )
    return children


def _build_daily_review_summary_children(summary: dict[str, Any]) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = [
        _heading_block("오늘의 리뷰 요약"),
        _bulleted_list_item_block(f"Review Date: {summary['review_date']}"),
        _bulleted_list_item_block(f"Review Status: {summary['review_status']}"),
        _bulleted_list_item_block(f"Committed Trades: {summary['committed_trade_count']}"),
        _bulleted_list_item_block(f"Warnings: {summary['warning_count']}"),
        _bulleted_list_item_block(
            f"Cash Start / End / Impact: {summary['cash_start']:.2f} / {summary['cash_end']:.2f} / {summary['cash_impact']:.2f}"
        ),
        _heading_block("체결 요약"),
    ]
    trade_items = summary.get("committed_trade_items") or []
    if trade_items:
        for item in trade_items:
            children.append(
                _bulleted_list_item_block(
                    f"{item['symbol']} {item['side']} {item['quantity']} @ {item['actual_price']} - {item['trade_id']}"
                )
            )
    else:
        children.append(_paragraph_block("No committed manual execution activity for the review date."))

    children.append(_heading_block("포지션 변화"))
    for line in summary.get("position_impact_lines") or ["No position impact summary available."]:
        children.append(_bulleted_list_item_block(line))

    children.append(_heading_block("경고 / 특이사항"))
    warning_items = summary.get("warning_items") or []
    if warning_items:
        for warning in warning_items:
            children.append(_bulleted_list_item_block(warning))
    else:
        children.append(_paragraph_block("OK"))

    children.extend(
        [
            _heading_block("원천 파일"),
            _bulleted_list_item_block(f"Commit Report Path: {summary.get('commit_report_path') or '-'}"),
            _bulleted_list_item_block(f"Preview Report Path: {summary.get('preview_report_path') or '-'}"),
            _bulleted_list_item_block(
                f"Account Snapshot Path: {(summary.get('source_paths') or {}).get('account_snapshot_path') or '-'}"
            ),
            _bulleted_list_item_block(
                f"Position Snapshot Path: {(summary.get('source_paths') or {}).get('position_snapshot_path') or '-'}"
            ),
            _bulleted_list_item_block(
                f"Current State Path: {(summary.get('source_paths') or {}).get('current_state_path') or '-'}"
            ),
        ]
    )
    return children


def _build_daily_plan_detail_blocks(
    *,
    title: str,
    items: list[str],
    empty_message: str,
    fallback_message: str | None,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = [_heading_block(title)]
    if fallback_message:
        blocks.append(_paragraph_block(fallback_message))
    elif items:
        for item in items:
            blocks.append(_bulleted_list_item_block(item))
    else:
        blocks.append(_paragraph_block(empty_message))
    return blocks


def build_weekly_report_properties(
    summary: dict[str, Any],
    mapping: dict[str, str],
    *,
    account_id: str | None = None,
    markdown_path: Path,
    json_path: Path,
    synced_at: str,
) -> dict[str, Any]:
    period = summary["period"]
    resolved_account_id = normalize_notion_account_id(account_id)
    account_summary = summary.get("account_summary") or {}
    trade_summary = summary.get("trade_summary") or {}
    gaps = summary.get("operation_gaps") or []
    high_gap_count = len([item for item in gaps if item.get("severity") == "HIGH"])
    properties = {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"Weekly Report {period['actual_start']} to {period['actual_end']}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(
            build_weekly_report_external_key(summary, resolved_account_id)
        ),
        resolve_notion_property_name(mapping, "account_id"): notion_select(resolved_account_id),
        resolve_notion_property_name(mapping, "period.actual_start"): notion_date(period["actual_start"]),
        resolve_notion_property_name(mapping, "period.actual_end"): notion_date(period["actual_end"]),
        resolve_notion_property_name(mapping, "latest_snapshot_date"): notion_date(summary["latest_snapshot_date"]),
        resolve_notion_property_name(mapping, "period.coverage_status"): notion_select(period["coverage_status"]),
        resolve_notion_property_name(mapping, "overall_status"): notion_select(summary["overall_status"]),
        resolve_notion_property_name(mapping, "period.snapshot_count"): notion_number(period["snapshot_count"]),
        resolve_notion_property_name(mapping, "account_summary.end_equity_market_value"): notion_number(
            account_summary.get("end_equity_market_value", 0.0)
        ),
        resolve_notion_property_name(mapping, "account_summary.equity_change_pct"): notion_number(
            account_summary.get("equity_change_pct", 0.0)
        ),
        resolve_notion_property_name(mapping, "account_summary.end_cash_ratio_market_value"): notion_number(
            account_summary.get("end_cash_ratio_market_value", 0.0)
        ),
        resolve_notion_property_name(mapping, "trade_summary.trade_count"): notion_number(
            trade_summary.get("trade_count", 0)
        ),
        resolve_notion_property_name(mapping, "operation_gaps.count"): notion_number(len(gaps)),
        resolve_notion_property_name(mapping, "operation_gaps.high_count"): notion_number(high_gap_count),
        resolve_notion_property_name(mapping, "markdown_path"): notion_rich_text(_relative_to_project(markdown_path)),
        resolve_notion_property_name(mapping, "json_path"): notion_rich_text(_relative_to_project(json_path)),
        resolve_notion_property_name(mapping, "schema_version"): notion_rich_text(
            summary.get("schema_version", "")
        ),
        resolve_notion_property_name(mapping, "synced_at"): notion_rich_text(synced_at),
        resolve_notion_property_name(mapping, "sync_status"): notion_select("SYNCED"),
    }
    return properties


def build_benchmark_report_properties(
    summary: dict[str, Any],
    mapping: dict[str, str],
    *,
    account_id: str | None = None,
    markdown_path: Path,
    json_path: Path,
    synced_at: str,
) -> dict[str, Any]:
    resolved_account_id = normalize_notion_account_id(account_id)
    benchmarks = summary.get("summary", {}).get("benchmarks", {})
    paper_summary = summary.get("summary", {}).get("paper", {})
    properties = {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"Benchmark Report {summary['latest_snapshot_date']} {summary['run_mode']}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(
            build_benchmark_report_external_key(summary, resolved_account_id)
        ),
        resolve_notion_property_name(mapping, "account_id"): notion_select(resolved_account_id),
        resolve_notion_property_name(mapping, "latest_snapshot_date"): notion_date(summary["latest_snapshot_date"]),
        resolve_notion_property_name(mapping, "run_mode"): notion_select(summary["run_mode"].upper()),
        resolve_notion_property_name(mapping, "official_run"): notion_select(
            "TRUE" if summary.get("official_run") else "FALSE"
        ),
        resolve_notion_property_name(mapping, "availability_status"): notion_select(
            summary.get("availability_status", "UNKNOWN")
        ),
        resolve_notion_property_name(mapping, "summary.paper.paper_return"): notion_number(
            paper_summary.get("paper_return", 0.0)
        ),
        resolve_notion_property_name(mapping, "summary.benchmarks.SPY.benchmark_return"): notion_number(
            benchmarks.get("SPY", {}).get("benchmark_return", 0.0)
        ),
        resolve_notion_property_name(mapping, "summary.benchmarks.QQQ.benchmark_return"): notion_number(
            benchmarks.get("QQQ", {}).get("benchmark_return", 0.0)
        ),
        resolve_notion_property_name(mapping, "summary.benchmarks.CASH.benchmark_return"): notion_number(
            benchmarks.get("CASH", {}).get("benchmark_return", 0.0)
        ),
        resolve_notion_property_name(mapping, "summary.benchmarks.SPY.excess_return"): notion_number(
            benchmarks.get("SPY", {}).get("excess_return", 0.0)
        ),
        resolve_notion_property_name(mapping, "summary.benchmarks.QQQ.excess_return"): notion_number(
            benchmarks.get("QQQ", {}).get("excess_return", 0.0)
        ),
        resolve_notion_property_name(mapping, "summary.benchmarks.CASH.excess_return"): notion_number(
            benchmarks.get("CASH", {}).get("excess_return", 0.0)
        ),
        resolve_notion_property_name(mapping, "summary.paper.paper_max_drawdown"): notion_number(
            paper_summary.get("paper_max_drawdown", 0.0)
        ),
        resolve_notion_property_name(mapping, "summary.benchmarks.SPY.benchmark_max_drawdown"): notion_number(
            benchmarks.get("SPY", {}).get("benchmark_max_drawdown", 0.0)
        ),
        resolve_notion_property_name(mapping, "summary.benchmarks.QQQ.benchmark_max_drawdown"): notion_number(
            benchmarks.get("QQQ", {}).get("benchmark_max_drawdown", 0.0)
        ),
        resolve_notion_property_name(mapping, "markdown_path"): notion_rich_text(_relative_to_project(markdown_path)),
        resolve_notion_property_name(mapping, "json_path"): notion_rich_text(_relative_to_project(json_path)),
        resolve_notion_property_name(mapping, "schema_version"): notion_rich_text(
            summary.get("schema_version", "")
        ),
        resolve_notion_property_name(mapping, "synced_at"): notion_rich_text(synced_at),
        resolve_notion_property_name(mapping, "sync_status"): notion_select("SYNCED"),
    }
    return properties


def build_account_snapshot_properties(
    row: dict[str, str],
    mapping: dict[str, str],
    *,
    account_id: str | None = None,
    synced_at: str,
) -> dict[str, Any]:
    resolved_account_id = normalize_notion_account_id(account_id)
    total_equity_market_value = _safe_float(row.get("total_equity_market_value")) or 0.0
    total_equity_cost_basis = _safe_float(row.get("total_equity_cost_basis")) or 0.0
    properties = {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"Account Snapshot {row.get('snapshot_date')}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(
            build_account_snapshot_external_key(row, resolved_account_id)
        ),
        resolve_notion_property_name(mapping, "account_id"): notion_select(resolved_account_id),
        resolve_notion_property_name(mapping, "snapshot_date"): notion_date(row["snapshot_date"]),
        resolve_notion_property_name(mapping, "initial_cash"): notion_number(
            _safe_float(row.get("initial_cash")) or 0.0
        ),
        resolve_notion_property_name(mapping, "cash"): notion_number(
            _safe_float(row.get("cash")) or 0.0
        ),
        resolve_notion_property_name(mapping, "total_equity_market_value"): notion_number(total_equity_market_value),
        resolve_notion_property_name(mapping, "total_equity_cost_basis"): notion_number(total_equity_cost_basis),
        resolve_notion_property_name(mapping, "unrealized_pnl"): notion_number(
            _safe_float(row.get("unrealized_pnl")) or 0.0
        ),
        resolve_notion_property_name(mapping, "cash_ratio_market_value"): notion_number(
            _safe_float(row.get("cash_ratio_market_value")) or 0.0
        ),
        resolve_notion_property_name(mapping, "cash_ratio_cost_basis"): notion_number(
            _safe_float(row.get("cash_ratio_cost_basis")) or 0.0
        ),
        resolve_notion_property_name(mapping, "position_count"): notion_number(
            int(float(row.get("position_count") or 0))
        ),
        resolve_notion_property_name(mapping, "symbols"): notion_rich_text(row.get("symbols") or ""),
        resolve_notion_property_name(mapping, "market_valuation_status"): notion_select(
            (row.get("market_valuation_status") or "UNKNOWN").upper()
        ),
        resolve_notion_property_name(mapping, "valuation_price_date"): notion_date(
            row.get("valuation_price_date") or row["snapshot_date"]
        ),
        resolve_notion_property_name(mapping, "synced_at"): notion_rich_text(synced_at),
        resolve_notion_property_name(mapping, "sync_status"): notion_select("SYNCED"),
    }
    return properties


def build_daily_plan_properties(
    summary: dict[str, Any],
    mapping: dict[str, str],
    *,
    account_id: str | None = None,
    markdown_path: Path,
    json_path: Path,
    synced_at: str,
) -> dict[str, Any]:
    resolved_account_id = normalize_notion_account_id(account_id)
    properties = {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"Daily Plan {summary['plan_date']}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(
            build_daily_plan_external_key(summary["plan_date"], resolved_account_id)
        ),
        resolve_notion_property_name(mapping, "account_id"): notion_select(resolved_account_id),
        resolve_notion_property_name(mapping, "plan_date"): notion_date(summary["plan_date"]),
        resolve_notion_property_name(mapping, "regime"): notion_select(summary["regime"]),
        resolve_notion_property_name(mapping, "confirmed_trade_count"): notion_number(
            summary["confirmed_trade_count"]
        ),
        resolve_notion_property_name(mapping, "review_item_count"): notion_number(
            summary["review_item_count"]
        ),
        resolve_notion_property_name(mapping, "warning_count"): notion_number(
            summary["warning_count"]
        ),
        resolve_notion_property_name(mapping, "markdown_path"): notion_rich_text(_relative_to_project(markdown_path)),
        resolve_notion_property_name(mapping, "json_path"): notion_rich_text(_relative_to_project(json_path)),
        resolve_notion_property_name(mapping, "schema_version"): notion_rich_text(
            str(summary.get("schema_version", ""))
        ),
        resolve_notion_property_name(mapping, "synced_at"): notion_rich_text(synced_at),
        resolve_notion_property_name(mapping, "sync_status"): notion_select("SYNCED"),
    }
    return properties


def build_daily_review_summary_properties(
    summary: dict[str, Any],
    mapping: dict[str, str],
    *,
    account_id: str | None = None,
    synced_at: str,
) -> dict[str, Any]:
    resolved_account_id = normalize_notion_account_id(account_id)
    properties = {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"Daily Review Summary {summary['review_date']}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(
            build_daily_review_summary_external_key_with_account(
                resolved_account_id,
                summary["review_date"],
            )
        ),
        resolve_notion_property_name(mapping, "account_id"): notion_select(resolved_account_id),
        resolve_notion_property_name(mapping, "review_date"): notion_date(summary["review_date"]),
        resolve_notion_property_name(mapping, "review_status"): notion_select(summary["review_status"]),
        resolve_notion_property_name(mapping, "availability_status"): notion_select(summary["availability_status"]),
        resolve_notion_property_name(mapping, "committed_trade_count"): notion_number(summary["committed_trade_count"]),
        resolve_notion_property_name(mapping, "warning_count"): notion_number(summary["warning_count"]),
        resolve_notion_property_name(mapping, "fail_count"): notion_number(summary["fail_count"]),
        resolve_notion_property_name(mapping, "cash_start"): notion_number(summary["cash_start"]),
        resolve_notion_property_name(mapping, "cash_end"): notion_number(summary["cash_end"]),
        resolve_notion_property_name(mapping, "cash_impact"): notion_number(summary["cash_impact"]),
        resolve_notion_property_name(mapping, "position_impact_summary"): notion_rich_text(
            summary["position_impact_summary"]
        ),
        resolve_notion_property_name(mapping, "commit_report_path"): notion_rich_text(
            summary.get("commit_report_path") or ""
        ),
        resolve_notion_property_name(mapping, "preview_report_path"): notion_rich_text(
            summary.get("preview_report_path") or ""
        ),
        resolve_notion_property_name(mapping, "latest_snapshot_date"): notion_date(
            summary["latest_snapshot_date"]
        ),
        resolve_notion_property_name(mapping, "schema_version"): notion_rich_text(
            summary["schema_version"]
        ),
        resolve_notion_property_name(mapping, "synced_at"): notion_rich_text(synced_at),
        resolve_notion_property_name(mapping, "sync_status"): notion_select("SYNCED"),
    }
    return properties


def load_manual_review_template_rows(
    *,
    template_path: Path,
    review_date: str,
) -> list[dict[str, str]]:
    try:
        with template_path.open("r", encoding="utf-8-sig", newline="") as handle:
            validate_manual_review_log_columns(csv.DictReader(handle).fieldnames)
    except FileNotFoundError as exc:
        raise NotionExportError(f"Missing source file: {template_path}") from exc
    except ValueError as exc:
        raise NotionExportError(str(exc)) from exc
    rows = _read_csv_rows(template_path)
    normalized_review_date = _normalize_export_date(review_date)
    if not rows:
        return []
    filtered = []
    for row in rows:
        row_review_date = str(row.get("review_date") or "").strip()
        if not row_review_date:
            continue
        if _normalize_export_date(row_review_date) == normalized_review_date:
            filtered.append(row)
    if not filtered:
        raise NotionExportError(f"No manual review template rows found for {normalized_review_date}: {template_path}")
    return filtered


def build_manual_review_template_properties(
    row: dict[str, str],
    mapping: dict[str, str],
    *,
    account_id: str,
    review_date: str,
    external_key: str,
) -> dict[str, Any]:
    symbol = str(row.get("symbol") or "").strip().upper()
    question_id = str(row.get("question_id") or "").strip()
    question = str(row.get("question_text") or "").strip()
    source_template_key = str(row.get("source_worksheet_path") or "").strip()
    return {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"{review_date} {account_id} {symbol} {question_id}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(external_key),
        resolve_notion_property_name(mapping, "account_id"): notion_select(account_id),
        resolve_notion_property_name(mapping, "review_date"): notion_date(review_date),
        resolve_notion_property_name(mapping, "symbol"): notion_rich_text(symbol),
        resolve_notion_property_name(mapping, "question_id"): notion_rich_text(question_id),
        resolve_notion_property_name(mapping, "question"): notion_rich_text(question),
        resolve_notion_property_name(mapping, "manual_answer"): notion_rich_text(""),
        resolve_notion_property_name(mapping, "review_status"): notion_select("pending"),
        resolve_notion_property_name(mapping, "follow_up_needed"): notion_select("false"),
        resolve_notion_property_name(mapping, "review_tag"): notion_multi_select(
            [str(row.get("review_tag") or "").strip()]
        ),
        resolve_notion_property_name(mapping, "reviewer_note"): notion_rich_text(""),
        resolve_notion_property_name(mapping, "source_template_key"): notion_rich_text(source_template_key),
        resolve_notion_property_name(mapping, "import_status"): notion_select(MANUAL_REVIEW_TEMPLATE_IMPORT_STATUS),
    }


def build_manual_review_template_update_properties(
    row: dict[str, str],
    mapping: dict[str, str],
    *,
    account_id: str,
    review_date: str,
    external_key: str,
) -> dict[str, Any]:
    """Update generated identity/question fields without replacing operator-owned review progress."""
    symbol = str(row.get("symbol") or "").strip().upper()
    question_id = str(row.get("question_id") or "").strip()
    question = str(row.get("question_text") or "").strip()
    source_template_key = str(row.get("source_worksheet_path") or "").strip()
    return {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"{review_date} {account_id} {symbol} {question_id}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(external_key),
        resolve_notion_property_name(mapping, "account_id"): notion_select(account_id),
        resolve_notion_property_name(mapping, "review_date"): notion_date(review_date),
        resolve_notion_property_name(mapping, "symbol"): notion_rich_text(symbol),
        resolve_notion_property_name(mapping, "question_id"): notion_rich_text(question_id),
        resolve_notion_property_name(mapping, "question"): notion_rich_text(question),
        resolve_notion_property_name(mapping, "source_template_key"): notion_rich_text(source_template_key),
    }


def _daily_plan_sidecar_path_for_date(root: Path, date_str: str) -> Path:
    compact_date = _compact_date(date_str)
    return root / f"daily_action_plan_{compact_date}.json"


def _load_daily_plan_sidecar_for_manual_execution_template(
    *,
    account_id: str,
    date_str: str,
    paper_root: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    normalized_date = _normalize_export_date(date_str)
    root = _resolve_daily_plan_export_root(account_id=account_id, paper_root=paper_root)
    sidecar_path = _daily_plan_sidecar_path_for_date(root, normalized_date)
    payload = _read_json(sidecar_path)
    sidecar_account_id = str(payload.get("account_id") or "").strip()
    if not sidecar_account_id:
        raise NotionExportError(f"Daily Plan sidecar account_id is required: {sidecar_path}")
    if sidecar_account_id != account_id:
        raise NotionExportError(
            f"Daily Plan sidecar account_id mismatch: cli={account_id}, sidecar={sidecar_account_id}"
        )
    plan_date = _normalize_export_date(str(payload.get("plan_date") or normalized_date))
    trade_date_raw = str(payload.get("trade_date") or "").strip()
    trade_date = _normalize_export_date(trade_date_raw) if trade_date_raw else plan_date
    if trade_date != normalized_date and plan_date != normalized_date:
        raise NotionExportError(
            f"Daily Plan sidecar date mismatch: requested={normalized_date}, "
            f"plan_date={plan_date}, trade_date={trade_date}"
        )
    return sidecar_path, payload


def _manual_execution_note_from_item(item: dict[str, Any]) -> str:
    price = item.get("price")
    reason = str(item.get("reason") or "").strip()
    note = f"generated_from_daily_plan; plan_price={'' if price is None else price}; reason={reason}"
    return note.strip()


def _manual_execution_template_candidates_from_sidecar(
    payload: dict[str, Any],
    *,
    account_id: str,
) -> tuple[str, list[ManualExecutionTemplateExportCandidate], list[dict[str, str]]]:
    trade_date_raw = str(payload.get("trade_date") or payload.get("plan_date") or "").strip()
    if not trade_date_raw:
        raise NotionExportError("Daily Plan sidecar plan_date/trade_date is required.")
    trade_date = _normalize_export_date(trade_date_raw)
    items = payload.get("items") or []
    if not isinstance(items, list):
        raise NotionExportError("Daily Plan sidecar items must be a list.")

    candidates: list[ManualExecutionTemplateExportCandidate] = []
    failed: list[dict[str, str]] = []
    sequence_by_key: dict[tuple[str, str], int] = {}
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            failed.append({"index": str(index), "error": "item is not an object"})
            continue
        side = str(item.get("action") or "").strip().upper()
        if side not in {"BUY", "SELL"}:
            continue
        symbol = str(item.get("symbol") or "").strip().upper()
        quantity = _safe_float(item.get("quantity"))
        if not is_daily_plan_execution_candidate(item):
            failed.append(
                {
                    "index": str(index),
                    "symbol": symbol,
                    "side": side,
                    "error": "BUY/SELL items require symbol and positive quantity.",
                }
            )
            continue
        sequence_key = (symbol, side)
        sequence_by_key[sequence_key] = sequence_by_key.get(sequence_key, 0) + 1
        sequence = sequence_by_key[sequence_key]
        external_key = build_manual_execution_canonical_key(
            account_id,
            trade_date,
            symbol,
            side,
            sequence,
        )
        candidates.append(
            ManualExecutionTemplateExportCandidate(
                external_key=external_key,
                action="create",
                page_id=None,
                account_id=account_id,
                execution_date=trade_date,
                plan_date=trade_date,
                symbol=symbol,
                side=side,
                quantity=quantity,
                plan_price=_safe_float(item.get("price")),
                note=_manual_execution_note_from_item(item),
            )
        )
    return trade_date, candidates, failed


def build_manual_execution_template_properties(
    candidate: ManualExecutionTemplateExportCandidate,
    mapping: dict[str, str],
    *,
    broker_property_type: str = "select",
) -> dict[str, Any]:
    broker_property = (
        notion_rich_text("PAPER") if broker_property_type == "rich_text" else notion_select("PAPER")
    )
    return {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"{candidate.execution_date} {candidate.account_id} {candidate.side} {candidate.symbol}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(candidate.external_key),
        resolve_notion_property_name(mapping, "account_id"): notion_select(candidate.account_id),
        resolve_notion_property_name(mapping, "execution_date"): notion_date(candidate.execution_date),
        resolve_notion_property_name(mapping, "plan_date"): notion_date(candidate.plan_date),
        resolve_notion_property_name(mapping, "symbol"): notion_rich_text(candidate.symbol),
        resolve_notion_property_name(mapping, "side"): notion_select(candidate.side),
        resolve_notion_property_name(mapping, "quantity"): notion_number(candidate.quantity),
        resolve_notion_property_name(mapping, "commission"): notion_number(0),
        resolve_notion_property_name(mapping, "currency"): notion_select("USD"),
        resolve_notion_property_name(mapping, "broker"): broker_property,
        resolve_notion_property_name(mapping, "status"): notion_select("DRAFT"),
        resolve_notion_property_name(mapping, "linked_daily_plan_key"): notion_rich_text(
            build_daily_plan_external_key(candidate.execution_date, candidate.account_id)
        ),
        resolve_notion_property_name(mapping, "note"): notion_rich_text(candidate.note),
        resolve_notion_property_name(mapping, "import_status"): notion_select(candidate.import_status),
    }


def _get_notion_property_schema(
    client: NotionClient | None,
    data_source_id: str,
    property_name: str,
) -> dict[str, Any]:
    if client is None or not hasattr(client, "get_data_source_schema"):
        return {}
    try:
        schema = client.get_data_source_schema(data_source_id)
    except Exception:
        return {}
    properties = schema.get("properties") or {}
    property_schema = properties.get(property_name) or {}
    return property_schema if isinstance(property_schema, dict) else {}


def _select_option_names(property_schema: dict[str, Any]) -> set[str]:
    property_type = str(property_schema.get("type") or "")
    options = (property_schema.get(property_type) or {}).get("options") or []
    return {str(option.get("name") or "") for option in options if isinstance(option, dict)}


def _resolve_manual_execution_template_import_status(property_schema: dict[str, Any]) -> str:
    options = _select_option_names(property_schema)
    if not options or MANUAL_EXECUTION_TEMPLATE_IMPORT_STATUS in options:
        return MANUAL_EXECUTION_TEMPLATE_IMPORT_STATUS
    if "NOT_IMPORTED" in options:
        return "NOT_IMPORTED"
    return MANUAL_EXECUTION_TEMPLATE_IMPORT_STATUS


def _manual_review_template_candidate_from_row(
    row: dict[str, str],
    *,
    account_id: str,
    review_date: str,
    action: str,
    page_id: str | None,
) -> ManualReviewTemplateExportCandidate:
    symbol = str(row.get("symbol") or "").strip().upper()
    question_id = str(row.get("question_id") or "").strip()
    return ManualReviewTemplateExportCandidate(
        external_key=build_manual_review_canonical_key(account_id, review_date, symbol, question_id),
        action=action,
        page_id=page_id,
        symbol=symbol,
        question_id=question_id,
        question=str(row.get("question_text") or "").strip(),
        source_template_key=str(row.get("source_worksheet_path") or "").strip(),
    )


def _extract_plan_section(markdown: str, heading_prefix: str, next_heading_prefixes: tuple[str, ...]) -> str:
    lines = markdown.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith(heading_prefix):
            start = index + 1
            break
    if start is None:
        raise NotionExportError(f"Missing daily plan section: {heading_prefix}")

    end = len(lines)
    for index in range(start, len(lines)):
        line = lines[index]
        if any(line.startswith(prefix) for prefix in next_heading_prefixes):
            end = index
            break
    return "\n".join(lines[start:end]).strip()


def _extract_plan_section_optional(
    markdown: str,
    heading_prefix: str,
    next_heading_prefixes: tuple[str, ...],
) -> tuple[str | None, str | None]:
    try:
        return _extract_plan_section(markdown, heading_prefix, next_heading_prefixes), None
    except NotionExportError:
        return None, f"Section {heading_prefix.strip()} could not be parsed. See source markdown path."


def _count_markdown_table_rows(section: str) -> int:
    rows = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(rows) < 3:
        return 0

    data_rows = rows[2:]
    count = 0
    for row in data_rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        if not cells:
            continue
        if all(cell in {"", "-", "[ ]"} for cell in cells):
            continue
        count += 1
    return count


def _strip_markdown_emphasis(text: str) -> str:
    cleaned = text.replace("**", "").replace("`", "").strip()
    return re.sub(r"\s+", " ", cleaned)


def _parse_markdown_table_rows(section: str | None) -> list[dict[str, str]]:
    if not section:
        return []

    rows = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    if len(rows) < 3:
        return []

    headers = [_strip_markdown_emphasis(cell) for cell in rows[0].strip("|").split("|")]
    parsed: list[dict[str, str]] = []
    for row in rows[2:]:
        cells = [_strip_markdown_emphasis(cell) for cell in row.strip("|").split("|")]
        if not cells:
            continue
        if all(cell in {"", "-", "[ ]"} for cell in cells):
            continue
        padded = cells + [""] * max(0, len(headers) - len(cells))
        parsed.append({headers[index]: padded[index] for index in range(len(headers))})
    return parsed


def _format_confirmed_trade_items(rows: list[dict[str, str]]) -> list[str]:
    items: list[str] = []
    for row in rows:
        trade_type = row.get("Type") or row.get("???") or "-"
        symbol = row.get("Symbol") or row.get("종목") or "-"
        shares = row.get("Shares") or row.get("수량") or "-"
        price = row.get("Ref Price") or row.get("예상단가") or "-"
        reason = row.get("Reason") or row.get("매매 사유") or "-"
        items.append(f"{trade_type} {symbol} {shares} @ {price} - {reason}")
    return items


def _format_review_item_body_items(rows: list[dict[str, str]]) -> list[str]:
    items: list[str] = []
    for row in rows:
        symbol = row.get("Symbol") or "-"
        shares = row.get("Shares") or "-"
        price = row.get("Ref Price") or "-"
        reason = row.get("Reason") or "-"
        note = row.get("Note") or "-"
        items.append(f"{symbol} {shares} @ {price} - {reason} ({note})")
    return items


def _format_warning_body_items(rows: list[dict[str, str]]) -> list[str]:
    items: list[str] = []
    for row in rows:
        symbol = row.get("Symbol") or "-"
        severity = row.get("Severity") or "-"
        reason = row.get("Reason") or "-"
        note = row.get("Note") or "-"
        items.append(f"{symbol} [{severity}] {reason} - {note}")
    return items


def summarize_daily_plan_artifacts(
    *,
    markdown_path: Path,
    config_snapshot_path: Path,
) -> dict[str, Any]:
    summary = _read_json(config_snapshot_path)
    plan_date = str(summary.get("plan_date") or "").strip()
    if not plan_date:
        raise NotionExportError(f"Missing plan_date in config snapshot: {config_snapshot_path}")

    regime = (
        str((summary.get("market_state") or {}).get("regime") or "").strip()
        or str((summary.get("market_status_summary") or {}).get("regime") or "").strip()
    )
    if not regime:
        raise NotionExportError(f"Missing regime in config snapshot: {config_snapshot_path}")

    if not markdown_path.exists():
        raise NotionExportError(f"Missing source file: {markdown_path}")
    markdown = markdown_path.read_text(encoding="utf-8")

    market_section, market_section_error = _extract_plan_section_optional(
        markdown,
        "## 1. ",
        ("## 2. ",),
    )
    confirmed_section, confirmed_section_error = _extract_plan_section_optional(
        markdown,
        "## 4. ",
        ("## 4-0. ",),
    )
    review_section, review_section_error = _extract_plan_section_optional(
        markdown,
        "## 4-0. ",
        ("## 4-0-1. ",),
    )
    warning_section, warning_section_error = _extract_plan_section_optional(
        markdown,
        "## 4-0-1. ",
        ("## 4-1. ",),
    )

    market_summary_lines = []
    if market_section:
        for line in market_section.splitlines():
            cleaned = _strip_markdown_emphasis(line.lstrip("- ").strip())
            if cleaned:
                market_summary_lines.append(cleaned)

    confirmed_rows = _parse_markdown_table_rows(confirmed_section)
    review_rows = _parse_markdown_table_rows(review_section)
    warning_rows = _parse_markdown_table_rows(warning_section)

    parsing_warnings = [
        warning
        for warning in (
            market_section_error,
            confirmed_section_error,
            review_section_error,
            warning_section_error,
        )
        if warning
    ]

    return {
        "schema_version": f"paper_daily_plan.v{summary.get('schema_version', 1)}",
        "plan_date": plan_date,
        "regime": regime.upper(),
        "confirmed_trade_count": _count_markdown_table_rows(confirmed_section or ""),
        "review_item_count": _count_markdown_table_rows(review_section or ""),
        "warning_count": _count_markdown_table_rows(warning_section or ""),
        "market_summary_lines": market_summary_lines[:3],
        "confirmed_trade_body_items": _format_confirmed_trade_items(confirmed_rows),
        "review_item_body_items": _format_review_item_body_items(review_rows),
        "warning_body_items": _format_warning_body_items(warning_rows),
        "confirmed_trade_fallback": confirmed_section_error,
        "review_item_fallback": review_section_error,
        "warning_fallback": warning_section_error,
        "parsing_warnings": parsing_warnings,
    }


def _latest_paper_daily_plan_artifacts(root: Path) -> tuple[Path, Path]:
    pattern = re.compile(r"daily_action_plan_(\d{8})\.md$")
    candidates: list[tuple[str, Path, Path]] = []
    for markdown_path in root.glob("daily_action_plan_*.md"):
        match = pattern.match(markdown_path.name)
        if not match:
            continue
        compact_date = match.group(1)
        config_snapshot_path = root / "config_snapshots" / f"paper_config_snapshot_{compact_date}.json"
        if not config_snapshot_path.exists():
            continue
        candidates.append((compact_date, markdown_path, config_snapshot_path))

    if not candidates:
        raise NotionExportError(
            "No daily plan artifacts found. Expected daily_action_plan_YYYYMMDD.md with matching "
            f"config_snapshots/paper_config_snapshot_YYYYMMDD.json under {root}."
        )

    _, markdown_path, config_snapshot_path = max(candidates, key=lambda item: item[0])
    return markdown_path, config_snapshot_path


def _paper_daily_plan_artifacts_for_date(root: Path, date_str: str) -> tuple[Path, Path]:
    compact_date = _compact_date(date_str)
    markdown_path = root / f"daily_action_plan_{compact_date}.md"
    config_snapshot_path = root / "config_snapshots" / f"paper_config_snapshot_{compact_date}.json"
    if not markdown_path.exists() or not config_snapshot_path.exists():
        raise NotionExportError(
            "No daily plan artifacts found for "
            f"{_normalize_export_date(date_str)} under {root}. Expected {markdown_path.name} "
            f"with matching config_snapshots/{config_snapshot_path.name}."
        )
    return markdown_path, config_snapshot_path


def _upsert_or_dry_run(
    *,
    client: NotionClient | None,
    data_source_id: str | None,
    account_id: str,
    external_key: str,
    legacy_external_key: str | None,
    external_key_property_name: str,
    properties: dict[str, Any],
    children: list[dict[str, Any]],
    target: str,
    source_path: Path,
    data_source_key: str,
    dry_run: bool,
    refresh_children_on_update: bool = False,
) -> ExportResult:
    if dry_run:
        return ExportResult(
            account_id=account_id,
            target=target,
            external_key=external_key,
            legacy_external_key=legacy_external_key,
            legacy_fallback_used=False,
            action="dry_run",
            page_id=None,
            source_path=_relative_to_project(source_path),
            data_source_key=data_source_key,
            dry_run=True,
        )
    if client is None:
        raise NotionExportError("Notion client is required for non-dry-run export.")
    if not data_source_id:
        raise NotionExportError("Notion data source id is required for non-dry-run export.")

    if legacy_external_key and account_id == "paper_default":
        existing = client.query_by_external_key(
            data_source_id,
            external_key,
            external_key_property_name,
        )
        if len(existing) >= 2:
            raise NotionDuplicateExternalKeyError(
                f"Multiple Notion pages found for external key '{external_key}'."
            )
        if len(existing) == 1:
            page_id = existing[0]["id"]
            payload = client.update_page(page_id, properties)
            if refresh_children_on_update:
                client.replace_page_children(page_id, children or [])
            return ExportResult(
                account_id=account_id,
                target=target,
                external_key=external_key,
                legacy_external_key=legacy_external_key,
                legacy_fallback_used=False,
                action="updated",
                page_id=page_id,
                source_path=_relative_to_project(source_path),
                data_source_key=data_source_key,
                dry_run=False,
            )

        legacy_existing = client.query_by_external_key(
            data_source_id,
            legacy_external_key,
            external_key_property_name,
        )
        if len(legacy_existing) >= 2:
            raise NotionDuplicateExternalKeyError(
                f"Multiple Notion pages found for legacy external key '{legacy_external_key}'."
            )
        if len(legacy_existing) == 1:
            page_id = legacy_existing[0]["id"]
            client.update_page(page_id, properties)
            if refresh_children_on_update:
                client.replace_page_children(page_id, children or [])
            return ExportResult(
                account_id=account_id,
                target=target,
                external_key=external_key,
                legacy_external_key=legacy_external_key,
                legacy_fallback_used=True,
                action="updated",
                page_id=page_id,
                source_path=_relative_to_project(source_path),
                data_source_key=data_source_key,
                dry_run=False,
            )

    result = client.upsert_page_by_external_key(
        data_source_id=data_source_id,
        external_key=external_key,
        external_key_property=external_key_property_name,
        properties=properties,
        children=children,
        refresh_children_on_update=refresh_children_on_update,
    )
    return ExportResult(
        account_id=account_id,
        target=target,
        external_key=external_key,
        legacy_external_key=legacy_external_key,
        legacy_fallback_used=False,
        action=result.action,
        page_id=result.page_id,
        source_path=_relative_to_project(source_path),
        data_source_key=data_source_key,
        dry_run=False,
    )


def export_weekly_report_to_notion(
    *,
    client: NotionClient | None,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    account_id: str | None = None,
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> ExportResult:
    resolved_account_id = normalize_notion_account_id(account_id)
    root = Path(paper_root) if paper_root is not None else paper_reports_dir().parent
    reports_dir = root / "reports"
    json_path = reports_dir / "paper_weekly_status_summary.json"
    markdown_path = reports_dir / "paper_weekly_status_summary.md"
    summary = _read_json(json_path)
    if not markdown_path.exists():
        raise NotionExportError(f"Missing source file: {markdown_path}")
    mapping = get_mapping_section(mapping_root, "weekly_reports")
    synced_at = datetime.now(timezone.utc).isoformat()
    period = summary["period"]
    external_key = build_weekly_report_external_key(summary, resolved_account_id)
    legacy_external_key = (
        build_legacy_weekly_report_external_key(period["actual_start"], period["actual_end"])
        if resolved_account_id == "paper_default"
        else None
    )
    properties = build_weekly_report_properties(
        summary,
        mapping,
        account_id=resolved_account_id,
        markdown_path=markdown_path,
        json_path=json_path,
        synced_at=synced_at,
    )
    data_source_id = None if dry_run else get_notion_data_source_id(
        settings,
        "weekly_reports",
        env_override="NOTION_WEEKLY_REPORTS_DATA_SOURCE_ID",
    )
    return _upsert_or_dry_run(
        client=client,
        data_source_id=data_source_id,
        account_id=resolved_account_id,
        external_key=external_key,
        legacy_external_key=legacy_external_key,
        external_key_property_name=resolve_notion_property_name(mapping, "external_key"),
        properties=properties,
        children=_build_weekly_children(summary, markdown_path, json_path),
        target="weekly_reports",
        source_path=json_path,
        data_source_key="weekly_reports",
        dry_run=dry_run,
        refresh_children_on_update=False,
    )


def export_benchmark_report_to_notion(
    *,
    client: NotionClient | None,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    account_id: str | None = None,
    expected_date: str | None = None,
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> ExportResult:
    resolved_account_id = normalize_notion_account_id(account_id)
    if expected_date is None:
        raise NotionExportError(
            "Benchmark export requires expected_date: "
            f"expected_account_id={resolved_account_id} reason=missing_expected_date"
        )
    normalized_expected_date = _normalize_export_date(expected_date)
    root = _resolve_snapshot_export_root(
        account_id=resolved_account_id,
        paper_root=paper_root,
    )
    reports_dir = root / "reports"
    json_path = reports_dir / "paper_benchmark_comparison.json"
    markdown_path = reports_dir / "paper_benchmark_comparison.md"
    summary = _read_json(json_path)
    actual_account_id = str(summary.get("account_id") or "").strip()
    if actual_account_id != resolved_account_id:
        raise NotionExportError(
            "Benchmark account identity mismatch: "
            f"expected_account_id={resolved_account_id} actual_account_id={actual_account_id or '<blank>'} "
            f"path={json_path} reason=account_id_mismatch"
        )
    actual_date = str(summary.get("latest_snapshot_date") or "").strip()
    if actual_date != normalized_expected_date:
        raise NotionExportError(
            "Benchmark latest date mismatch: "
            f"expected_date={normalized_expected_date} actual_date={actual_date or '<blank>'} "
            f"expected_account_id={resolved_account_id} path={json_path} reason=date_mismatch"
        )
    if not markdown_path.exists():
        raise NotionExportError(f"Missing source file: {markdown_path}")
    mapping = get_mapping_section(mapping_root, "benchmark_reports")
    synced_at = datetime.now(timezone.utc).isoformat()
    external_key = build_benchmark_report_external_key(summary, resolved_account_id)
    legacy_external_key = (
        build_legacy_benchmark_report_external_key(summary["latest_snapshot_date"], summary["run_mode"])
        if resolved_account_id == "paper_default"
        else None
    )
    properties = build_benchmark_report_properties(
        summary,
        mapping,
        account_id=resolved_account_id,
        markdown_path=markdown_path,
        json_path=json_path,
        synced_at=synced_at,
    )
    data_source_id = None if dry_run else get_notion_data_source_id(
        settings,
        "benchmark_reports",
        env_override="NOTION_BENCHMARK_REPORTS_DATA_SOURCE_ID",
    )
    return _upsert_or_dry_run(
        client=client,
        data_source_id=data_source_id,
        account_id=resolved_account_id,
        external_key=external_key,
        legacy_external_key=legacy_external_key,
        external_key_property_name=resolve_notion_property_name(mapping, "external_key"),
        properties=properties,
        children=_build_benchmark_children(summary, markdown_path, json_path),
        target="benchmark_reports",
        source_path=json_path,
        data_source_key="benchmark_reports",
        dry_run=dry_run,
        refresh_children_on_update=False,
    )


def export_latest_account_snapshot_to_notion(
    *,
    client: NotionClient | None,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    account_id: str | None = None,
    expected_date: str | None = None,
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> ExportResult:
    resolved_account_id = normalize_notion_account_id(account_id)
    if expected_date is None:
        raise NotionExportError(
            "Account snapshot export requires expected_date: "
            f"expected_account_id={resolved_account_id} reason=missing_expected_date"
        )
    normalized_expected_date = _normalize_export_date(expected_date)
    root = _resolve_snapshot_export_root(
        account_id=resolved_account_id,
        paper_root=paper_root,
    )
    csv_path = root / paper_account_snapshot_path().name
    rows, fieldnames = _read_snapshot_csv_rows(csv_path)
    try:
        rows, _ = validate_snapshot_account_identity(
            rows,
            fieldnames=fieldnames,
            allowed_fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS,
            expected_account_id=resolved_account_id,
            source_path=csv_path,
            account_root=root,
        )
    except PaperSnapshotIdentityError as exc:
        raise NotionExportError(str(exc)) from exc
    if not rows:
        raise NotionExportError(f"No account snapshot rows found: {csv_path}")
    latest_row = max(rows, key=lambda row: row.get("snapshot_date", ""))
    actual_date = str(latest_row.get("snapshot_date") or "").strip()
    if actual_date != normalized_expected_date:
        raise NotionExportError(
            "Account snapshot latest date mismatch: "
            f"expected_date={normalized_expected_date} actual_date={actual_date or '<blank>'} "
            f"expected_account_id={resolved_account_id} path={csv_path} reason=date_mismatch"
        )
    mapping = get_mapping_section(mapping_root, "account_snapshots")
    synced_at = datetime.now(timezone.utc).isoformat()
    external_key = build_account_snapshot_external_key(latest_row, resolved_account_id)
    legacy_external_key = (
        build_legacy_account_snapshot_external_key(str(latest_row.get("snapshot_date") or ""))
        if resolved_account_id == "paper_default"
        else None
    )
    properties = build_account_snapshot_properties(
        latest_row,
        mapping,
        account_id=resolved_account_id,
        synced_at=synced_at,
    )
    data_source_id = None if dry_run else get_notion_data_source_id(
        settings,
        "account_snapshots",
        env_override="NOTION_ACCOUNT_SNAPSHOTS_DATA_SOURCE_ID",
    )
    return _upsert_or_dry_run(
        client=client,
        data_source_id=data_source_id,
        account_id=resolved_account_id,
        external_key=external_key,
        legacy_external_key=legacy_external_key,
        external_key_property_name=resolve_notion_property_name(mapping, "external_key"),
        properties=properties,
        children=_build_account_snapshot_children(latest_row),
        target="account_snapshots",
        source_path=csv_path,
        data_source_key="account_snapshots",
        dry_run=dry_run,
        refresh_children_on_update=False,
    )


def export_daily_plan_to_notion(
    *,
    client: NotionClient | None,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    account_id: str | None = None,
    paper_root: Path | None = None,
    plan_date: str | None = None,
    dry_run: bool = False,
) -> ExportResult:
    resolved_account_id = normalize_notion_account_id(account_id)
    root = _resolve_daily_plan_export_root(
        account_id=resolved_account_id,
        paper_root=paper_root,
    )
    if plan_date:
        markdown_path, config_snapshot_path = _paper_daily_plan_artifacts_for_date(root, plan_date)
    else:
        markdown_path, config_snapshot_path = _latest_paper_daily_plan_artifacts(root)
    summary = summarize_daily_plan_artifacts(
        markdown_path=markdown_path,
        config_snapshot_path=config_snapshot_path,
    )
    mapping = get_mapping_section(mapping_root, "daily_plans")
    synced_at = datetime.now(timezone.utc).isoformat()
    external_key = build_daily_plan_external_key(summary["plan_date"], resolved_account_id)
    legacy_external_key = (
        build_legacy_daily_plan_external_key(summary["plan_date"])
        if resolved_account_id == "paper_default"
        else None
    )
    properties = build_daily_plan_properties(
        summary,
        mapping,
        account_id=resolved_account_id,
        markdown_path=markdown_path,
        json_path=config_snapshot_path,
        synced_at=synced_at,
    )
    data_source_id = None if dry_run else get_notion_data_source_id(
        settings,
        "daily_plans",
        env_override="NOTION_DAILY_PLANS_DATA_SOURCE_ID",
    )
    return _upsert_or_dry_run(
        client=client,
        data_source_id=data_source_id,
        account_id=resolved_account_id,
        external_key=external_key,
        legacy_external_key=legacy_external_key,
        external_key_property_name=resolve_notion_property_name(mapping, "external_key"),
        properties=properties,
        children=_build_daily_plan_children(summary, markdown_path, config_snapshot_path),
        target="daily_plans",
        source_path=config_snapshot_path,
        data_source_key="daily_plans",
        dry_run=dry_run,
        refresh_children_on_update=True,
    )


def export_daily_review_summary_to_notion(
    *,
    client: NotionClient | None,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    review_date: str,
    account_id: str | None = None,
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> ExportResult:
    resolved_account_id = normalize_notion_account_id(account_id)
    root = Path(paper_root) if paper_root is not None else paper_reports_dir().parent
    summary = build_daily_review_summary(review_date=review_date, paper_root=root)
    mapping = get_mapping_section(mapping_root, "daily_review_summaries")
    synced_at = datetime.now(timezone.utc).isoformat()
    external_key = build_daily_review_summary_external_key_with_account(
        resolved_account_id,
        summary["review_date"],
    )
    legacy_external_key = (
        build_legacy_daily_review_summary_external_key(summary["review_date"])
        if resolved_account_id == "paper_default"
        else None
    )
    properties = build_daily_review_summary_properties(
        summary,
        mapping,
        account_id=resolved_account_id,
        synced_at=synced_at,
    )
    data_source_id = None if dry_run else get_notion_data_source_id(
        settings,
        "daily_review_summaries",
        env_override="NOTION_DAILY_REVIEW_SUMMARIES_DATA_SOURCE_ID",
    )
    source_path = root / "reports" / f"manual_execution_import_commit_{review_date.replace('-', '')}.json"
    return _upsert_or_dry_run(
        client=client,
        data_source_id=data_source_id,
        account_id=resolved_account_id,
        external_key=external_key,
        legacy_external_key=legacy_external_key,
        external_key_property_name=resolve_notion_property_name(mapping, "external_key"),
        properties=properties,
        children=_build_daily_review_summary_children(summary),
        target="daily_review_summaries",
        source_path=source_path,
        data_source_key="daily_review_summaries",
        dry_run=dry_run,
        refresh_children_on_update=False,
    )


def export_manual_execution_template_to_notion(
    *,
    client: NotionClient | None,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    date_str: str,
    account_id: str | None = None,
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_account_id = normalize_notion_account_id(account_id)
    normalized_date = _normalize_export_date(date_str)
    sidecar_path, payload = _load_daily_plan_sidecar_for_manual_execution_template(
        account_id=resolved_account_id,
        date_str=normalized_date,
        paper_root=paper_root,
    )
    sidecar_account_id = str(payload.get("account_id") or "").strip()
    trade_date, raw_candidates, failed = _manual_execution_template_candidates_from_sidecar(
        payload,
        account_id=sidecar_account_id,
    )
    mapping = get_mapping_section(mapping_root, "manual_executions")
    data_source_id = get_notion_data_source_id(
        settings,
        "manual_executions",
        env_override="NOTION_MANUAL_EXECUTIONS_DATA_SOURCE_ID",
    )
    external_key_property = resolve_notion_property_name(mapping, "external_key")
    import_status_property = resolve_notion_property_name(mapping, "import_status")
    broker_property = resolve_notion_property_name(mapping, "broker")
    import_status_schema = _get_notion_property_schema(client, data_source_id, import_status_property)
    broker_schema = _get_notion_property_schema(client, data_source_id, broker_property)
    initial_import_status = _resolve_manual_execution_template_import_status(import_status_schema)
    broker_property_type = str(broker_schema.get("type") or "select")

    candidates: list[ManualExecutionTemplateExportCandidate] = []
    for candidate in raw_candidates:
        existing: list[dict[str, Any]] = []
        if client is not None:
            existing = client.query_by_external_key(
                data_source_id,
                candidate.external_key,
                external_key_property,
            )
        if len(existing) >= 2:
            failed.append(
                {
                    "symbol": candidate.symbol,
                    "side": candidate.side,
                    "external_key": candidate.external_key,
                    "error": "Multiple Notion rows found for external key.",
                }
            )
            continue

        page_id = str(existing[0].get("id") or "").strip() if existing else None
        action = "update" if page_id else "create"
        candidate = ManualExecutionTemplateExportCandidate(
            external_key=candidate.external_key,
            action=action,
            page_id=page_id,
            account_id=candidate.account_id,
            execution_date=candidate.execution_date,
            plan_date=candidate.plan_date,
            symbol=candidate.symbol,
            side=candidate.side,
            quantity=candidate.quantity,
            plan_price=candidate.plan_price,
            note=candidate.note,
            import_status=initial_import_status,
        )
        candidates.append(candidate)

        if not dry_run:
            if client is None:
                raise NotionExportError("Notion client is required for actual manual execution template export.")
            properties = build_manual_execution_template_properties(
                candidate,
                mapping,
                broker_property_type=broker_property_type,
            )
            if page_id:
                client.update_page(page_id, properties)
            else:
                created = client.create_page(data_source_id, properties)
                candidates[-1] = ManualExecutionTemplateExportCandidate(
                    external_key=candidate.external_key,
                    action="create",
                    page_id=str(created.get("id") or "").strip(),
                    account_id=candidate.account_id,
                    execution_date=candidate.execution_date,
                    plan_date=candidate.plan_date,
                    symbol=candidate.symbol,
                    side=candidate.side,
                    quantity=candidate.quantity,
                    plan_price=candidate.plan_price,
                    note=candidate.note,
                    import_status=candidate.import_status,
                )

    create_count = sum(1 for candidate in candidates if candidate.action == "create")
    update_count = sum(1 for candidate in candidates if candidate.action == "update")
    failed_count = len(failed)
    return {
        "target": MANUAL_EXECUTION_TEMPLATE_TARGET,
        "account_id": sidecar_account_id,
        "execution_date": trade_date,
        "plan_date": trade_date,
        "linked_daily_plan_key": build_daily_plan_external_key(trade_date, sidecar_account_id),
        "candidate_count": len(candidates),
        "create_count": create_count,
        "update_count": update_count,
        "created_count": 0 if dry_run else create_count,
        "updated_count": 0 if dry_run else update_count,
        "skip_count": 0,
        "failed_count": failed_count,
        "source_plan_path": _relative_to_project(sidecar_path),
        "dry_run": dry_run,
        "would_write": not dry_run,
        "data_source_key": "manual_executions",
        "data_source_id": data_source_id,
        "initial_import_status": initial_import_status,
        "initial_status": "DRAFT",
        "candidates": [candidate.to_dict() for candidate in candidates],
        "failed": failed,
        "legacy_trade_date_note": "" if payload.get("trade_date") else "trade_date missing; used plan_date",
    }


def export_manual_review_template_to_notion(
    *,
    client: NotionClient | None,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    review_date: str,
    account_id: str | None = None,
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    resolved_account_id = normalize_notion_account_id(account_id)
    normalized_review_date = _normalize_export_date(review_date)
    root = _resolve_manual_review_template_root(
        account_id=resolved_account_id,
        paper_root=paper_root,
    )
    template_path = root / "reviews" / "paper_manual_review_log_template.csv"
    if not template_path.exists():
        raise NotionExportError(f"Manual review template not found: {template_path}")

    rows = load_manual_review_template_rows(
        template_path=template_path,
        review_date=normalized_review_date,
    )
    mapping = get_mapping_section(mapping_root, "manual_reviews")
    data_source_id = get_notion_data_source_id(
        settings,
        "manual_reviews",
        env_override="NOTION_MANUAL_REVIEWS_DATA_SOURCE_ID",
    )
    external_key_property = resolve_notion_property_name(mapping, "external_key")

    live_schema: dict[str, Any] | None = None
    if not dry_run:
        if client is None:
            raise NotionExportError("Notion client is required for actual manual review template export.")
        live_schema = client.get_data_source_schema(data_source_id)
        schema_assessment = assess_manual_review_schema(live_schema, mapping)
        if schema_assessment["runner_result"] != "PASS":
            raise NotionExportError(
                "Manual Reviews schema is not compatible; run the read-only schema assess and "
                "explicit additive migration before export."
            )

    candidates: list[ManualReviewTemplateExportCandidate] = []
    failed: list[dict[str, str]] = []
    planned: list[tuple[dict[str, str], str, str | None]] = []
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        question_id = str(row.get("question_id") or "").strip()
        if not symbol or not question_id:
            failed.append(
                {
                    "symbol": symbol,
                    "question_id": question_id,
                    "error": "symbol and question_id are required.",
                }
            )
            continue
        external_key = build_manual_review_canonical_key(
            resolved_account_id,
            normalized_review_date,
            symbol,
            question_id,
        )
        existing: list[dict[str, Any]] = []
        if client is not None:
            existing = client.query_by_external_key(
                data_source_id,
                external_key,
                external_key_property,
            )
        if len(existing) >= 2:
            failed.append(
                {
                    "symbol": symbol,
                    "question_id": question_id,
                    "external_key": external_key,
                    "error": "Multiple Notion rows found for external key.",
                }
            )
            continue

        page_id = str(existing[0].get("id") or "").strip() if existing else None
        action = "update" if page_id else "create"
        candidate = _manual_review_template_candidate_from_row(
            row,
            account_id=resolved_account_id,
            review_date=normalized_review_date,
            action=action,
            page_id=page_id,
        )
        candidates.append(candidate)
        planned.append((row, external_key, page_id))

    if failed and not dry_run:
        return {
            "target": MANUAL_REVIEW_TEMPLATE_TARGET,
            "account_id": resolved_account_id,
            "review_date": normalized_review_date,
            "candidate_count": len(candidates),
            "create_count": sum(1 for candidate in candidates if candidate.action == "create"),
            "update_count": sum(1 for candidate in candidates if candidate.action == "update"),
            "created_count": 0,
            "updated_count": 0,
            "skip_count": 0,
            "failed_count": len(failed),
            "source_template_path": _relative_to_project(template_path),
            "dry_run": False,
            "would_write": False,
            "data_source_key": "manual_reviews",
            "data_source_id": data_source_id,
            "initial_import_status": MANUAL_REVIEW_TEMPLATE_IMPORT_STATUS,
            "initial_review_status": "pending",
            "candidates": [candidate.to_dict() for candidate in candidates],
            "failed": failed,
        }

    if not dry_run:
        assert client is not None
        assert live_schema is not None
        payloads: list[dict[str, Any]] = []
        for row, external_key, _ in planned:
            properties = build_manual_review_template_properties(
                row,
                mapping,
                account_id=resolved_account_id,
                review_date=normalized_review_date,
                external_key=external_key,
            )
            payload_errors = validate_manual_review_create_payload(properties, live_schema)
            if payload_errors:
                raise NotionExportError(
                    "Manual Review create payload is incompatible with live schema: "
                    + ", ".join(payload_errors)
                )
            payloads.append(properties)

        for index, ((row, external_key, page_id), properties) in enumerate(zip(planned, payloads)):
            if page_id:
                client.update_page(
                    page_id,
                    build_manual_review_template_update_properties(
                        row,
                        mapping,
                        account_id=resolved_account_id,
                        review_date=normalized_review_date,
                        external_key=external_key,
                    ),
                )
            else:
                created = client.create_page(data_source_id, properties)
                candidate = _manual_review_template_candidate_from_row(
                    row,
                    account_id=resolved_account_id,
                    review_date=normalized_review_date,
                    action="create",
                    page_id=str(created.get("id") or "").strip(),
                )
                candidates[index] = candidate

    create_count = sum(1 for candidate in candidates if candidate.action == "create")
    update_count = sum(1 for candidate in candidates if candidate.action == "update")
    failed_count = len(failed)
    return {
        "target": MANUAL_REVIEW_TEMPLATE_TARGET,
        "account_id": resolved_account_id,
        "review_date": normalized_review_date,
        "candidate_count": len(candidates),
        "create_count": create_count,
        "update_count": update_count,
        "created_count": 0 if dry_run else create_count,
        "updated_count": 0 if dry_run else update_count,
        "skip_count": 0,
        "failed_count": failed_count,
        "source_template_path": _relative_to_project(template_path),
        "dry_run": dry_run,
        "would_write": not dry_run,
        "data_source_key": "manual_reviews",
        "data_source_id": data_source_id,
        "initial_import_status": MANUAL_REVIEW_TEMPLATE_IMPORT_STATUS,
        "initial_review_status": "pending",
        "candidates": [candidate.to_dict() for candidate in candidates],
        "failed": failed,
    }


def export_selected_paper_reports_to_notion(
    *,
    client: NotionClient | None,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    account_id: str | None = None,
    export_weekly: bool = False,
    export_benchmark: bool = False,
    export_account_snapshot: bool = False,
    export_daily_plan: bool = False,
    export_daily_review_summary: bool = False,
    review_date: str | None = None,
    daily_plan_date: str | None = None,
    expected_date: str | None = None,
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> list[ExportResult]:
    if not any([export_weekly, export_benchmark, export_account_snapshot, export_daily_plan, export_daily_review_summary]):
        raise NotionExportError("No export targets selected.")

    results: list[ExportResult] = []
    if export_weekly:
        results.append(
            export_weekly_report_to_notion(
                client=client,
                settings=settings,
                mapping_root=mapping_root,
                account_id=account_id,
                paper_root=paper_root,
                plan_date=daily_plan_date,
                dry_run=dry_run,
            )
        )
    if export_benchmark:
        results.append(
            export_benchmark_report_to_notion(
                client=client,
                settings=settings,
                mapping_root=mapping_root,
                account_id=account_id,
                expected_date=expected_date,
                paper_root=paper_root,
                dry_run=dry_run,
            )
        )
    if export_account_snapshot:
        results.append(
            export_latest_account_snapshot_to_notion(
                client=client,
                settings=settings,
                mapping_root=mapping_root,
                account_id=account_id,
                expected_date=expected_date,
                paper_root=paper_root,
                dry_run=dry_run,
            )
        )
    if export_daily_plan:
        results.append(
            export_daily_plan_to_notion(
                client=client,
                settings=settings,
                mapping_root=mapping_root,
                account_id=account_id,
                paper_root=paper_root,
                dry_run=dry_run,
            )
        )
    if export_daily_review_summary:
        if not review_date:
            raise NotionExportError("review_date is required for daily_review_summaries export.")
        results.append(
            export_daily_review_summary_to_notion(
                client=client,
                settings=settings,
                mapping_root=mapping_root,
                review_date=review_date,
                account_id=account_id,
                paper_root=paper_root,
                dry_run=dry_run,
            )
        )
    return results
