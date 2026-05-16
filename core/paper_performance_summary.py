from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from core.paper_safety import assert_paper_path
from core.paths import PAPER_TEST_DIR


def _read_csv_rows(path: Path, label: str) -> list[dict[str, str]]:
    assert_paper_path(path, PAPER_TEST_DIR)
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{label} is empty")
    return rows


def load_paper_account_snapshots(snapshot_path: Path) -> list[dict[str, str]]:
    return sorted(
        _read_csv_rows(snapshot_path, "paper_account_snapshot.csv"),
        key=lambda row: str(row.get("snapshot_date", "")).strip(),
    )


def load_paper_equity_curve(path: Path) -> list[dict[str, str]]:
    return sorted(
        _read_csv_rows(path, "paper_equity_curve.csv"),
        key=lambda row: str(row.get("snapshot_date", "")).strip(),
    )


def load_paper_drawdown(path: Path) -> list[dict[str, str]]:
    return sorted(
        _read_csv_rows(path, "paper_drawdown.csv"),
        key=lambda row: str(row.get("snapshot_date", "")).strip(),
    )


def load_latest_position_snapshot_rows(path: Path) -> tuple[str, list[dict[str, str]]]:
    rows = sorted(
        _read_csv_rows(path, "paper_position_snapshot.csv"),
        key=lambda row: str(row.get("snapshot_date", "")).strip(),
    )
    latest_date = str(rows[-1].get("snapshot_date", "")).strip()
    latest_rows = [row for row in rows if str(row.get("snapshot_date", "")).strip() == latest_date]
    return latest_date, latest_rows


def _value_or_na(value: Any, formatter=None) -> str:
    if value is None:
        return "N/A"
    text = str(value).strip()
    if text == "":
        return "N/A"
    if formatter is not None:
        return formatter(text)
    return text


def _format_money(value: Any) -> str:
    return f"${float(value):,.2f}"


def _format_pct(value: Any) -> str:
    return f"{float(value):.2f}%"


def _format_ratio_as_pct(value: Any) -> str:
    return f"{float(value) * 100:.2f}%"


def _format_shares(value: Any) -> str:
    numeric = float(value)
    if numeric.is_integer():
        return f"{int(numeric):,}"
    return f"{numeric:,.2f}"


def build_paper_performance_summary(
    equity_rows: list[dict[str, str]],
    drawdown_rows: list[dict[str, str]],
    account_rows: list[dict[str, str]],
    latest_position_snapshot_date: str,
    latest_position_rows: list[dict[str, str]],
) -> dict[str, Any]:
    if not equity_rows:
        raise ValueError("paper equity curve rows are empty")
    if not drawdown_rows:
        raise ValueError("paper drawdown rows are empty")
    if not account_rows:
        raise ValueError("paper account snapshot rows are empty")

    latest_equity = equity_rows[-1]
    latest_drawdown = drawdown_rows[-1]
    latest_account = account_rows[-1]
    latest_equity_date = str(latest_equity.get("snapshot_date", "")).strip()
    latest_drawdown_date = str(latest_drawdown.get("snapshot_date", "")).strip()

    primary_mdd_row = min(drawdown_rows, key=lambda row: float(row.get("primary_drawdown_pct", "0") or 0))
    secondary_mdd_row = min(drawdown_rows, key=lambda row: float(row.get("secondary_drawdown_pct", "0") or 0))

    warnings: list[str] = []
    if latest_equity_date != latest_drawdown_date:
        warnings.append(
            f"Latest equity date ({latest_equity_date}) and drawdown date ({latest_drawdown_date}) do not match."
        )
    if str(latest_account.get("market_valuation_status", "")).strip() != "success":
        warnings.append(
            "Latest market_valuation_status is not success: "
            + (str(latest_account.get("market_valuation_status", "")).strip() or "<blank>")
        )
    if len(equity_rows) <= 5:
        warnings.append(
            f"Snapshot row count is only {len(equity_rows)}, so performance interpretation is preliminary."
        )
    if any(str(row.get("market_valuation_status", "")).strip() != "success" for row in drawdown_rows):
        warnings.append("Some rows have market_valuation_status != success.")

    return {
        "first_snapshot_date": equity_rows[0]["snapshot_date"],
        "latest_snapshot_date": latest_equity_date,
        "snapshot_count": len(equity_rows),
        "equity_first": equity_rows[0],
        "equity_latest": latest_equity,
        "drawdown_latest": latest_drawdown,
        "account_latest": latest_account,
        "position_latest_date": latest_position_snapshot_date,
        "position_latest_rows": latest_position_rows,
        "primary_mdd_row": primary_mdd_row,
        "secondary_mdd_row": secondary_mdd_row,
        "warnings": warnings,
    }


def render_paper_performance_summary_markdown(summary: dict[str, Any]) -> str:
    equity_first = summary["equity_first"]
    equity_latest = summary["equity_latest"]
    drawdown_latest = summary["drawdown_latest"]
    account_latest = summary["account_latest"]
    latest_positions = summary["position_latest_rows"]
    primary_mdd_row = summary["primary_mdd_row"]
    secondary_mdd_row = summary["secondary_mdd_row"]

    lines = ["# Paper Performance Summary", ""]

    if summary["warnings"]:
        lines.extend(["## Warnings"] + [f"- {warning}" for warning in summary["warnings"]] + [""])

    lines.extend(
        [
            "## Summary",
            f"- Latest Snapshot Date: {summary['latest_snapshot_date']}",
            f"- Primary Equity: {_value_or_na(equity_latest.get('primary_equity', ''), _format_money)}",
            f"- Secondary Equity: {_value_or_na(equity_latest.get('secondary_equity', ''), _format_money)}",
            f"- Primary Return From Start: {_value_or_na(equity_latest.get('primary_return_from_start_pct', ''), _format_pct)}",
            f"- Secondary Return From Start: {_value_or_na(equity_latest.get('secondary_return_from_start_pct', ''), _format_pct)}",
            f"- Latest Primary Drawdown: {_value_or_na(drawdown_latest.get('primary_drawdown_pct', ''), _format_pct)}",
            f"- Primary MDD: {_value_or_na(primary_mdd_row.get('primary_drawdown_pct', ''), _format_pct)}",
            f"- Cash: {_value_or_na(equity_latest.get('cash', ''), _format_money)}",
            f"- Cash Ratio: {_value_or_na(equity_latest.get('cash_ratio_market', ''), _format_ratio_as_pct)}",
            f"- Open Position Count: {_value_or_na(equity_latest.get('open_position_count', ''))}",
            f"- Market Valuation Status: {account_latest.get('market_valuation_status', '') or 'N/A'}",
            "",
            "## Equity Summary",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Start Date | {summary['first_snapshot_date']} |",
            f"| Latest Date | {summary['latest_snapshot_date']} |",
            f"| Start Primary Equity | {_value_or_na(equity_first.get('primary_equity', ''), _format_money)} |",
            f"| Latest Primary Equity | {_value_or_na(equity_latest.get('primary_equity', ''), _format_money)} |",
            f"| Primary Return From Start | {_value_or_na(equity_latest.get('primary_return_from_start_pct', ''), _format_pct)} |",
            f"| Start Secondary Equity | {_value_or_na(equity_first.get('secondary_equity', ''), _format_money)} |",
            f"| Latest Secondary Equity | {_value_or_na(equity_latest.get('secondary_equity', ''), _format_money)} |",
            f"| Secondary Return From Start | {_value_or_na(equity_latest.get('secondary_return_from_start_pct', ''), _format_pct)} |",
            "",
            "## Drawdown Summary",
            "| Metric | Value |",
            "| --- | --- |",
            f"| Latest Primary Drawdown | {_value_or_na(drawdown_latest.get('primary_drawdown_pct', ''), _format_pct)} |",
            f"| Primary MDD | {_value_or_na(primary_mdd_row.get('primary_drawdown_pct', ''), _format_pct)} |",
            f"| Primary MDD Date | {primary_mdd_row.get('snapshot_date', '') or 'N/A'} |",
            f"| Latest Secondary Drawdown | {_value_or_na(drawdown_latest.get('secondary_drawdown_pct', ''), _format_pct)} |",
            f"| Secondary MDD | {_value_or_na(secondary_mdd_row.get('secondary_drawdown_pct', ''), _format_pct)} |",
            f"| Secondary MDD Date | {secondary_mdd_row.get('snapshot_date', '') or 'N/A'} |",
            "",
            "## PnL Summary",
            f"- Realized PnL: {_value_or_na(account_latest.get('realized_pnl', ''), _format_money)}",
            f"- Unrealized PnL: {_value_or_na(account_latest.get('unrealized_pnl', ''), _format_money)}",
            f"- Total PnL: {_value_or_na(account_latest.get('total_pnl', ''), _format_money)}",
            "- Relationship: total_pnl = realized_pnl + unrealized_pnl",
            "",
            "## Allocation Summary",
            f"- Cash: {_value_or_na(equity_latest.get('cash', ''), _format_money)}",
            f"- Positions Market Value: {_value_or_na(equity_latest.get('positions_market_value', ''), _format_money)}",
            f"- Cash Ratio Market: {_value_or_na(equity_latest.get('cash_ratio_market', ''), _format_ratio_as_pct)}",
            f"- Position Ratio Market: {_value_or_na(equity_latest.get('position_ratio_market', ''), _format_ratio_as_pct)}",
            f"- Open Position Count: {_value_or_na(equity_latest.get('open_position_count', ''))}",
            "",
            "## Open Positions",
            f"- Snapshot Date: {summary['position_latest_date']}",
            "",
            "| Symbol | Shares | Avg Price | Close Price | Cost Value | Market Value | Unrealized PnL | Unrealized Return |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for row in latest_positions:
        lines.append(
            "| "
            + " | ".join(
                [
                    str(row.get("symbol", "") or "N/A"),
                    _value_or_na(row.get("shares", ""), _format_shares),
                    _value_or_na(row.get("avg_price", ""), _format_money),
                    _value_or_na(row.get("close_price", row.get("market_price", "")), _format_money),
                    _value_or_na(row.get("cost_value", row.get("cost_basis", "")), _format_money),
                    _value_or_na(row.get("market_value", ""), _format_money),
                    _value_or_na(row.get("unrealized_pnl", ""), _format_money),
                    _value_or_na(row.get("unrealized_pnl_pct", row.get("unrealized_return_pct", "")), _format_ratio_as_pct),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Limitations",
            "- Snapshot row count may still be small, so performance interpretation is preliminary.",
            "- Benchmark, Sharpe, Sortino, and CAGR are not included yet.",
            "- This report is for paper-test only and is not real investment performance.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_paper_performance_summary(markdown: str, output_path: Path) -> None:
    assert_paper_path(output_path, PAPER_TEST_DIR)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
