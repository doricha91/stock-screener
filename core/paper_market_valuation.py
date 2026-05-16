from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.paper_account_state import PaperAccountState


@dataclass(frozen=True)
class PaperPositionValuation:
    symbol: str
    shares: int
    avg_price: float
    close_price: float
    market_value: float
    cost_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float | None
    valuation_price_date: str
    price_staleness_days: int


@dataclass(frozen=True)
class PaperAccountValuation:
    snapshot_date: str
    cash: float
    positions_cost_value: float
    positions_market_value: float
    total_equity_cost_basis: float
    total_equity_market_value: float
    cash_ratio_market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float | None
    valuation_method: str
    valuation_price_date: str
    valuation_price_dates: dict[str, str]
    price_staleness_days: dict[str, int]
    positions: list[PaperPositionValuation]


def _normalize_date(value: str) -> str:
    clean_date = value.replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid date format: {value}")
    return datetime.strptime(clean_date, "%Y%m%d").strftime("%Y-%m-%d")


def get_latest_close_on_or_before(
    conn,
    symbol: str,
    snapshot_date: str,
) -> tuple[float, str]:
    normalized_date = _normalize_date(snapshot_date)
    row = conn.execute(
        """
        SELECT close, date
        FROM daily_price
        WHERE symbol = ? AND date <= ?
        ORDER BY date DESC
        LIMIT 1
        """,
        (symbol, normalized_date),
    ).fetchone()

    if row is None:
        raise ValueError(f"No daily_price close found for {symbol} on or before {normalized_date}")

    close_price = float(row[0])
    price_date = str(row[1])
    if close_price <= 0:
        raise ValueError(f"Invalid close price for {symbol} on {price_date}: {close_price}")
    return close_price, price_date


def value_paper_account_state(
    state: PaperAccountState,
    snapshot_date: str,
    db_path: Path,
) -> PaperAccountValuation:
    normalized_date = _normalize_date(snapshot_date)
    snapshot_dt = datetime.strptime(normalized_date, "%Y-%m-%d").date()

    if not state.positions:
        total_equity_market_value = float(state.cash)
        if total_equity_market_value <= 0:
            raise ValueError("total_equity_market_value must be > 0")
        return PaperAccountValuation(
            snapshot_date=normalized_date,
            cash=float(state.cash),
            positions_cost_value=0.0,
            positions_market_value=0.0,
            total_equity_cost_basis=float(state.cash),
            total_equity_market_value=total_equity_market_value,
            cash_ratio_market_value=1.0,
            unrealized_pnl=0.0,
            unrealized_pnl_pct=None,
            valuation_method="db_daily_price_close",
            valuation_price_date=normalized_date,
            valuation_price_dates={},
            price_staleness_days={},
            positions=[],
        )

    conn = sqlite3.connect(str(db_path))
    try:
        positions: list[PaperPositionValuation] = []
        valuation_price_dates: dict[str, str] = {}
        price_staleness_days: dict[str, int] = {}

        for symbol in sorted(state.positions):
            position = state.positions[symbol]
            close_price, valuation_price_date = get_latest_close_on_or_before(
                conn,
                symbol,
                normalized_date,
            )
            valuation_dt = datetime.strptime(valuation_price_date, "%Y-%m-%d").date()
            staleness_days = (snapshot_dt - valuation_dt).days

            cost_value = position.shares * position.avg_price
            market_value = position.shares * close_price
            unrealized_pnl = market_value - cost_value
            unrealized_pnl_pct = None if cost_value == 0 else unrealized_pnl / cost_value

            positions.append(
                PaperPositionValuation(
                    symbol=symbol,
                    shares=position.shares,
                    avg_price=position.avg_price,
                    close_price=close_price,
                    market_value=market_value,
                    cost_value=cost_value,
                    unrealized_pnl=unrealized_pnl,
                    unrealized_pnl_pct=unrealized_pnl_pct,
                    valuation_price_date=valuation_price_date,
                    price_staleness_days=staleness_days,
                )
            )
            valuation_price_dates[symbol] = valuation_price_date
            price_staleness_days[symbol] = staleness_days

        positions_cost_value = sum(position.cost_value for position in positions)
        positions_market_value = sum(position.market_value for position in positions)
        total_equity_cost_basis = float(state.cash) + positions_cost_value
        total_equity_market_value = float(state.cash) + positions_market_value
        if total_equity_market_value <= 0:
            raise ValueError("total_equity_market_value must be > 0")

        unrealized_pnl = positions_market_value - positions_cost_value
        unrealized_pnl_pct = None if positions_cost_value == 0 else unrealized_pnl / positions_cost_value
        valuation_price_date = min(valuation_price_dates.values())

        return PaperAccountValuation(
            snapshot_date=normalized_date,
            cash=float(state.cash),
            positions_cost_value=positions_cost_value,
            positions_market_value=positions_market_value,
            total_equity_cost_basis=total_equity_cost_basis,
            total_equity_market_value=total_equity_market_value,
            cash_ratio_market_value=float(state.cash) / total_equity_market_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            valuation_method="db_daily_price_close",
            valuation_price_date=valuation_price_date,
            valuation_price_dates=valuation_price_dates,
            price_staleness_days=price_staleness_days,
            positions=positions,
        )
    finally:
        conn.close()
