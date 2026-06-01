from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_paths import PaperAccountPaths
from core.paths import PAPER_TEST_DIR


REPORTS_DIR = PAPER_TEST_DIR / "reports"
EQUITY_CURVE_PATH = REPORTS_DIR / "paper_equity_curve.csv"
PAPER_DRAWDOWN_PATH = REPORTS_DIR / "paper_drawdown.csv"
PAPER_DRAWDOWN_SUMMARY_PATH = REPORTS_DIR / "paper_drawdown_summary.md"

REQUIRED_EQUITY_COLUMNS = [
    "snapshot_date",
    "primary_equity",
    "secondary_equity",
    "market_valuation_status",
]

PAPER_DRAWDOWN_COLUMNS = [
    "snapshot_date",
    "primary_equity",
    "primary_peak_equity",
    "primary_drawdown",
    "primary_drawdown_pct",
    "secondary_equity",
    "secondary_peak_equity",
    "secondary_drawdown",
    "secondary_drawdown_pct",
    "market_valuation_status",
    "is_primary_new_peak",
    "is_secondary_new_peak",
    "primary_mdd_to_date_pct",
    "secondary_mdd_to_date_pct",
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


def load_equity_curve(path: Path = EQUITY_CURVE_PATH) -> list[dict[str, str]]:
    rows = read_csv_rows(path)
    if not rows:
        raise ValueError("paper_equity_curve.csv is empty")

    missing_columns = [column for column in REQUIRED_EQUITY_COLUMNS if column not in rows[0]]
    if missing_columns:
        raise ValueError("Missing equity curve columns: " + ", ".join(missing_columns))

    normalized_dates: list[str] = []
    for row in rows:
        row["snapshot_date"] = normalize_date(row.get("snapshot_date", ""))
        normalized_dates.append(row["snapshot_date"])

    duplicate_dates = sorted({date for date in normalized_dates if normalized_dates.count(date) > 1})
    if duplicate_dates:
        raise ValueError("Duplicate snapshot_date values: " + ", ".join(duplicate_dates))

    return sorted(rows, key=lambda row: row["snapshot_date"])


def build_paper_drawdown(equity_rows: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[str]]:
    if not equity_rows:
        raise ValueError("paper equity curve rows are empty")

    drawdown_rows: list[dict[str, Any]] = []
    warnings: list[str] = []

    primary_peak: float | None = None
    secondary_peak: float | None = None
    primary_mdd_to_date: float = 0.0
    secondary_mdd_to_date: float = 0.0

    for row in equity_rows:
        snapshot_date = row["snapshot_date"]
        primary_equity = to_float(row.get("primary_equity", ""), "primary_equity")
        secondary_equity = to_float(row.get("secondary_equity", ""), "secondary_equity")
        status = str(row.get("market_valuation_status", "")).strip()
        if status != "success":
            warnings.append(f"{snapshot_date}: market_valuation_status={status or '<blank>'}")

        is_primary_new_peak = primary_peak is None or primary_equity >= primary_peak
        is_secondary_new_peak = secondary_peak is None or secondary_equity >= secondary_peak
        primary_peak = primary_equity if primary_peak is None else max(primary_peak, primary_equity)
        secondary_peak = secondary_equity if secondary_peak is None else max(secondary_peak, secondary_equity)

        primary_drawdown = primary_equity - primary_peak
        secondary_drawdown = secondary_equity - secondary_peak
        primary_drawdown_pct = (primary_drawdown / primary_peak * 100.0) if primary_peak > 0 else ""
        secondary_drawdown_pct = (secondary_drawdown / secondary_peak * 100.0) if secondary_peak > 0 else ""

        if primary_drawdown_pct != "":
            primary_mdd_to_date = min(primary_mdd_to_date, float(primary_drawdown_pct))
        if secondary_drawdown_pct != "":
            secondary_mdd_to_date = min(secondary_mdd_to_date, float(secondary_drawdown_pct))

        drawdown_rows.append(
            {
                "snapshot_date": snapshot_date,
                "primary_equity": primary_equity,
                "primary_peak_equity": primary_peak,
                "primary_drawdown": primary_drawdown,
                "primary_drawdown_pct": primary_drawdown_pct,
                "secondary_equity": secondary_equity,
                "secondary_peak_equity": secondary_peak,
                "secondary_drawdown": secondary_drawdown,
                "secondary_drawdown_pct": secondary_drawdown_pct,
                "market_valuation_status": status,
                "is_primary_new_peak": "Y" if is_primary_new_peak else "N",
                "is_secondary_new_peak": "Y" if is_secondary_new_peak else "N",
                "primary_mdd_to_date_pct": primary_mdd_to_date,
                "secondary_mdd_to_date_pct": secondary_mdd_to_date,
            }
        )

    return drawdown_rows, warnings


def summarize_drawdown(drawdown_rows: list[dict[str, Any]], warnings: list[str]) -> dict[str, Any]:
    if not drawdown_rows:
        raise ValueError("paper drawdown rows are empty")
    latest = drawdown_rows[-1]
    primary_mdd_pct = min(float(row["primary_drawdown_pct"]) for row in drawdown_rows)
    secondary_mdd_pct = min(float(row["secondary_drawdown_pct"]) for row in drawdown_rows)
    return {
        "row_count": len(drawdown_rows),
        "first_snapshot_date": drawdown_rows[0]["snapshot_date"],
        "latest_snapshot_date": latest["snapshot_date"],
        "latest_primary_drawdown_pct": latest["primary_drawdown_pct"],
        "latest_secondary_drawdown_pct": latest["secondary_drawdown_pct"],
        "primary_mdd_pct": primary_mdd_pct,
        "secondary_mdd_pct": secondary_mdd_pct,
        "warnings": warnings,
    }


def save_drawdown(rows: list[dict[str, Any]], output_path: Path = PAPER_DRAWDOWN_PATH) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAPER_DRAWDOWN_COLUMNS)
        writer.writeheader()
        for row in rows:
            serialized: dict[str, Any] = {}
            for column in PAPER_DRAWDOWN_COLUMNS:
                value = row.get(column, "")
                if isinstance(value, float):
                    if column.endswith("_pct"):
                        serialized[column] = f"{value:.7f}"
                    else:
                        serialized[column] = f"{value:.2f}"
                else:
                    serialized[column] = value
            writer.writerow(serialized)


def save_drawdown_summary(summary: dict[str, Any], output_path: Path = PAPER_DRAWDOWN_SUMMARY_PATH) -> None:
    lines = [
        "# Paper Drawdown Summary",
        "",
        f"- Row count: {summary['row_count']}",
        f"- First snapshot_date: {summary['first_snapshot_date']}",
        f"- Latest snapshot_date: {summary['latest_snapshot_date']}",
        f"- Latest primary_drawdown_pct: {summary['latest_primary_drawdown_pct']:.7f}%",
        f"- Latest secondary_drawdown_pct: {summary['latest_secondary_drawdown_pct']:.7f}%",
        f"- Primary MDD pct: {summary['primary_mdd_pct']:.7f}%",
        f"- Secondary MDD pct: {summary['secondary_mdd_pct']:.7f}%",
        "",
        "## Notes",
        "- Primary drawdown uses total_equity_market_value.",
        "- Secondary drawdown uses total_equity_cost_basis.",
        "- Snapshot row count may still be small, so drawdown/MDD interpretation is preliminary.",
        "",
        "## Warnings",
    ]
    if summary["warnings"]:
        lines.extend(f"- {warning}" for warning in summary["warnings"])
    else:
        lines.append("- None")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_paper_drawdown(
    equity_curve_path: Path = EQUITY_CURVE_PATH,
    output_path: Path = PAPER_DRAWDOWN_PATH,
    summary_path: Path = PAPER_DRAWDOWN_SUMMARY_PATH,
) -> dict[str, Any]:
    equity_rows = load_equity_curve(equity_curve_path)
    drawdown_rows, warnings = build_paper_drawdown(equity_rows)
    summary = summarize_drawdown(drawdown_rows, warnings)
    save_drawdown(drawdown_rows, output_path)
    save_drawdown_summary(summary, summary_path)
    return {
        "row_count": len(drawdown_rows),
        "output_path": output_path,
        "summary_path": summary_path,
        "latest": drawdown_rows[-1],
        "summary": summary,
    }


def generate_paper_drawdown_for_account(
    account_paths: PaperAccountPaths | None = None,
) -> dict[str, Any]:
    if account_paths is not None and account_paths.account_id != "paper_default":
        reports_dir = account_paths.reports_dir
        return generate_paper_drawdown(
            equity_curve_path=reports_dir / "paper_equity_curve.csv",
            output_path=reports_dir / "paper_drawdown.csv",
            summary_path=reports_dir / "paper_drawdown_summary.md",
        )
    return generate_paper_drawdown()


def main() -> int:
    result = generate_paper_drawdown()
    print("Paper drawdown generated")
    print(f"  output_path: {result['output_path']}")
    print(f"  summary_path: {result['summary_path']}")
    print(f"  row_count: {result['row_count']}")
    print(f"  latest_snapshot_date: {result['latest']['snapshot_date']}")
    print(f"  primary_mdd_pct: {result['summary']['primary_mdd_pct']:.7f}")
    print(f"  secondary_mdd_pct: {result['summary']['secondary_mdd_pct']:.7f}")
    print(f"  warnings: {len(result['summary']['warnings'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
