from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_paths import PaperAccountPaths
from core.paths import PAPER_TEST_DIR


ACCOUNT_SNAPSHOT_PATH = PAPER_TEST_DIR / "paper_account_snapshot.csv"
POSITION_SNAPSHOT_PATH = PAPER_TEST_DIR / "paper_position_snapshot.csv"
REPORTS_DIR = PAPER_TEST_DIR / "reports"
EQUITY_CURVE_PATH = REPORTS_DIR / "paper_equity_curve.csv"
EQUITY_CURVE_SUMMARY_PATH = REPORTS_DIR / "paper_equity_curve_summary.md"
TOLERANCE = 0.05

REQUIRED_ACCOUNT_COLUMNS = [
    "snapshot_date",
    "cash",
    "positions_cost_value",
    "total_equity_cost_basis",
    "positions_market_value",
    "total_equity_market_value",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "market_valuation_status",
]

EQUITY_CURVE_COLUMNS = [
    "snapshot_date",
    "primary_equity",
    "secondary_equity",
    "cash",
    "positions_market_value",
    "positions_cost_value",
    "realized_pnl",
    "unrealized_pnl",
    "total_pnl",
    "market_valuation_status",
    "primary_return_from_start_pct",
    "secondary_return_from_start_pct",
    "cash_ratio_market",
    "position_ratio_market",
    "open_position_count",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_date(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError("blank snapshot_date")
    if len(clean) == 8 and clean.isdigit():
        return datetime.strptime(clean, "%Y%m%d").strftime("%Y-%m-%d")
    return datetime.strptime(clean, "%Y-%m-%d").strftime("%Y-%m-%d")


def to_float(value: Any, column_name: str) -> float:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"blank numeric in {column_name}")
    normalized = text.replace(",", "").replace("$", "")
    lowered = normalized.lower()
    if lowered in {"nan", "inf", "-inf", "infinity", "-infinity"}:
        raise ValueError(f"invalid numeric in {column_name}: {value}")
    try:
        return float(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid numeric in {column_name}: {value}") from exc


def load_account_snapshot(path: Path = ACCOUNT_SNAPSHOT_PATH) -> list[dict[str, str]]:
    rows = read_csv_rows(path)
    if not rows:
        raise ValueError("paper_account_snapshot.csv is empty")

    missing_columns = [column for column in REQUIRED_ACCOUNT_COLUMNS if column not in rows[0]]
    if missing_columns:
        raise ValueError("Missing account snapshot columns: " + ", ".join(missing_columns))

    normalized_dates: list[str] = []
    for row in rows:
        row["snapshot_date"] = normalize_date(row.get("snapshot_date", ""))
        normalized_dates.append(row["snapshot_date"])

    duplicate_dates = sorted({date for date in normalized_dates if normalized_dates.count(date) > 1})
    if duplicate_dates:
        raise ValueError("Duplicate snapshot_date values: " + ", ".join(duplicate_dates))

    return sorted(rows, key=lambda row: row["snapshot_date"])


def load_open_position_counts(path: Path = POSITION_SNAPSHOT_PATH) -> dict[str, int]:
    if not path.exists():
        return {}
    rows = read_csv_rows(path)
    counts: dict[str, int] = {}
    for row in rows:
        snapshot_date = normalize_date(row.get("snapshot_date", ""))
        status = str(row.get("position_status", "")).strip().upper()
        if status != "OPEN":
            continue
        counts[snapshot_date] = counts.get(snapshot_date, 0) + 1
    return counts


def build_paper_equity_curve(
    account_rows: list[dict[str, str]],
    position_open_counts: dict[str, int] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not account_rows:
        raise ValueError("paper account snapshot rows are empty")

    position_open_counts = position_open_counts or {}
    curve_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    first_primary: float | None = None
    first_secondary: float | None = None

    numeric_columns = [
        "cash",
        "positions_cost_value",
        "total_equity_cost_basis",
        "positions_market_value",
        "total_equity_market_value",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
    ]

    for row in account_rows:
        parsed = {
            column: to_float(row.get(column, ""), column)
            for column in numeric_columns
        }
        snapshot_date = row["snapshot_date"]
        primary_equity = parsed["total_equity_market_value"]
        secondary_equity = parsed["total_equity_cost_basis"]

        if first_primary is None:
            first_primary = primary_equity
            if first_primary <= 0:
                warnings.append("first_primary_equity <= 0; primary returns not calculated")
        if first_secondary is None:
            first_secondary = secondary_equity
            if first_secondary <= 0:
                warnings.append("first_secondary_equity <= 0; secondary returns not calculated")

        primary_return = ""
        secondary_return = ""
        if first_primary and first_primary > 0:
            primary_return = (primary_equity / first_primary - 1.0) * 100.0
        if first_secondary and first_secondary > 0:
            secondary_return = (secondary_equity / first_secondary - 1.0) * 100.0

        cash_ratio_market = ""
        position_ratio_market = ""
        if primary_equity > 0:
            cash_ratio_market = parsed["cash"] / primary_equity
            position_ratio_market = parsed["positions_market_value"] / primary_equity

        status = str(row.get("market_valuation_status", "")).strip()
        if status != "success":
            warnings.append(f"{snapshot_date}: market_valuation_status={status or '<blank>'}")

        curve_rows.append(
            {
                "snapshot_date": snapshot_date,
                "primary_equity": primary_equity,
                "secondary_equity": secondary_equity,
                "cash": parsed["cash"],
                "positions_market_value": parsed["positions_market_value"],
                "positions_cost_value": parsed["positions_cost_value"],
                "realized_pnl": parsed["realized_pnl"],
                "unrealized_pnl": parsed["unrealized_pnl"],
                "total_pnl": parsed["total_pnl"],
                "market_valuation_status": status,
                "primary_return_from_start_pct": primary_return,
                "secondary_return_from_start_pct": secondary_return,
                "cash_ratio_market": cash_ratio_market,
                "position_ratio_market": position_ratio_market,
                "open_position_count": position_open_counts.get(snapshot_date, ""),
            }
        )

    return curve_rows, warnings


def save_equity_curve(rows: list[dict[str, Any]], output_path: Path = EQUITY_CURVE_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EQUITY_CURVE_COLUMNS)
        writer.writeheader()
        for row in rows:
            serialized: dict[str, Any] = {}
            for column in EQUITY_CURVE_COLUMNS:
                value = row.get(column, "")
                if isinstance(value, float):
                    serialized[column] = f"{value:.7f}" if "ratio" in column else f"{value:.2f}"
                else:
                    serialized[column] = value
            writer.writerow(serialized)


def save_equity_curve_summary(
    curve_rows: list[dict[str, Any]],
    warnings: list[str],
    output_path: Path = EQUITY_CURVE_SUMMARY_PATH,
) -> None:
    latest = curve_rows[-1]
    lines = [
        "# Paper Equity Curve Summary",
        "",
        f"- Row count: {len(curve_rows)}",
        f"- First snapshot_date: {curve_rows[0]['snapshot_date']}",
        f"- Latest snapshot_date: {latest['snapshot_date']}",
        f"- Latest primary_equity: {latest['primary_equity']:.2f}",
        f"- Latest secondary_equity: {latest['secondary_equity']:.2f}",
        f"- Latest primary_return_from_start_pct: {latest['primary_return_from_start_pct'] if latest['primary_return_from_start_pct'] != '' else 'N/A'}",
        f"- Latest secondary_return_from_start_pct: {latest['secondary_return_from_start_pct'] if latest['secondary_return_from_start_pct'] != '' else 'N/A'}",
        "",
        "## Warnings",
    ]
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- None")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_paper_equity_curve(
    account_snapshot_path: Path = ACCOUNT_SNAPSHOT_PATH,
    position_snapshot_path: Path = POSITION_SNAPSHOT_PATH,
    output_path: Path = EQUITY_CURVE_PATH,
    summary_path: Path = EQUITY_CURVE_SUMMARY_PATH,
) -> dict[str, Any]:
    account_rows = load_account_snapshot(account_snapshot_path)
    position_open_counts = load_open_position_counts(position_snapshot_path)
    curve_rows, warnings = build_paper_equity_curve(account_rows, position_open_counts)
    save_equity_curve(curve_rows, output_path)
    save_equity_curve_summary(curve_rows, warnings, summary_path)
    return {
        "row_count": len(curve_rows),
        "output_path": output_path,
        "summary_path": summary_path,
        "latest": curve_rows[-1],
        "warnings": warnings,
    }


def generate_paper_equity_curve_for_account(
    account_paths: PaperAccountPaths | None = None,
) -> dict[str, Any]:
    if account_paths is not None and account_paths.account_id != "paper_default":
        return generate_paper_equity_curve(
            account_snapshot_path=account_paths.account_snapshot_path,
            position_snapshot_path=account_paths.position_snapshot_path,
            output_path=account_paths.reports_dir / "paper_equity_curve.csv",
            summary_path=account_paths.reports_dir / "paper_equity_curve_summary.md",
        )
    return generate_paper_equity_curve()


def main() -> int:
    result = generate_paper_equity_curve()
    print("Paper equity curve generated")
    print(f"  output_path: {result['output_path']}")
    print(f"  summary_path: {result['summary_path']}")
    print(f"  row_count: {result['row_count']}")
    print(f"  latest_snapshot_date: {result['latest']['snapshot_date']}")
    print(f"  latest_primary_equity: {result['latest']['primary_equity']:.2f}")
    print(f"  latest_secondary_equity: {result['latest']['secondary_equity']:.2f}")
    print(f"  warnings: {len(result['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
