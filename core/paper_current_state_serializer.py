from __future__ import annotations

from datetime import datetime

from core.paper_account_state import PaperAccountState


def _normalize_state_date(state_date: str) -> str:
    clean_date = state_date.replace("-", "").strip()
    if len(clean_date) != 8 or not clean_date.isdigit():
        raise ValueError(f"Invalid state_date format: {state_date}")
    return datetime.strptime(clean_date, "%Y%m%d").strftime("%Y-%m-%d")


def paper_account_state_to_current_state_dict(
    state: PaperAccountState,
    state_date: str,
) -> dict:
    normalized_date = _normalize_state_date(state_date)

    current_symbols = sorted(state.positions.keys())
    shares = {symbol: position.shares for symbol, position in state.positions.items()}
    avg_price = {symbol: position.avg_price for symbol, position in state.positions.items()}
    highest_prices = {
        symbol: position.highest_price for symbol, position in state.positions.items()
    }
    highest_price_meta = {
        symbol: {
            "updated_at": normalized_date,
            "source": "paper_execution_log",
            "basis": "trade_price",
        }
        for symbol in current_symbols
    }

    total_position_value = sum(
        position.shares * position.avg_price for position in state.positions.values()
    )
    total_equity = float(state.cash) + float(total_position_value)
    current_cash_ratio = float(state.cash) / total_equity if total_equity > 0 else 0.0

    return {
        "current_symbols": current_symbols,
        "current_cash_ratio": current_cash_ratio,
        "current_hedge_ratio": 0.0,
        "absolute_cash": float(state.cash),
        "shares": shares,
        "avg_price": avg_price,
        "highest_prices": highest_prices,
        "highest_price_meta": highest_price_meta,
        "hedge_symbols": [],
        "applied_trade_ids": sorted(state.applied_trade_ids),
    }
