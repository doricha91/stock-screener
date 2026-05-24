from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.notion_client import (
    NotionClient,
    notion_date,
    notion_number,
    notion_rich_text,
    notion_select,
    notion_title,
)
from core.notion_mapping import get_mapping_section, resolve_notion_property_name
from core.notion_settings import NotionSettings, get_notion_data_source_id
from core.paths import (
    paper_account_snapshot_path,
    paper_daily_action_plan_path,
    paper_reports_dir,
)


class NotionExportError(RuntimeError):
    pass


@dataclass
class ExportResult:
    target: str
    external_key: str
    action: str
    page_id: str | None
    source_path: str
    data_source_key: str
    dry_run: bool


def _relative_to_project(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


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


def build_weekly_report_external_key(summary: dict[str, Any]) -> str:
    period = summary.get("period") or {}
    return f"weekly_report:{period.get('actual_start')}:{period.get('actual_end')}"


def build_benchmark_report_external_key(summary: dict[str, Any]) -> str:
    return f"benchmark:{summary.get('latest_snapshot_date')}:{summary.get('run_mode')}"


def build_account_snapshot_external_key(row: dict[str, str]) -> str:
    return f"account_snapshot:{row.get('snapshot_date')}"


def build_daily_plan_external_key(plan_date: str) -> str:
    return f"daily_plan:{plan_date}"


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
    markdown_path: Path,
    json_path: Path,
    synced_at: str,
) -> dict[str, Any]:
    period = summary["period"]
    account_summary = summary.get("account_summary") or {}
    trade_summary = summary.get("trade_summary") or {}
    gaps = summary.get("operation_gaps") or []
    high_gap_count = len([item for item in gaps if item.get("severity") == "HIGH"])
    properties = {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"Weekly Report {period['actual_start']} to {period['actual_end']}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(
            build_weekly_report_external_key(summary)
        ),
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
    markdown_path: Path,
    json_path: Path,
    synced_at: str,
) -> dict[str, Any]:
    benchmarks = summary.get("summary", {}).get("benchmarks", {})
    paper_summary = summary.get("summary", {}).get("paper", {})
    properties = {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"Benchmark Report {summary['latest_snapshot_date']} {summary['run_mode']}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(
            build_benchmark_report_external_key(summary)
        ),
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
    synced_at: str,
) -> dict[str, Any]:
    total_equity_market_value = _safe_float(row.get("total_equity_market_value")) or 0.0
    total_equity_cost_basis = _safe_float(row.get("total_equity_cost_basis")) or 0.0
    properties = {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"Account Snapshot {row.get('snapshot_date')}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(
            build_account_snapshot_external_key(row)
        ),
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
    markdown_path: Path,
    json_path: Path,
    synced_at: str,
) -> dict[str, Any]:
    properties = {
        resolve_notion_property_name(mapping, "name"): notion_title(
            f"Daily Plan {summary['plan_date']}"
        ),
        resolve_notion_property_name(mapping, "external_key"): notion_rich_text(
            build_daily_plan_external_key(summary["plan_date"])
        ),
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
            "config_snapshots/paper_config_snapshot_YYYYMMDD.json under outputs/paper_test."
        )

    _, markdown_path, config_snapshot_path = max(candidates, key=lambda item: item[0])
    return markdown_path, config_snapshot_path


def _upsert_or_dry_run(
    *,
    client: NotionClient | None,
    data_source_id: str | None,
    external_key: str,
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
            target=target,
            external_key=external_key,
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
    result = client.upsert_page_by_external_key(
        data_source_id=data_source_id,
        external_key=external_key,
        external_key_property=external_key_property_name,
        properties=properties,
        children=children,
        refresh_children_on_update=refresh_children_on_update,
    )
    return ExportResult(
        target=target,
        external_key=external_key,
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
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> ExportResult:
    root = Path(paper_root) if paper_root is not None else paper_reports_dir().parent
    reports_dir = root / "reports"
    json_path = reports_dir / "paper_weekly_status_summary.json"
    markdown_path = reports_dir / "paper_weekly_status_summary.md"
    summary = _read_json(json_path)
    if not markdown_path.exists():
        raise NotionExportError(f"Missing source file: {markdown_path}")
    mapping = get_mapping_section(mapping_root, "weekly_reports")
    synced_at = datetime.now(timezone.utc).isoformat()
    external_key = build_weekly_report_external_key(summary)
    properties = build_weekly_report_properties(
        summary,
        mapping,
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
        external_key=external_key,
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
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> ExportResult:
    root = Path(paper_root) if paper_root is not None else paper_reports_dir().parent
    reports_dir = root / "reports"
    json_path = reports_dir / "paper_benchmark_comparison.json"
    markdown_path = reports_dir / "paper_benchmark_comparison.md"
    summary = _read_json(json_path)
    if not markdown_path.exists():
        raise NotionExportError(f"Missing source file: {markdown_path}")
    mapping = get_mapping_section(mapping_root, "benchmark_reports")
    synced_at = datetime.now(timezone.utc).isoformat()
    external_key = build_benchmark_report_external_key(summary)
    properties = build_benchmark_report_properties(
        summary,
        mapping,
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
        external_key=external_key,
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
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> ExportResult:
    root = Path(paper_root) if paper_root is not None else paper_account_snapshot_path().parent
    csv_path = root / paper_account_snapshot_path().name
    rows = _read_csv_rows(csv_path)
    if not rows:
        raise NotionExportError(f"No account snapshot rows found: {csv_path}")
    latest_row = max(rows, key=lambda row: row.get("snapshot_date", ""))
    mapping = get_mapping_section(mapping_root, "account_snapshots")
    synced_at = datetime.now(timezone.utc).isoformat()
    external_key = build_account_snapshot_external_key(latest_row)
    properties = build_account_snapshot_properties(latest_row, mapping, synced_at=synced_at)
    data_source_id = None if dry_run else get_notion_data_source_id(
        settings,
        "account_snapshots",
        env_override="NOTION_ACCOUNT_SNAPSHOTS_DATA_SOURCE_ID",
    )
    return _upsert_or_dry_run(
        client=client,
        data_source_id=data_source_id,
        external_key=external_key,
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
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> ExportResult:
    root = Path(paper_root) if paper_root is not None else paper_daily_action_plan_path("1970-01-01").parent
    markdown_path, config_snapshot_path = _latest_paper_daily_plan_artifacts(root)
    summary = summarize_daily_plan_artifacts(
        markdown_path=markdown_path,
        config_snapshot_path=config_snapshot_path,
    )
    mapping = get_mapping_section(mapping_root, "daily_plans")
    synced_at = datetime.now(timezone.utc).isoformat()
    external_key = build_daily_plan_external_key(summary["plan_date"])
    properties = build_daily_plan_properties(
        summary,
        mapping,
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
        external_key=external_key,
        external_key_property_name=resolve_notion_property_name(mapping, "external_key"),
        properties=properties,
        children=_build_daily_plan_children(summary, markdown_path, config_snapshot_path),
        target="daily_plans",
        source_path=config_snapshot_path,
        data_source_key="daily_plans",
        dry_run=dry_run,
        refresh_children_on_update=True,
    )


def export_selected_paper_reports_to_notion(
    *,
    client: NotionClient | None,
    settings: NotionSettings,
    mapping_root: dict[str, dict[str, str]],
    export_weekly: bool = False,
    export_benchmark: bool = False,
    export_account_snapshot: bool = False,
    export_daily_plan: bool = False,
    paper_root: Path | None = None,
    dry_run: bool = False,
) -> list[ExportResult]:
    if not any([export_weekly, export_benchmark, export_account_snapshot, export_daily_plan]):
        raise NotionExportError("No export targets selected.")

    results: list[ExportResult] = []
    if export_weekly:
        results.append(
            export_weekly_report_to_notion(
                client=client,
                settings=settings,
                mapping_root=mapping_root,
                paper_root=paper_root,
                dry_run=dry_run,
            )
        )
    if export_benchmark:
        results.append(
            export_benchmark_report_to_notion(
                client=client,
                settings=settings,
                mapping_root=mapping_root,
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
                paper_root=paper_root,
                dry_run=dry_run,
            )
        )
    return results
