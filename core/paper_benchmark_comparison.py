from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from core.paper_account_paths import PaperAccountPaths
from core.paper_account_snapshot import PAPER_ACCOUNT_SNAPSHOT_COLUMNS
from core.paper_snapshot_identity import validate_snapshot_account_identity
from core.paths import market_db_path, paper_account_snapshot_path, paper_reports_dir

SCHEMA_VERSION = "paper_benchmark_comparison.v1"
BENCHMARK_MARKDOWN = "paper_benchmark_comparison.md"
BENCHMARK_JSON = "paper_benchmark_comparison.json"
BENCHMARK_SYMBOLS = ("SPY", "QQQ", "CASH")
LIMITATIONS = [
    "This benchmark is computed from existing exploratory paper snapshots.",
    "It should not be interpreted as official since-inception performance until clean reset/archive is completed.",
]


def _read_csv_rows(path: Path) -> tuple[list[dict[str, str]], list[str] | None]:
    if not path.exists():
        return [], None
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str]] = []
        for row in reader:
            normalized: dict[str, str] = {}
            for key, value in row.items():
                normalized[(key or "").replace("\ufeff", "").strip()] = value or ""
            rows.append(normalized)
        return rows, reader.fieldnames


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


def _normalize_date(value: str) -> str:
    clean = str(value).strip().replace("-", "")
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"Invalid date format: {value}")
    return f"{clean[:4]}-{clean[4:6]}-{clean[6:]}"


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _relative_to_project(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _resolve_equity_row(row: dict[str, str]) -> tuple[float | None, str]:
    market_value = _safe_float(row.get("total_equity_market_value"))
    if market_value is not None:
        return market_value, "total_equity_market_value"
    cost_basis = _safe_float(row.get("total_equity_cost_basis"))
    if cost_basis is not None:
        return cost_basis, "total_equity_cost_basis"
    return None, "unavailable"


def _compute_max_drawdown(series: list[float]) -> float | None:
    if not series:
        return None
    peak = series[0]
    max_drawdown = 0.0
    for value in series:
        peak = max(peak, value)
        if peak == 0:
            continue
        drawdown = value / peak - 1.0
        max_drawdown = min(max_drawdown, drawdown)
    return max_drawdown


def _load_market_index_history(db_path: Path, symbol: str) -> list[dict[str, Any]]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT date, adj_close, close
            FROM market_index
            WHERE symbol = ?
            ORDER BY date ASC
            """,
            (symbol,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()

    history: list[dict[str, Any]] = []
    for date, adj_close, close in rows:
        price = adj_close if adj_close is not None else close
        price_source = "adj_close" if adj_close is not None else "close"
        if price is None:
            continue
        history.append(
            {
                "date": str(date),
                "price": float(price),
                "price_source": price_source,
            }
        )
    return history


def _resolve_price_for_date(history: list[dict[str, Any]], snapshot_date: str) -> dict[str, Any] | None:
    candidate: dict[str, Any] | None = None
    for item in history:
        if item["date"] <= snapshot_date:
            candidate = item
        else:
            break
    if candidate is None:
        return None
    price_date = candidate["date"]
    staleness_days = (datetime.fromisoformat(snapshot_date) - datetime.fromisoformat(price_date)).days
    return {
        "price": candidate["price"],
        "price_date": price_date,
        "staleness_days": staleness_days,
        "used_fallback_price": price_date != snapshot_date,
        "price_source": candidate["price_source"],
    }


def build_paper_benchmark_comparison_summary(
    *,
    paper_root: Path | None = None,
    market_db: Path | None = None,
    account_paths: PaperAccountPaths | None = None,
) -> dict[str, Any]:
    root = account_paths.root if account_paths is not None else (Path(paper_root) if paper_root is not None else paper_account_snapshot_path().parent)
    account_path = root / paper_account_snapshot_path().name
    db_path = Path(market_db) if market_db is not None else Path(market_db_path())

    expected_account_id = account_paths.account_id if account_paths is not None else "paper_default"
    account_rows, account_fieldnames = _read_csv_rows(account_path)
    account_rows, _ = validate_snapshot_account_identity(
        account_rows,
        fieldnames=account_fieldnames,
        allowed_fieldnames=PAPER_ACCOUNT_SNAPSHOT_COLUMNS,
        expected_account_id=expected_account_id,
        source_path=account_path,
        account_root=root,
    )
    account_rows = [row for row in account_rows if row.get("snapshot_date")]
    account_rows.sort(key=lambda row: row["snapshot_date"])

    valid_rows: list[dict[str, Any]] = []
    for row in account_rows:
        equity, valuation_basis = _resolve_equity_row(row)
        initial_cash = _safe_float(row.get("initial_cash"))
        if equity is None or initial_cash is None:
            continue
        valid_rows.append(
            {
                "snapshot_date": row["snapshot_date"],
                "initial_cash": initial_cash,
                "paper_equity": equity,
                "valuation_basis": valuation_basis,
                "valuation_status": row.get("market_valuation_status") or "",
                "valuation_price_date": row.get("valuation_price_date") or "",
            }
        )

    if len(valid_rows) < 2:
        return {
            "account_id": expected_account_id,
            "account_root": str(root),
            "legacy_default_used": bool(account_paths.legacy_default_used) if account_paths is not None else False,
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "run_mode": "exploratory",
            "official_run": False,
            "comparison_mode": "since_inception",
            "starting_capital_source": "paper_account_snapshot.initial_cash",
            "initial_cash": valid_rows[0]["initial_cash"] if valid_rows else None,
            "official_start_date": None,
            "start_date_source": "earliest_available_snapshot",
            "latest_snapshot_date": valid_rows[-1]["snapshot_date"] if valid_rows else None,
            "availability_status": "INSUFFICIENT_DATA",
            "benchmarks": list(BENCHMARK_SYMBOLS),
            "paper_series": [],
            "benchmark_series": {},
            "summary": {"status": "INSUFFICIENT_DATA"},
            "source_files": {
                "account_snapshot": {
                    "path": _relative_to_project(account_path),
                    "exists": account_path.exists(),
                    "row_count": len(account_rows),
                },
                "market_db": {
                    "path": _relative_to_project(db_path),
                    "exists": db_path.exists(),
                },
            },
            "limitations": LIMITATIONS,
        }

    initial_cash = valid_rows[0]["initial_cash"]
    paper_series: list[dict[str, Any]] = []
    for row in valid_rows:
        paper_return = row["paper_equity"] / initial_cash - 1.0
        paper_series.append(
            {
                "date": row["snapshot_date"],
                "paper_equity": row["paper_equity"],
                "paper_return_from_initial_cash": paper_return,
                "valuation_basis": row["valuation_basis"],
                "valuation_status": row["valuation_status"],
                "valuation_price_date": row["valuation_price_date"] or None,
            }
        )

    benchmark_series: dict[str, list[dict[str, Any]]] = {}
    benchmark_summaries: dict[str, dict[str, Any]] = {}
    benchmark_sources: dict[str, Any] = {}

    for symbol in ("SPY", "QQQ"):
        history = _load_market_index_history(db_path, symbol) if db_path.exists() else []
        series: list[dict[str, Any]] = []
        start_anchor = _resolve_price_for_date(history, paper_series[0]["date"])

        if start_anchor is None:
            benchmark_series[symbol] = []
            benchmark_summaries[symbol] = {
                "symbol": symbol,
                "availability_status": "UNAVAILABLE",
                "message": "Start benchmark price could not be resolved.",
            }
            benchmark_sources[symbol] = {
                "path": _relative_to_project(db_path),
                "table": "market_index",
                "price_column_priority": ["adj_close", "close"],
                "resolved_price_column": None,
            }
            continue

        start_price = start_anchor["price"]
        price_columns_used = {start_anchor["price_source"]}

        for row in paper_series:
            resolved = _resolve_price_for_date(history, row["date"])
            if resolved is None:
                continue
            price_columns_used.add(resolved["price_source"])
            equity = initial_cash * resolved["price"] / start_price
            benchmark_return = equity / initial_cash - 1.0
            series.append(
                {
                    "date": row["date"],
                    "symbol": symbol,
                    "price": resolved["price"],
                    "price_date": resolved["price_date"],
                    "staleness_days": resolved["staleness_days"],
                    "used_fallback_price": resolved["used_fallback_price"],
                    "benchmark_equity": equity,
                    "benchmark_return": benchmark_return,
                }
            )

        benchmark_series[symbol] = series
        benchmark_sources[symbol] = {
            "path": _relative_to_project(db_path),
            "table": "market_index",
            "price_column_priority": ["adj_close", "close"],
            "resolved_price_column": "adj_close" if "adj_close" in price_columns_used else "close",
        }

        if not series:
            benchmark_summaries[symbol] = {
                "symbol": symbol,
                "availability_status": "UNAVAILABLE",
                "message": "No benchmark series rows were produced.",
            }
            continue

        paper_return = paper_series[-1]["paper_return_from_initial_cash"]
        benchmark_return = series[-1]["benchmark_return"]
        benchmark_summaries[symbol] = {
            "symbol": symbol,
            "availability_status": "AVAILABLE",
            "benchmark_start_equity": initial_cash,
            "benchmark_end_equity": series[-1]["benchmark_equity"],
            "benchmark_return": benchmark_return,
            "benchmark_max_drawdown": _compute_max_drawdown([item["benchmark_equity"] for item in series]),
            "excess_return": paper_return - benchmark_return,
            "latest_gap": paper_series[-1]["paper_equity"] - series[-1]["benchmark_equity"],
            "start_price_date": series[0]["price_date"],
            "end_price_date": series[-1]["price_date"],
        }

    cash_series: list[dict[str, Any]] = []
    for row in paper_series:
        cash_series.append(
            {
                "date": row["date"],
                "symbol": "CASH",
                "price": 1.0,
                "price_date": row["date"],
                "staleness_days": 0,
                "used_fallback_price": False,
                "benchmark_equity": initial_cash,
                "benchmark_return": 0.0,
            }
        )
    benchmark_series["CASH"] = cash_series
    benchmark_summaries["CASH"] = {
        "symbol": "CASH",
        "availability_status": "AVAILABLE",
        "benchmark_start_equity": initial_cash,
        "benchmark_end_equity": initial_cash,
        "benchmark_return": 0.0,
        "benchmark_max_drawdown": 0.0,
        "excess_return": paper_series[-1]["paper_return_from_initial_cash"],
        "latest_gap": paper_series[-1]["paper_equity"] - initial_cash,
        "start_price_date": paper_series[0]["date"],
        "end_price_date": paper_series[-1]["date"],
    }
    benchmark_sources["CASH"] = {
        "path": None,
        "table": None,
        "price_column_priority": [],
        "resolved_price_column": None,
        "synthetic": True,
    }

    summary = {
        "paper": {
            "paper_start_equity": paper_series[0]["paper_equity"],
            "paper_end_equity": paper_series[-1]["paper_equity"],
            "paper_return": paper_series[-1]["paper_return_from_initial_cash"],
            "paper_max_drawdown": _compute_max_drawdown([item["paper_equity"] for item in paper_series]),
            "valuation_basis": paper_series[-1]["valuation_basis"],
        },
        "benchmarks": benchmark_summaries,
    }

    return {
        "account_id": expected_account_id,
        "account_root": str(root),
        "legacy_default_used": bool(account_paths.legacy_default_used) if account_paths is not None else False,
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_mode": "exploratory",
        "official_run": False,
        "comparison_mode": "since_inception",
        "starting_capital_source": "paper_account_snapshot.initial_cash",
        "initial_cash": initial_cash,
        "official_start_date": None,
        "start_date_source": "earliest_available_snapshot",
        "latest_snapshot_date": paper_series[-1]["date"],
        "availability_status": "AVAILABLE",
        "benchmarks": list(BENCHMARK_SYMBOLS),
        "paper_series": paper_series,
        "benchmark_series": benchmark_series,
        "summary": summary,
        "source_files": {
            "account_snapshot": {
                "path": _relative_to_project(account_path),
                "exists": account_path.exists(),
                "row_count": len(account_rows),
                "latest_snapshot_date": paper_series[-1]["date"],
            },
            "market_db": {
                "path": _relative_to_project(db_path),
                "exists": db_path.exists(),
                "benchmark_sources": benchmark_sources,
            },
        },
        "limitations": LIMITATIONS,
    }


def render_paper_benchmark_comparison_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Paper Benchmark Comparison",
        "",
        "> Exploratory / unofficial benchmark comparison from existing paper snapshots.",
        "",
        "## 1. Status",
        "",
        f"- Schema version: {summary['schema_version']}",
        f"- Run mode: {summary['run_mode']}",
        f"- Official run: {summary['official_run']}",
        f"- Comparison mode: {summary['comparison_mode']}",
        f"- Availability status: {summary['availability_status']}",
        f"- Latest snapshot date: {summary['latest_snapshot_date']}",
        "",
        "## 2. Data Sources",
        "",
        f"- Starting capital source: {summary['starting_capital_source']}",
        f"- Initial cash: ${summary['initial_cash']:.2f}" if summary["initial_cash"] is not None else "- Initial cash: unavailable",
        f"- Account snapshot: {summary['source_files']['account_snapshot']['path']}",
        f"- Market DB: {summary['source_files']['market_db']['path']}",
        "",
        "## 3. Paper Summary",
        "",
    ]

    paper = summary["summary"].get("paper", {})
    if paper:
        lines.extend(
            [
                f"- Start equity: ${paper['paper_start_equity']:.2f}",
                f"- End equity: ${paper['paper_end_equity']:.2f}",
                f"- Return: {paper['paper_return']:.4%}",
                f"- Max drawdown: {paper['paper_max_drawdown']:.4%}" if paper.get("paper_max_drawdown") is not None else "- Max drawdown: unavailable",
                f"- Valuation basis: {paper['valuation_basis']}",
            ]
        )
    else:
        lines.append("- Insufficient paper snapshot data.")

    lines.extend(
        [
            "",
            "## 4. Benchmark Summary",
            "",
        ]
    )

    for symbol in summary["benchmarks"]:
        item = summary["summary"].get("benchmarks", {}).get(symbol, {})
        lines.append(f"### {symbol}")
        if item.get("availability_status") != "AVAILABLE":
            lines.append(f"- Availability: {item.get('availability_status', 'UNAVAILABLE')}")
            lines.append(f"- Message: {item.get('message', 'unavailable')}")
        else:
            lines.extend(
                [
                    f"- End equity: ${item['benchmark_end_equity']:.2f}",
                    f"- Return: {item['benchmark_return']:.4%}",
                    f"- Max drawdown: {item['benchmark_max_drawdown']:.4%}",
                    f"- Excess return vs paper: {item['excess_return']:.4%}",
                    f"- Latest gap: ${item['latest_gap']:.2f}",
                ]
            )
        lines.append("")

    lines.extend(
        [
            "## 5. Paper vs Benchmark Table",
            "",
            "| Benchmark | Availability | End Equity | Return | Excess Return | Latest Gap |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for symbol in summary["benchmarks"]:
        item = summary["summary"].get("benchmarks", {}).get(symbol, {})
        if item.get("availability_status") == "AVAILABLE":
            lines.append(
                f"| {symbol} | AVAILABLE | ${item['benchmark_end_equity']:.2f} | {item['benchmark_return']:.4%} | {item['excess_return']:.4%} | ${item['latest_gap']:.2f} |"
            )
        else:
            lines.append(f"| {symbol} | {item.get('availability_status', 'UNAVAILABLE')} | - | - | - | - |")

    lines.extend(
        [
            "",
            "## 6. Latest Gap",
            "",
        ]
    )
    for symbol in summary["benchmarks"]:
        item = summary["summary"].get("benchmarks", {}).get(symbol, {})
        if item.get("availability_status") == "AVAILABLE":
            lines.append(f"- {symbol}: ${item['latest_gap']:.2f}")
        else:
            lines.append(f"- {symbol}: unavailable")

    lines.extend(
        [
            "",
            "## 7. Limitations",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in summary["limitations"]])
    return "\n".join(lines) + "\n"


def generate_paper_benchmark_comparison(
    *,
    paper_root: Path | None = None,
    market_db: Path | None = None,
    account_paths: PaperAccountPaths | None = None,
) -> dict[str, Any]:
    root = account_paths.root if account_paths is not None else (Path(paper_root) if paper_root is not None else paper_account_snapshot_path().parent)
    summary = build_paper_benchmark_comparison_summary(
        paper_root=root,
        market_db=market_db,
        account_paths=account_paths,
    )
    reports_dir = root / "reports" if paper_root is not None else paper_reports_dir()
    if account_paths is not None:
        reports_dir = root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    markdown_path = reports_dir / BENCHMARK_MARKDOWN
    json_path = reports_dir / BENCHMARK_JSON
    _write_text(markdown_path, render_paper_benchmark_comparison_markdown(summary))
    _write_text(json_path, json.dumps(summary, ensure_ascii=False, indent=2))
    return {
        "markdown_path": markdown_path,
        "json_path": json_path,
        "summary": summary,
    }
