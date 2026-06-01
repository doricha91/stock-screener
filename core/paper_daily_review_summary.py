from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_guard import assert_path_under_account_root
from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


REQUIRED_SIDE_BY_SIDE_COLUMNS = [
    "symbol",
    "symbol_status",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
]

REQUIRED_REVIEW_BUCKET_COLUMNS = [
    "symbol",
    "review_bucket",
    "review_priority",
    "sample_size_flag",
]

def build_report_index_rows(report_base_root: Path) -> list[dict[str, str]]:
    report_base_root = report_base_root.resolve()
    return [
    {
        "report_path": str(report_base_root / "paper_daily_review_summary.md"),
        "category": "Final / operator-facing reports",
        "purpose": "Daily operator-facing review entrypoint",
        "operator_should_read_daily": "true",
        "notes": "Non-actionable final summary",
    },
    {
        "report_path": str(report_base_root / "paper_report_index.md"),
        "category": "Final / operator-facing reports",
        "purpose": "Index of paper-test reports",
        "operator_should_read_daily": "false",
        "notes": "Navigation aid",
    },
    {
        "report_path": str(report_base_root / "paper_performance_summary.md"),
        "category": "Core account reports",
        "purpose": "Account-level paper performance summary",
        "operator_should_read_daily": "true",
        "notes": "Primary account summary source",
    },
    {
        "report_path": str(report_base_root / "paper_equity_curve.csv"),
        "category": "Core account reports",
        "purpose": "Equity curve time series",
        "operator_should_read_daily": "false",
        "notes": "Intermediate quantitative source",
    },
    {
        "report_path": str(report_base_root / "paper_drawdown.csv"),
        "category": "Core account reports",
        "purpose": "Drawdown time series",
        "operator_should_read_daily": "false",
        "notes": "Intermediate quantitative source",
    },
    {
        "report_path": str(report_base_root / "paper_realized_trade_journal.csv"),
        "category": "Trade-level reports",
        "purpose": "SELL-event realized trade journal",
        "operator_should_read_daily": "false",
        "notes": "Average-cost realized ledger",
    },
    {
        "report_path": str(report_base_root / "paper_realized_trade_journal_summary.md"),
        "category": "Trade-level reports",
        "purpose": "Realized trade journal summary",
        "operator_should_read_daily": "false",
        "notes": "Quick trade-level realized summary",
    },
    {
        "report_path": str(report_base_root / "paper_symbol_realized_performance.csv"),
        "category": "Symbol-level reports",
        "purpose": "Per-symbol realized performance table",
        "operator_should_read_daily": "false",
        "notes": "Derived from realized trade journal",
    },
    {
        "report_path": str(report_base_root / "paper_symbol_unrealized_performance.csv"),
        "category": "Symbol-level reports",
        "purpose": "Per-symbol open-position unrealized table",
        "operator_should_read_daily": "false",
        "notes": "Latest snapshot only",
    },
    {
        "report_path": str(report_base_root / "paper_symbol_side_by_side_performance.csv"),
        "category": "Symbol-level reports",
        "purpose": "Side-by-side realized/unrealized symbol table",
        "operator_should_read_daily": "true",
        "notes": "Reference total_pnl included",
    },
    {
        "report_path": str(report_base_root / "paper_realized_ranking_report.md"),
        "category": "Symbol-level reports",
        "purpose": "Realized ranking markdown report",
        "operator_should_read_daily": "false",
        "notes": "Realized-only ranking context",
    },
    {
        "report_path": str(report_base_root / "paper_symbol_review_buckets.csv"),
        "category": "Review / worksheet reports",
        "purpose": "Non-actionable review bucket classification",
        "operator_should_read_daily": "true",
        "notes": "Review prioritization source",
    },
    {
        "report_path": str(report_base_root / "paper_symbol_review_buckets_summary.md"),
        "category": "Review / worksheet reports",
        "purpose": "Review bucket summary",
        "operator_should_read_daily": "false",
        "notes": "Bucket counts and warnings",
    },
    {
        "report_path": str(report_base_root / "paper_symbol_review_worksheet.md"),
        "category": "Review / worksheet reports",
        "purpose": "Manual review worksheet",
        "operator_should_read_daily": "true",
        "notes": "Questions only, non-actionable",
    },
    {
        "report_path": str(report_base_root / "paper_symbol_review_worksheet.csv"),
        "category": "Review / worksheet reports",
        "purpose": "Question-row export of worksheet",
        "operator_should_read_daily": "false",
        "notes": "Machine-readable worksheet rows",
    },
    {
        "report_path": str(report_base_root / "paper_performance_input_audit.md"),
        "category": "Debug / intermediate reports",
        "purpose": "Input integrity audit",
        "operator_should_read_daily": "false",
        "notes": "Debug / validation",
    },
    {
        "report_path": str(report_base_root / "paper_report_regeneration_safety.md"),
        "category": "Debug / intermediate reports",
        "purpose": "Report regeneration safety check",
        "operator_should_read_daily": "false",
        "notes": "Debug / validation",
    },
]



def _parse_float(value: Any, field_name: str) -> float:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is blank")
    normalized = text.replace(",", "").replace("$", "").replace("%", "")
    lowered = normalized.lower()
    if lowered in {"nan", "inf", "-inf", "infinity", "-infinity"}:
        raise ValueError(f"invalid numeric in {field_name}: {value}")
    try:
        return float(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid numeric in {field_name}: {value}") from exc


def load_csv_rows(
    path: Path,
    required_columns: list[str],
    label: str,
    allowed_root: Path | None = None,
) -> list[dict[str, str]]:
    if allowed_root is None:
        assert_paper_path(path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(path, allowed_root)
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return []
    missing = [column for column in required_columns if column not in rows[0]]
    if missing:
        raise ValueError(f"Missing {label} columns: " + ", ".join(missing))
    return rows


def parse_paper_performance_summary_markdown(
    path: Path,
    allowed_root: Path | None = None,
) -> tuple[dict[str, str], list[str]]:
    if allowed_root is None:
        assert_paper_path(path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(path, allowed_root)
    if not path.exists():
        raise FileNotFoundError(f"paper_performance_summary.md not found: {path}")
    lines = path.read_text(encoding="utf-8").splitlines()
    warnings: list[str] = []
    values: dict[str, str] = {
        "latest_snapshot_date": "",
        "primary_equity": "",
        "cash": "",
        "cash_ratio": "",
        "position_ratio": "",
        "realized_pnl": "",
        "unrealized_pnl": "",
        "total_pnl": "",
    }
    mapping = {
        "- Latest Snapshot Date:": "latest_snapshot_date",
        "- Primary Equity:": "primary_equity",
        "- Cash:": "cash",
        "- Cash Ratio:": "cash_ratio",
        "- Realized PnL:": "realized_pnl",
        "- Unrealized PnL:": "unrealized_pnl",
        "- Total PnL:": "total_pnl",
        "- Position Ratio Market:": "position_ratio",
    }
    for line in lines:
        stripped = line.strip()
        for prefix, key in mapping.items():
            if stripped.startswith(prefix):
                values[key] = stripped[len(prefix):].strip()
    if not values["position_ratio"]:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- Position Ratio Market:"):
                values["position_ratio"] = stripped.split(":", 1)[1].strip()
    if not values["cash_ratio"]:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("- Cash Ratio Market:"):
                values["cash_ratio"] = stripped.split(":", 1)[1].strip()
    missing = [key for key, value in values.items() if value == ""]
    if missing:
        warnings.append("paper_performance_summary.md parse incomplete: " + ", ".join(missing))
    return values, warnings


def build_paper_daily_review_summary_data(
    performance_summary_path: Path,
    side_by_side_rows: list[dict[str, str]],
    review_bucket_rows: list[dict[str, str]],
    worksheet_path: Path,
    report_base_root: Path | None = None,
    allowed_root: Path | None = None,
) -> tuple[dict[str, Any], list[str], list[dict[str, str]]]:
    warnings: list[str] = []
    account_summary, account_warnings = parse_paper_performance_summary_markdown(
        performance_summary_path,
        allowed_root=allowed_root,
    )
    warnings.extend(account_warnings)

    side_by_side_summary = {
        "symbol_count": len(side_by_side_rows),
        "realized_only_count": sum(1 for row in side_by_side_rows if str(row.get("symbol_status", "")).strip() == "realized_only"),
        "unrealized_only_count": sum(1 for row in side_by_side_rows if str(row.get("symbol_status", "")).strip() == "unrealized_only"),
        "realized_and_unrealized_count": sum(1 for row in side_by_side_rows if str(row.get("symbol_status", "")).strip() == "realized_and_unrealized"),
        "total_realized_pnl": sum(_parse_float(row.get("realized_pnl", ""), "realized_pnl") for row in side_by_side_rows) if side_by_side_rows else 0.0,
        "total_unrealized_pnl": sum(_parse_float(row.get("unrealized_pnl", ""), "unrealized_pnl") for row in side_by_side_rows) if side_by_side_rows else 0.0,
        "total_pnl_reference": sum(_parse_float(row.get("total_pnl", ""), "total_pnl") for row in side_by_side_rows) if side_by_side_rows else 0.0,
    }
    sorted_total = sorted(
        side_by_side_rows,
        key=lambda row: (_parse_float(row.get("total_pnl", ""), "total_pnl"), str(row.get("symbol", ""))),
        reverse=True,
    ) if side_by_side_rows else []
    side_by_side_summary["top_total_pnl_symbols"] = sorted_total[:3]
    side_by_side_summary["worst_total_pnl_symbols"] = list(reversed(sorted_total[-3:])) if sorted_total else []

    bucket_counts = Counter(str(row.get("review_bucket", "")).strip() for row in review_bucket_rows)
    priority_counts = Counter(str(row.get("review_priority", "")).strip() for row in review_bucket_rows)
    sample_counts = Counter(str(row.get("sample_size_flag", "")).strip() for row in review_bucket_rows)
    high_priority_symbols = [str(row.get("symbol", "")).strip() for row in review_bucket_rows if str(row.get("review_priority", "")).strip() == "high"]
    review_bucket_summary = {
        "bucket_counts": dict(bucket_counts),
        "priority_counts": dict(priority_counts),
        "sample_size_counts": dict(sample_counts),
        "high_priority_symbols": high_priority_symbols,
    }

    report_base_root = report_base_root or performance_summary_path.parent
    report_index_rows = build_report_index_rows(report_base_root)
    summary_data = {
        "account_summary": account_summary,
        "side_by_side_summary": side_by_side_summary,
        "review_bucket_summary": review_bucket_summary,
        "worksheet_path": str(worksheet_path),
        "report_base_path": str(report_base_root),
        "performance_summary_path": str(performance_summary_path),
        "report_index_rows": report_index_rows,
        "is_actionable": "false",
    }
    return summary_data, warnings, report_index_rows


def summarize_paper_daily_review_summary(
    summary_data: dict[str, Any],
    warnings: list[str],
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "generated_at": (generated_at or datetime.now()).isoformat(timespec="seconds"),
        "warnings": warnings,
        "limitations": [
            "This is a paper-test review summary, not real investment performance.",
            "This report is non-actionable.",
            "It does not recommend buy/sell/hold actions.",
            "realized PnL is average-cost SELL-event based.",
            "unrealized PnL is current open-position snapshot based.",
            "total_pnl is a reference metric only.",
            "FIFO/LIFO/lot ledger accounting is not implemented.",
            "open_date and holding_days are excluded.",
            "Metrics are preliminary when trade count or snapshot history is small.",
        ],
        **summary_data,
    }


def _format_symbol_rows(rows: list[dict[str, str]], metric_key: str) -> str:
    if not rows:
        return "-"
    return ", ".join(f"{row.get('symbol','')} ({_parse_float(row.get(metric_key, ''), metric_key):.2f})" for row in rows)


def render_paper_daily_review_summary(summary: dict[str, Any]) -> str:
    account = summary["account_summary"]
    side = summary["side_by_side_summary"]
    buckets = summary["review_bucket_summary"]
    lines = [
        "# Paper Daily Review Summary",
        "",
        "## Header",
        f"- Generated at: {summary['generated_at']}",
        f"- Report base path: {summary['report_base_path']}",
        f"- is_actionable: {summary['is_actionable']}",
        "",
        "## Account Summary",
        f"- Latest snapshot date: {account.get('latest_snapshot_date') or 'See source report'}",
        f"- Primary equity: {account.get('primary_equity') or 'See source report'}",
        f"- Cash: {account.get('cash') or 'See source report'}",
        f"- Cash ratio: {account.get('cash_ratio') or 'See source report'}",
        f"- Position ratio: {account.get('position_ratio') or 'See source report'}",
        f"- Realized PnL: {account.get('realized_pnl') or 'See source report'}",
        f"- Unrealized PnL: {account.get('unrealized_pnl') or 'See source report'}",
        f"- Total PnL: {account.get('total_pnl') or 'See source report'}",
        f"- Source report: {summary['performance_summary_path']}",
        "",
        "## Symbol Side-by-Side Summary",
        f"- Symbol count: {side['symbol_count']}",
        f"- realized_only count: {side['realized_only_count']}",
        f"- unrealized_only count: {side['unrealized_only_count']}",
        f"- realized_and_unrealized count: {side['realized_and_unrealized_count']}",
        f"- Total realized PnL: {side['total_realized_pnl']:.2f}",
        f"- Total unrealized PnL: {side['total_unrealized_pnl']:.2f}",
        f"- Total PnL reference: {side['total_pnl_reference']:.2f}",
        f"- Top total PnL symbols: {_format_symbol_rows(side['top_total_pnl_symbols'], 'total_pnl')}",
        f"- Worst total PnL symbols: {_format_symbol_rows(side['worst_total_pnl_symbols'], 'total_pnl')}",
        "- Note: total_pnl is a reference metric, not a lot-matched accounting result.",
        "",
        "## Review Bucket Summary",
        f"- review_loss count: {buckets['bucket_counts'].get('review_loss', 0)}",
        f"- track_realized_gain count: {buckets['bucket_counts'].get('track_realized_gain', 0)}",
        f"- monitor_open_gain count: {buckets['bucket_counts'].get('monitor_open_gain', 0)}",
        f"- monitor_open_loss count: {buckets['bucket_counts'].get('monitor_open_loss', 0)}",
        f"- neutral count: {buckets['bucket_counts'].get('neutral', 0)}",
        f"- high priority count: {buckets['priority_counts'].get('high', 0)}",
        f"- medium priority count: {buckets['priority_counts'].get('medium', 0)}",
        f"- low priority count: {buckets['priority_counts'].get('low', 0)}",
        f"- high priority symbols: {'|'.join(buckets['high_priority_symbols']) if buckets['high_priority_symbols'] else '-'}",
        f"- sample_size_flag summary: no_realized_trades={buckets['sample_size_counts'].get('no_realized_trades', 0)}, low_sample={buckets['sample_size_counts'].get('low_sample', 0)}, enough_sample={buckets['sample_size_counts'].get('enough_sample', 0)}",
        "",
        "## Review Worksheet Pointers",
        f"- Worksheet path: {summary['worksheet_path']}",
        f"- High priority symbols to review first: {'|'.join(buckets['high_priority_symbols']) if buckets['high_priority_symbols'] else '-'}",
        "- Review worksheet contains manual review questions only.",
        "- No buy/sell/hold recommendation is included.",
        "",
        "## Report Index",
        "| Report | Purpose | Read Daily | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for row in summary["report_index_rows"]:
        lines.append(
            f"| {row['report_path']} | {row['purpose']} | {row['operator_should_read_daily']} | {row['notes']} |"
        )
    lines.extend(["", "## Warnings"])
    if summary["warnings"]:
        lines.extend(f"- {warning}" for warning in summary["warnings"])
    else:
        lines.append("- None")
    lines.extend(["", "## Limitations"])
    lines.extend(f"- {item}" for item in summary["limitations"])
    return "\n".join(lines) + "\n"


def render_paper_report_index(report_rows: list[dict[str, str]], generated_at: datetime | None = None) -> str:
    ts = (generated_at or datetime.now()).isoformat(timespec="seconds")
    categories = [
        "Final / operator-facing reports",
        "Core account reports",
        "Trade-level reports",
        "Symbol-level reports",
        "Review / worksheet reports",
        "Debug / intermediate reports",
    ]
    lines = ["# Paper Report Index", "", f"- Generated at: {ts}", ""]
    for idx, category in enumerate(categories, start=1):
        lines.extend([f"## {idx}. {category}", "", "| report_path | category | purpose | operator_should_read_daily | notes |", "| --- | --- | --- | --- | --- |"])
        rows = [row for row in report_rows if row["category"] == category]
        if not rows:
            lines.append("| - | - | - | - | - |")
        else:
            for row in rows:
                lines.append(
                    f"| {row['report_path']} | {row['category']} | {row['purpose']} | {row['operator_should_read_daily']} | {row['notes']} |"
                )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_markdown(path: Path, markdown: str, allowed_root: Path | None = None) -> None:
    if allowed_root is None:
        assert_paper_path(path, PAPER_TEST_DIR)
    else:
        assert_path_under_account_root(path, allowed_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
