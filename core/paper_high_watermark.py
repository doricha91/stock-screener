from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Any

from core.paper_account_state import PaperAccountState, PaperPosition


@dataclass(frozen=True)
class PaperHighWatermarkResult:
    decision_state: PaperAccountState
    updated_state: PaperAccountState
    position_open_dates: dict[str, str]
    decision_highest: dict[str, float]
    updated_highest: dict[str, float]
    max_high_dates: dict[str, str | None]
    metadata: dict[str, dict[str, Any]]
    warnings: list[dict[str, str]]


def _normalize_date(value: str) -> str:
    clean = str(value or "").replace("-", "").strip()
    if len(clean) != 8 or not clean.isdigit():
        raise ValueError(f"Invalid date format: {value}")
    return datetime.strptime(clean, "%Y%m%d").strftime("%Y-%m-%d")


def filter_execution_rows_on_or_before(
    trade_rows: list[dict],
    as_of_date: str,
) -> list[dict]:
    cutoff = _normalize_date(as_of_date)
    filtered: list[dict] = []
    for row in trade_rows:
        execution_date = _normalize_date(str(row.get("date") or ""))
        if execution_date <= cutoff:
            filtered.append(row)
    return filtered


def find_position_open_dates(
    trade_rows: list[dict],
    as_of_date: str,
) -> dict[str, str]:
    filtered = filter_execution_rows_on_or_before(trade_rows, as_of_date)
    indexed_rows = list(enumerate(filtered))
    indexed_rows.sort(key=lambda item: (_normalize_date(str(item[1].get("date") or "")), item[0]))
    quantities: dict[str, int] = {}
    open_dates: dict[str, str] = {}
    for _, row in indexed_rows:
        symbol = str(row.get("symbol") or "").strip()
        side = str(row.get("side") or "").strip().upper()
        shares = int(row.get("shares"))
        execution_date = _normalize_date(str(row.get("date") or ""))
        before = quantities.get(symbol, 0)
        if side == "BUY":
            if before == 0:
                open_dates[symbol] = execution_date
            quantities[symbol] = before + shares
        elif side == "SELL":
            after = before - abs(shares)
            if after <= 0:
                quantities.pop(symbol, None)
                open_dates.pop(symbol, None)
            else:
                quantities[symbol] = after
    return open_dates


def _market_high_rows(
    conn: sqlite3.Connection,
    symbol: str,
    open_date: str,
    as_of_date: str,
) -> list[tuple[str, float | None]]:
    rows = conn.execute(
        """
        SELECT date, high
        FROM daily_price
        WHERE symbol = ?
          AND date > ?
          AND date <= ?
        ORDER BY date
        """,
        (symbol, open_date, as_of_date),
    ).fetchall()
    normalized_rows: list[tuple[str, float | None]] = []
    for date_value, raw_high in rows:
        try:
            high = float(raw_high)
            if high <= 0 or not isfinite(high):
                high = None
        except (TypeError, ValueError):
            high = None
        normalized_rows.append((str(date_value), high))
    return normalized_rows


def _state_with_highest(
    state: PaperAccountState,
    highest: dict[str, float],
    metadata: dict[str, dict[str, Any]],
) -> PaperAccountState:
    positions = {
        symbol: replace(position, highest_price=highest[symbol])
        for symbol, position in state.positions.items()
    }
    return replace(
        state,
        positions=positions,
        highest_price_meta={symbol: dict(metadata[symbol]) for symbol in positions},
    )


def calculate_paper_high_watermarks(
    state: PaperAccountState,
    trade_rows: list[dict],
    as_of_date: str,
    db_path: str | Path,
) -> PaperHighWatermarkResult:
    cutoff = _normalize_date(as_of_date)
    open_dates = find_position_open_dates(trade_rows, cutoff)
    decision: dict[str, float] = {}
    updated: dict[str, float] = {}
    max_high_dates: dict[str, str | None] = {}
    metadata: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, str]] = []

    if not state.positions:
        return PaperHighWatermarkResult(
            decision_state=state,
            updated_state=state,
            position_open_dates={},
            decision_highest={},
            updated_highest={},
            max_high_dates={},
            metadata={},
            warnings=[],
        )

    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(f"file:{Path(db_path).resolve().as_posix()}?mode=ro", uri=True)
        for symbol in sorted(state.positions):
            position = state.positions[symbol]
            open_date = open_dates.get(symbol)
            if not open_date:
                raise ValueError(f"position_open_date_not_found:{symbol}")
            base_highest = float(position.highest_price)
            rows = _market_high_rows(conn, symbol, open_date, cutoff)
            valid_rows = [row for row in rows if row[1] is not None]
            prior_rows = [row for row in valid_rows if row[0] < cutoff]
            current_rows = [row for row in rows if row[0] == cutoff]
            current_valid_rows = [row for row in current_rows if row[1] is not None]

            prior_date, prior_high = max(prior_rows, key=lambda row: (row[1], row[0])) if prior_rows else (None, None)
            decision_value = max(base_highest, prior_high) if prior_high is not None else base_highest
            current_high = max(row[1] for row in current_valid_rows) if current_valid_rows else None
            updated_value = max(decision_value, current_high) if current_high is not None else decision_value

            market_candidates = [(date_value, high) for date_value, high in valid_rows]
            market_max_date, market_max = (
                max(market_candidates, key=lambda row: (row[1], row[0]))
                if market_candidates
                else (None, None)
            )
            market_sets_highest = market_max is not None and market_max >= base_highest
            observed_through = max((row[0] for row in valid_rows), default=None)
            meta: dict[str, Any] = {
                "updated_at": cutoff,
                "position_open_date": open_date,
                "observed_through": observed_through,
                "max_high_date": market_max_date if market_sets_highest else None,
                "decision_highest": decision_value,
                "updated_highest": updated_value,
                "current_high": current_high,
            }
            fallback_reason = None
            if cutoff != open_date and not current_rows:
                fallback_reason = "as_of_market_row_missing"
            elif cutoff != open_date and not current_valid_rows:
                fallback_reason = "as_of_high_invalid"

            if fallback_reason is not None:
                meta.update({
                    "source": "market_data_partial",
                    "basis": "position_lifecycle_max_daily_high",
                    "requested_through": cutoff,
                    "fallback_reason": fallback_reason,
                })
                warnings.append({
                    "symbol": symbol,
                    "reason": fallback_reason,
                })
            elif current_valid_rows or market_sets_highest:
                meta.update({
                    "source": "market_data",
                    "basis": "position_lifecycle_max_daily_high",
                })
            elif rows:
                meta.update({
                    "source": "paper_execution_log",
                    "basis": "trade_price",
                })
            elif cutoff == open_date:
                meta.update({
                    "source": "paper_execution_log",
                    "basis": "trade_price",
                })
            else:
                meta.update({
                    "source": "paper_execution_log",
                    "basis": "trade_price",
                })

            decision[symbol] = decision_value
            updated[symbol] = updated_value
            max_high_dates[symbol] = meta["max_high_date"]
            metadata[symbol] = meta
    except sqlite3.Error as exc:
        raise ValueError(f"paper_high_watermark_market_db_error: {exc}") from exc
    finally:
        if conn is not None:
            conn.close()

    return PaperHighWatermarkResult(
        decision_state=_state_with_highest(state, decision, metadata),
        updated_state=_state_with_highest(state, updated, metadata),
        position_open_dates=open_dates,
        decision_highest=decision,
        updated_highest=updated,
        max_high_dates=max_high_dates,
        metadata=metadata,
        warnings=warnings,
    )
