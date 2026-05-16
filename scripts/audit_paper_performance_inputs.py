from __future__ import annotations

import csv
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_state import build_paper_state_from_trades
from core.paths import PAPER_TEST_DIR


REPORTS_DIR = PAPER_TEST_DIR / "reports"
ACCOUNT_SNAPSHOT_PATH = PAPER_TEST_DIR / "paper_account_snapshot.csv"
POSITION_SNAPSHOT_PATH = PAPER_TEST_DIR / "paper_position_snapshot.csv"
EXECUTION_LOG_PATH = PAPER_TEST_DIR / "paper_execution_log.csv"
AUDIT_REPORT_PATH = REPORTS_DIR / "paper_performance_input_audit.md"
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

POSITION_LOGICAL_COLUMNS = {
    "snapshot_date": ["snapshot_date"],
    "symbol": ["symbol"],
    "shares": ["shares"],
    "avg_price": ["avg_price"],
    "cost_basis": ["cost_basis", "cost_value"],
    "market_price": ["market_price", "close_price"],
    "market_value": ["market_value"],
    "unrealized_pnl": ["unrealized_pnl"],
    "unrealized_return_pct": ["unrealized_return_pct", "unrealized_pnl_pct"],
    "position_status": ["position_status"],
}


@dataclass
class AuditSection:
    summary: dict[str, Any]
    issues: list[str]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_date(value: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError("blank date")
    if len(clean) == 8 and clean.isdigit():
        return datetime.strptime(clean, "%Y%m%d").strftime("%Y-%m-%d")
    return datetime.strptime(clean, "%Y-%m-%d").strftime("%Y-%m-%d")


def is_blank(value: Any) -> bool:
    text = str(value or "").strip()
    return text == ""


def to_float(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        raise ValueError("blank numeric")
    normalized = text.replace(",", "").replace("$", "")
    lowered = normalized.lower()
    if lowered in {"nan", "inf", "-inf", "infinity", "-infinity"}:
        raise ValueError(f"invalid numeric {value}")
    return float(normalized)


def almost_equal(left: float, right: float, tolerance: float = TOLERANCE) -> bool:
    return abs(left - right) <= tolerance


def resolve_position_columns(fieldnames: list[str]) -> tuple[dict[str, str], list[str]]:
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for logical_name, candidates in POSITION_LOGICAL_COLUMNS.items():
        found = next((candidate for candidate in candidates if candidate in fieldnames), None)
        if found is None:
            missing.append(logical_name)
        else:
            resolved[logical_name] = found
    return resolved, missing


def audit_account_snapshot(rows: list[dict[str, str]]) -> AuditSection:
    issues: list[str] = []
    fieldnames = list(rows[0].keys()) if rows else []
    missing_columns = [column for column in REQUIRED_ACCOUNT_COLUMNS if column not in fieldnames]
    if missing_columns:
        issues.append(f"Missing account snapshot columns: {', '.join(missing_columns)}")

    date_values: list[str] = []
    duplicate_dates: list[str] = []
    date_counter: Counter[str] = Counter()
    invalid_date_rows = 0
    for row in rows:
        try:
            normalized = normalize_date(row.get("snapshot_date", ""))
            date_values.append(normalized)
            date_counter[normalized] += 1
        except ValueError:
            invalid_date_rows += 1
    duplicate_dates = sorted([date for date, count in date_counter.items() if count > 1])
    if invalid_date_rows:
        issues.append(f"Account snapshot has {invalid_date_rows} invalid snapshot_date rows")
    if duplicate_dates:
        issues.append(f"Duplicate account snapshot_date values: {', '.join(duplicate_dates)}")

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
    numeric_invalid_counts: Counter[str] = Counter()
    negative_cash_dates: list[str] = []
    nonpositive_equity_dates: list[str] = []
    market_status_counts: Counter[str] = Counter()
    success_blank_market_value_dates: list[str] = []
    identity_mismatches: list[str] = []
    market_identity_mismatches: list[str] = []
    pnl_identity_mismatches: list[str] = []

    for row in rows:
        snapshot_date = row.get("snapshot_date", "")
        parsed: dict[str, float] = {}
        for column in numeric_columns:
            try:
                parsed[column] = to_float(row.get(column, ""))
            except ValueError:
                numeric_invalid_counts[column] += 1

        if "cash" in parsed and parsed["cash"] < 0:
            negative_cash_dates.append(snapshot_date)
        if "total_equity_market_value" in parsed and parsed["total_equity_market_value"] <= 0:
            nonpositive_equity_dates.append(snapshot_date)

        status = str(row.get("market_valuation_status", "")).strip() or "<blank>"
        market_status_counts[status] += 1
        if status == "success" and is_blank(row.get("positions_market_value", "")):
            success_blank_market_value_dates.append(snapshot_date)

        if all(key in parsed for key in ("cash", "positions_cost_value", "total_equity_cost_basis")):
            lhs = parsed["cash"] + parsed["positions_cost_value"]
            rhs = parsed["total_equity_cost_basis"]
            if not almost_equal(lhs, rhs):
                identity_mismatches.append(snapshot_date)

        if all(key in parsed for key in ("cash", "positions_market_value", "total_equity_market_value")):
            lhs = parsed["cash"] + parsed["positions_market_value"]
            rhs = parsed["total_equity_market_value"]
            if not almost_equal(lhs, rhs):
                market_identity_mismatches.append(snapshot_date)

        if all(key in parsed for key in ("realized_pnl", "unrealized_pnl", "total_pnl")):
            lhs = parsed["realized_pnl"] + parsed["unrealized_pnl"]
            rhs = parsed["total_pnl"]
            if not almost_equal(lhs, rhs):
                pnl_identity_mismatches.append(snapshot_date)

    for column, count in numeric_invalid_counts.items():
        if count:
            issues.append(f"Account snapshot column {column} has {count} invalid numeric rows")
    if negative_cash_dates:
        issues.append(f"Negative cash found on: {', '.join(negative_cash_dates)}")
    if nonpositive_equity_dates:
        issues.append(f"Non-positive total_equity_market_value on: {', '.join(nonpositive_equity_dates)}")
    if success_blank_market_value_dates:
        issues.append(
            "market_valuation_status=success with blank positions_market_value on: "
            + ", ".join(success_blank_market_value_dates)
        )
    if identity_mismatches:
        issues.append("Cost-basis identity mismatch on: " + ", ".join(identity_mismatches))
    if market_identity_mismatches:
        issues.append("Market-value identity mismatch on: " + ", ".join(market_identity_mismatches))
    if pnl_identity_mismatches:
        issues.append("PnL identity mismatch on: " + ", ".join(pnl_identity_mismatches))

    summary = {
        "columns": fieldnames,
        "row_count": len(rows),
        "latest_snapshot_date": max(date_values) if date_values else None,
        "duplicate_dates": duplicate_dates,
        "market_valuation_status_counts": dict(market_status_counts),
        "negative_cash_count": len(negative_cash_dates),
        "nonpositive_equity_count": len(nonpositive_equity_dates),
    }
    return AuditSection(summary=summary, issues=issues)


def audit_position_snapshot(rows: list[dict[str, str]]) -> AuditSection:
    issues: list[str] = []
    fieldnames = list(rows[0].keys()) if rows else []
    resolved_columns, missing_logical_columns = resolve_position_columns(fieldnames)
    if missing_logical_columns:
        issues.append("Missing position snapshot logical columns: " + ", ".join(missing_logical_columns))

    date_counter: Counter[str] = Counter()
    invalid_date_rows = 0
    duplicate_keys: list[str] = []
    blank_symbols: list[str] = []
    nonpositive_shares: list[str] = []
    formula_cost_mismatches: list[str] = []
    formula_market_mismatches: list[str] = []
    open_position_counts: dict[str, int] = defaultdict(int)
    seen_keys: Counter[tuple[str, str]] = Counter()

    for row in rows:
        try:
            normalized_date = normalize_date(row.get(resolved_columns.get("snapshot_date", "snapshot_date"), ""))
            date_counter[normalized_date] += 1
        except ValueError:
            invalid_date_rows += 1
            normalized_date = "<invalid>"

        symbol = str(row.get(resolved_columns.get("symbol", "symbol"), "")).strip()
        if not symbol:
            blank_symbols.append(normalized_date)
        key = (normalized_date, symbol)
        seen_keys[key] += 1

        if all(name in resolved_columns for name in ("shares", "avg_price", "cost_basis")):
            try:
                shares = to_float(row.get(resolved_columns["shares"], ""))
                avg_price = to_float(row.get(resolved_columns["avg_price"], ""))
                cost_basis = to_float(row.get(resolved_columns["cost_basis"], ""))
                if shares <= 0:
                    nonpositive_shares.append(f"{normalized_date}:{symbol}")
                if not almost_equal(shares * avg_price, cost_basis):
                    formula_cost_mismatches.append(f"{normalized_date}:{symbol}")
            except ValueError:
                issues.append(f"Invalid numeric position row for cost basis check: {normalized_date}:{symbol}")

        if all(name in resolved_columns for name in ("shares", "market_price", "market_value")):
            try:
                shares = to_float(row.get(resolved_columns["shares"], ""))
                market_price = to_float(row.get(resolved_columns["market_price"], ""))
                market_value = to_float(row.get(resolved_columns["market_value"], ""))
                if not almost_equal(shares * market_price, market_value):
                    formula_market_mismatches.append(f"{normalized_date}:{symbol}")
            except ValueError:
                issues.append(f"Invalid numeric position row for market value check: {normalized_date}:{symbol}")

        status_column = resolved_columns.get("position_status")
        if status_column and str(row.get(status_column, "")).strip().upper() == "OPEN":
            open_position_counts[normalized_date] += 1

    duplicate_keys = sorted(
        [f"{snapshot_date}:{symbol}" for (snapshot_date, symbol), count in seen_keys.items() if count > 1]
    )

    if invalid_date_rows:
        issues.append(f"Position snapshot has {invalid_date_rows} invalid snapshot_date rows")
    if duplicate_keys:
        issues.append("Duplicate snapshot_date+symbol rows: " + ", ".join(duplicate_keys))
    if blank_symbols:
        issues.append("Blank symbol rows on: " + ", ".join(blank_symbols))
    if nonpositive_shares:
        issues.append("Non-positive shares on: " + ", ".join(nonpositive_shares))
    if formula_cost_mismatches:
        issues.append("cost_basis/cost_value mismatch on: " + ", ".join(formula_cost_mismatches))
    if formula_market_mismatches:
        issues.append("market_value mismatch on: " + ", ".join(formula_market_mismatches))

    summary = {
        "columns": fieldnames,
        "resolved_columns": resolved_columns,
        "row_count": len(rows),
        "latest_snapshot_date": max(date_counter) if date_counter else None,
        "open_position_counts": dict(open_position_counts),
    }
    return AuditSection(summary=summary, issues=issues)


def cross_validate_account_vs_position(
    account_rows: list[dict[str, str]],
    position_rows: list[dict[str, str]],
    resolved_position_columns: dict[str, str],
) -> AuditSection:
    issues: list[str] = []
    position_cost_sums: dict[str, float] = defaultdict(float)
    position_market_sums: dict[str, float] = defaultdict(float)

    for row in position_rows:
        snapshot_date = normalize_date(row[resolved_position_columns["snapshot_date"]])
        position_cost_sums[snapshot_date] += to_float(row[resolved_position_columns["cost_basis"]])
        position_market_sums[snapshot_date] += to_float(row[resolved_position_columns["market_value"]])

    mismatch_cost_dates: list[str] = []
    mismatch_market_dates: list[str] = []

    for row in account_rows:
        snapshot_date = normalize_date(row["snapshot_date"])
        account_cost = to_float(row["positions_cost_value"])
        account_market = to_float(row["positions_market_value"])
        if not almost_equal(account_cost, position_cost_sums.get(snapshot_date, 0.0)):
            mismatch_cost_dates.append(snapshot_date)
        if not almost_equal(account_market, position_market_sums.get(snapshot_date, 0.0)):
            mismatch_market_dates.append(snapshot_date)

    if mismatch_cost_dates:
        issues.append("Account vs position cost sum mismatch on: " + ", ".join(mismatch_cost_dates))
    if mismatch_market_dates:
        issues.append("Account vs position market sum mismatch on: " + ", ".join(mismatch_market_dates))

    summary = {
        "matched_dates": len(account_rows) - len(set(mismatch_cost_dates + mismatch_market_dates)),
        "account_dates": [normalize_date(row["snapshot_date"]) for row in account_rows],
    }
    return AuditSection(summary=summary, issues=issues)


def compare_latest_execution_log_state(
    execution_rows: list[dict[str, str]],
    account_rows: list[dict[str, str]],
    position_rows: list[dict[str, str]],
    resolved_position_columns: dict[str, str],
) -> AuditSection:
    issues: list[str] = []
    latest_account_date = max(normalize_date(row["snapshot_date"]) for row in account_rows)
    latest_positions = [
        row for row in position_rows
        if normalize_date(row[resolved_position_columns["snapshot_date"]]) == latest_account_date
    ]
    state = build_paper_state_from_trades(execution_rows)

    latest_snapshot_symbols = sorted(str(row[resolved_position_columns["symbol"]]).strip() for row in latest_positions)
    latest_state_symbols = sorted(state.positions.keys())
    if latest_snapshot_symbols != latest_state_symbols:
        issues.append(
            "Latest snapshot symbols do not match reducer symbols: "
            f"snapshot={latest_snapshot_symbols}, reducer={latest_state_symbols}"
        )

    share_mismatches: list[str] = []
    avg_price_mismatches: list[str] = []
    for row in latest_positions:
        symbol = str(row[resolved_position_columns["symbol"]]).strip()
        if symbol not in state.positions:
            continue
        snapshot_shares = to_float(row[resolved_position_columns["shares"]])
        snapshot_avg_price = to_float(row[resolved_position_columns["avg_price"]])
        position = state.positions[symbol]
        if not almost_equal(snapshot_shares, float(position.shares), tolerance=0.001):
            share_mismatches.append(symbol)
        if not almost_equal(snapshot_avg_price, float(position.avg_price)):
            avg_price_mismatches.append(symbol)

    latest_account_row = next(row for row in account_rows if normalize_date(row["snapshot_date"]) == latest_account_date)
    snapshot_cash = to_float(latest_account_row["cash"])
    if not almost_equal(snapshot_cash, float(state.cash)):
        issues.append(f"Latest snapshot cash does not match reducer cash: snapshot={snapshot_cash}, reducer={state.cash}")
    if share_mismatches:
        issues.append("Latest snapshot share mismatch symbols: " + ", ".join(sorted(share_mismatches)))
    if avg_price_mismatches:
        issues.append("Latest snapshot avg_price mismatch symbols: " + ", ".join(sorted(avg_price_mismatches)))

    summary = {
        "latest_snapshot_date": latest_account_date,
        "latest_snapshot_symbols": latest_snapshot_symbols,
        "latest_reducer_symbols": latest_state_symbols,
        "latest_snapshot_cash": snapshot_cash,
        "latest_reducer_cash": round(float(state.cash), 2),
    }
    return AuditSection(summary=summary, issues=issues)


def render_report(
    account_section: AuditSection,
    position_section: AuditSection,
    cross_section: AuditSection,
    execution_section: AuditSection,
) -> str:
    all_issues = (
        account_section.issues
        + position_section.issues
        + cross_section.issues
        + execution_section.issues
    )
    proceed = "Yes" if not all_issues else "Yes, with review" if len(all_issues) <= 3 else "No"
    lines = [
        "# Paper Performance Input Audit",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Proceed to PAPER8-2: {proceed}",
        "",
        "## Account Snapshot",
        f"- Row count: {account_section.summary.get('row_count')}",
        f"- Latest snapshot_date: {account_section.summary.get('latest_snapshot_date')}",
        f"- market_valuation_status: {account_section.summary.get('market_valuation_status_counts')}",
        "",
        "## Position Snapshot",
        f"- Row count: {position_section.summary.get('row_count')}",
        f"- Latest snapshot_date: {position_section.summary.get('latest_snapshot_date')}",
        f"- Open position counts: {position_section.summary.get('open_position_counts')}",
        "",
        "## Account vs Position Cross Check",
        f"- Matched account dates: {cross_section.summary.get('matched_dates')}",
        "",
        "## Execution Log Latest State Check",
        f"- Latest snapshot_date: {execution_section.summary.get('latest_snapshot_date')}",
        f"- Snapshot symbols: {execution_section.summary.get('latest_snapshot_symbols')}",
        f"- Reducer symbols: {execution_section.summary.get('latest_reducer_symbols')}",
        f"- Snapshot cash: {execution_section.summary.get('latest_snapshot_cash')}",
        f"- Reducer cash: {execution_section.summary.get('latest_reducer_cash')}",
        "",
        "## Issues",
    ]
    if not all_issues:
        lines.append("- No issues detected")
    else:
        lines.extend(f"- {issue}" for issue in all_issues)
    return "\n".join(lines) + "\n"


def run_audit(
    account_snapshot_path: Path = ACCOUNT_SNAPSHOT_PATH,
    position_snapshot_path: Path = POSITION_SNAPSHOT_PATH,
    execution_log_path: Path = EXECUTION_LOG_PATH,
    report_path: Path = AUDIT_REPORT_PATH,
) -> dict[str, Any]:
    account_rows = read_csv_rows(account_snapshot_path)
    position_rows = read_csv_rows(position_snapshot_path)
    execution_rows = read_csv_rows(execution_log_path)

    account_section = audit_account_snapshot(account_rows)
    position_section = audit_position_snapshot(position_rows)
    resolved_position_columns = position_section.summary["resolved_columns"]
    cross_section = cross_validate_account_vs_position(account_rows, position_rows, resolved_position_columns)
    execution_section = compare_latest_execution_log_state(
        execution_rows,
        account_rows,
        position_rows,
        resolved_position_columns,
    )

    report_text = render_report(account_section, position_section, cross_section, execution_section)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report_text, encoding="utf-8")

    return {
        "report_path": report_path,
        "account": account_section,
        "position": position_section,
        "cross": cross_section,
        "execution": execution_section,
        "issues": (
            account_section.issues
            + position_section.issues
            + cross_section.issues
            + execution_section.issues
        ),
    }


def main() -> None:
    result = run_audit()
    print(f"Audit report written: {result['report_path']}")
    print(f"Issue count: {len(result['issues'])}")


if __name__ == "__main__":
    main()
