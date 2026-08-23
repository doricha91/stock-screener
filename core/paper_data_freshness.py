from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paths import OUTPUTS, market_db_path, paper_reports_dir
from core.universe_manager import load_universe_snapshot_as_of_quarter


FRESHNESS_REPORT_PATH_NAMES = {
    "markdown": "paper_data_freshness_report.md",
    "issues": "paper_data_freshness_issues.csv",
}
REQUIRED_TABLES = ("daily_price", "market_index", "daily_indicators", "tickers")
REQUIRED_INDEX_SYMBOLS = ("SPY", "QQQ", "^VIX")
MIN_TICKER_COUNT = 50


def _normalize_date(date_str: str) -> str:
    clean = str(date_str).replace("-", "").strip()
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"Invalid date format: {date_str}")
    return datetime.strptime(clean, "%Y%m%d").strftime("%Y-%m-%d")


def _issue(
    severity: str,
    check_name: str,
    status: str,
    message: str,
    *,
    table: str = "",
    symbol: str = "",
    latest_date: str = "",
    row_count: int | None = None,
    suggestion: str = "",
) -> dict[str, Any]:
    return {
        "severity": severity,
        "check_name": check_name,
        "status": status,
        "message": message,
        "table": table,
        "symbol": symbol,
        "latest_date": latest_date,
        "row_count": "" if row_count is None else row_count,
        "suggestion": suggestion,
    }


def _connect_read_only(db_path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cur.fetchone() is not None


def _query_scalar(conn: sqlite3.Connection, query: str, params: tuple[Any, ...] = ()) -> Any:
    cur = conn.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    return row[0] if row else None


def _query_listing_board_distribution(conn: sqlite3.Connection) -> dict[str, int]:
    cur = conn.cursor()
    try:
        cur.execute("SELECT listing_board, COUNT(*) FROM tickers GROUP BY listing_board")
    except sqlite3.OperationalError:
        return {}
    rows = cur.fetchall()
    return {str(board): int(count) for board, count in rows}


def _quarter_label(date_value: str) -> str:
    parsed = datetime.strptime(date_value, "%Y-%m-%d")
    quarter = ((parsed.month - 1) // 3) + 1
    return f"{parsed.year}Q{quarter}"


def _build_universe_snapshot_check(target_date: str, universe_dir: Path) -> dict[str, Any]:
    selection = load_universe_snapshot_as_of_quarter(target_date, snapshots_dir=universe_dir)
    metadata = selection.get("metadata", {}) if isinstance(selection, dict) else {}
    selected_date = str(metadata.get("snapshot_date") or "")
    selected_path = str(metadata.get("snapshot_path") or "")
    warning = str(metadata.get("warning") or "")
    target_quarter = _quarter_label(target_date)
    selected_quarter = str(metadata.get("snapshot_quarter") or "")

    if warning:
        if "Failed to read" in warning:
            return _issue(
                "warning",
                "universe_snapshot",
                "unreadable",
                f"universe snapshot could not be read: {selected_path}",
                latest_date=selected_date,
                suggestion="Review or regenerate the selected universe snapshot",
            )
        if selected_date and selected_quarter != target_quarter:
            return _issue(
                "warning",
                "universe_snapshot",
                "fallback",
                (
                    "using prior-quarter universe snapshot under quarterly_as_of policy "
                    f"({selected_quarter} -> {target_quarter})"
                ),
                latest_date=selected_date,
                suggestion="Review fallback or create a same-quarter universe snapshot",
            )
        return _issue(
            "warning",
            "universe_snapshot",
            "missing",
            "optional universe snapshot is unavailable for quarterly_as_of selection",
            latest_date=selected_date or target_date,
            suggestion="Create a universe snapshot if quarterly as-of selection should be updated",
        )

    if selected_date == target_date:
        message = "exact universe snapshot exists for target_date"
    else:
        message = "selected same-quarter quarterly_as_of universe snapshot"
    return _issue(
        "info",
        "universe_snapshot",
        "ok",
        message,
        latest_date=selected_date,
        suggestion=f"Optional check passed: {selected_path}",
    )


def _apply_summary(target_date: str, db_path: Path, checks: list[dict[str, Any]]) -> dict[str, Any]:
    error_count = sum(1 for item in checks if item["severity"] == "error")
    warning_count = sum(1 for item in checks if item["severity"] == "warning")
    if error_count > 0:
        result = "FAIL"
    elif warning_count > 0:
        result = "PASS_WITH_WARNINGS"
    else:
        result = "PASS"
    return {
        "result": result,
        "error_count": error_count,
        "warning_count": warning_count,
        "target_date": target_date,
        "market_db_path": str(db_path),
        "checks": checks,
    }


def run_paper_data_freshness_check(
    *,
    date_str: str,
    strict: bool = False,
    db_path: str | Path | None = None,
    universe_root: str | Path | None = None,
) -> dict[str, Any]:
    target_date = _normalize_date(date_str)
    target_ts = datetime.strptime(target_date, "%Y-%m-%d").date()
    market_db = Path(db_path) if db_path is not None else Path(market_db_path())
    universe_dir = Path(universe_root) if universe_root is not None else (OUTPUTS / "universe")
    checks: list[dict[str, Any]] = []

    if not market_db.exists():
        checks.append(
            _issue(
                "error",
                "market_db_exists",
                "missing",
                "market_data.db does not exist",
                suggestion="Run prepare-data before planning",
            )
        )
        return _apply_summary(target_date, market_db, checks)

    try:
        conn = _connect_read_only(market_db)
    except sqlite3.Error as exc:
        checks.append(
            _issue(
                "error",
                "market_db_connect",
                "failed",
                f"failed to connect to market_data.db: {exc}",
                suggestion="Verify the DB path and file permissions",
            )
        )
        return _apply_summary(target_date, market_db, checks)

    with conn:
        for table in REQUIRED_TABLES:
            if not _table_exists(conn, table):
                checks.append(
                    _issue(
                        "error",
                        f"{table}_table_exists",
                        "missing",
                        f"required table is missing: {table}",
                        table=table,
                        suggestion="Initialize or restore the market DB schema",
                    )
                )

        if any(item["severity"] == "error" for item in checks):
            return _apply_summary(target_date, market_db, checks)

        daily_price_row_count = int(_query_scalar(conn, "SELECT COUNT(*) FROM daily_price") or 0)
        daily_price_latest = _query_scalar(conn, "SELECT MAX(date) FROM daily_price")
        daily_price_target_count = int(
            _query_scalar(conn, "SELECT COUNT(*) FROM daily_price WHERE date = ?", (target_date,)) or 0
        )
        daily_price_symbol_count = int(_query_scalar(conn, "SELECT COUNT(DISTINCT symbol) FROM daily_price") or 0)
        if daily_price_row_count == 0 or not daily_price_latest:
            checks.append(
                _issue(
                    "error",
                    "daily_price_data",
                    "empty",
                    "daily_price has no data",
                    table="daily_price",
                    row_count=daily_price_row_count,
                    suggestion="Refresh daily price data before planning",
                )
            )
        elif daily_price_target_count == 0:
            checks.append(
                _issue(
                    "error",
                    "daily_price_target_coverage",
                    "missing",
                    "daily_price has no rows for target_date",
                    table="daily_price",
                    latest_date=daily_price_latest,
                    row_count=daily_price_target_count,
                    suggestion="Refresh or restore exact target_date price coverage",
                )
            )
        elif datetime.strptime(daily_price_latest, "%Y-%m-%d").date() < target_ts:
            checks.append(
                _issue(
                    "error" if strict else "warning",
                    "daily_price_freshness",
                    "stale",
                    "daily_price latest date is older than target_date",
                    table="daily_price",
                    latest_date=daily_price_latest,
                    row_count=daily_price_row_count,
                    suggestion="Refresh price data or verify market holiday timing",
                )
            )
        else:
            checks.append(
                _issue(
                    "info",
                    "daily_price_freshness",
                    "ok",
                    "daily_price is available through target_date or later",
                    table="daily_price",
                    latest_date=daily_price_latest,
                    row_count=daily_price_row_count,
                )
            )
        checks.append(
            _issue(
                "info",
                "daily_price_symbol_count",
                "ok",
                "daily_price symbol count summary",
                table="daily_price",
                row_count=daily_price_symbol_count,
            )
        )

        for symbol in REQUIRED_INDEX_SYMBOLS:
            row_count = int(
                _query_scalar(conn, "SELECT COUNT(*) FROM market_index WHERE symbol = ?", (symbol,)) or 0
            )
            latest_date = _query_scalar(conn, "SELECT MAX(date) FROM market_index WHERE symbol = ?", (symbol,))
            target_count = int(
                _query_scalar(
                    conn,
                    "SELECT COUNT(*) FROM market_index WHERE symbol = ? AND date = ?",
                    (symbol, target_date),
                )
                or 0
            )
            if row_count == 0 or not latest_date:
                severity = "error" if symbol == "SPY" else "warning"
                checks.append(
                    _issue(
                        severity,
                        "market_index_symbol",
                        "missing",
                        f"market_index has no rows for {symbol}",
                        table="market_index",
                        symbol=symbol,
                        row_count=row_count,
                        suggestion="Refresh market index data",
                    )
                )
                continue

            if target_count == 0:
                checks.append(
                    _issue(
                        "error" if symbol == "SPY" or strict else "warning",
                        "market_index_target_coverage",
                        "missing",
                        f"market_index has no {symbol} row for target_date",
                        table="market_index",
                        symbol=symbol,
                        latest_date=latest_date,
                        row_count=target_count,
                        suggestion="Refresh or restore exact target_date index coverage",
                    )
                )
            else:
                checks.append(
                    _issue(
                        "info",
                        "market_index_symbol",
                        "ok",
                        f"market_index rows exist for {symbol}",
                        table="market_index",
                        symbol=symbol,
                        latest_date=latest_date,
                        row_count=row_count,
                    )
                )

        indicators_row_count = int(_query_scalar(conn, "SELECT COUNT(*) FROM daily_indicators") or 0)
        indicators_latest = _query_scalar(conn, "SELECT MAX(date) FROM daily_indicators")
        indicators_target_count = int(
            _query_scalar(conn, "SELECT COUNT(*) FROM daily_indicators WHERE date = ?", (target_date,)) or 0
        )
        indicators_symbol_count = int(_query_scalar(conn, "SELECT COUNT(DISTINCT symbol) FROM daily_indicators") or 0)
        if indicators_row_count == 0 or not indicators_latest:
            checks.append(
                _issue(
                    "error",
                    "daily_indicators_data",
                    "empty",
                    "daily_indicators has no data",
                    table="daily_indicators",
                    row_count=indicators_row_count,
                    suggestion="Run indicator refresh before planning",
                )
            )
        elif indicators_target_count == 0:
            checks.append(
                _issue(
                    "error",
                    "daily_indicators_target_coverage",
                    "missing",
                    "daily_indicators has no rows for target_date",
                    table="daily_indicators",
                    latest_date=indicators_latest,
                    row_count=indicators_target_count,
                    suggestion="Refresh or restore exact target_date indicator coverage",
                )
            )
        else:
            checks.append(
                _issue(
                    "info",
                    "daily_indicators_freshness",
                    "ok",
                    "daily_indicators has exact target_date coverage",
                    table="daily_indicators",
                    latest_date=indicators_latest or "",
                    row_count=indicators_row_count,
                )
            )
        checks.append(
            _issue(
                "info",
                "daily_indicators_symbol_count",
                "ok",
                "daily_indicators symbol count summary",
                table="daily_indicators",
                row_count=indicators_symbol_count,
            )
        )

        tickers_row_count = int(_query_scalar(conn, "SELECT COUNT(*) FROM tickers") or 0)
        listing_board_distribution = _query_listing_board_distribution(conn)
        if tickers_row_count == 0:
            checks.append(
                _issue(
                    "error",
                    "tickers_row_count",
                    "empty",
                    "tickers table has no rows",
                    table="tickers",
                    row_count=tickers_row_count,
                    suggestion="Refresh ticker metadata before planning",
                )
            )
        elif tickers_row_count < MIN_TICKER_COUNT:
            checks.append(
                _issue(
                    "warning",
                    "tickers_row_count",
                    "low",
                    f"tickers row count is below the conservative threshold ({MIN_TICKER_COUNT})",
                    table="tickers",
                    row_count=tickers_row_count,
                    suggestion="Verify the ticker universe and metadata refresh coverage",
                )
            )
        else:
            checks.append(
                _issue(
                    "info",
                    "tickers_row_count",
                    "ok",
                    "tickers table has sufficient rows",
                    table="tickers",
                    row_count=tickers_row_count,
                )
            )
        if listing_board_distribution:
            checks.append(
                _issue(
                    "info",
                    "tickers_listing_board_distribution",
                    "ok",
                    f"listing_board distribution: {listing_board_distribution}",
                    table="tickers",
                    row_count=tickers_row_count,
                )
            )

        checks.append(_build_universe_snapshot_check(target_date, universe_dir))

    return _apply_summary(target_date, market_db, checks)


def render_paper_data_freshness_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Paper Data Freshness Report",
        "",
        f"- Generated at: {datetime.now().isoformat(timespec='seconds')}",
        f"- Target date: `{summary['target_date']}`",
        f"- Market DB path: `{summary['market_db_path']}`",
        f"- Result: `{summary['result']}`",
        f"- Error count: `{summary['error_count']}`",
        f"- Warning count: `{summary['warning_count']}`",
        "",
        "## Checks",
        "",
        "| Severity | Check | Status | Table | Symbol | Latest Date | Row Count | Message | Suggestion |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | ---: | :--- | :--- |",
    ]
    for item in summary["checks"]:
        lines.append(
            "| {severity} | {check_name} | {status} | {table} | {symbol} | {latest_date} | {row_count} | {message} | {suggestion} |".format(
                severity=item.get("severity", ""),
                check_name=item.get("check_name", ""),
                status=item.get("status", ""),
                table=item.get("table", ""),
                symbol=item.get("symbol", ""),
                latest_date=item.get("latest_date", ""),
                row_count=item.get("row_count", ""),
                message=str(item.get("message", "")).replace("|", "/"),
                suggestion=str(item.get("suggestion", "")).replace("|", "/"),
            )
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "- This data freshness check is read-only.",
            "- It does not run market data collection, DB writes, paper daily plan generation, or EOD commit.",
            "- It only checks operational readiness for paper workflow inputs.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_markdown(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_paper_data_freshness_issues_csv(checks: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "severity",
                "check_name",
                "status",
                "message",
                "table",
                "symbol",
                "latest_date",
                "row_count",
                "suggestion",
            ],
        )
        writer.writeheader()
        for item in checks:
            writer.writerow(item)


def write_paper_data_freshness_report(summary: dict[str, Any]) -> tuple[Path, Path]:
    reports_dir = paper_reports_dir()
    markdown_path = reports_dir / FRESHNESS_REPORT_PATH_NAMES["markdown"]
    issues_path = reports_dir / FRESHNESS_REPORT_PATH_NAMES["issues"]
    write_markdown(markdown_path, render_paper_data_freshness_report(summary))
    write_paper_data_freshness_issues_csv(summary["checks"], issues_path)
    return markdown_path, issues_path
