from __future__ import annotations

from datetime import datetime

import config

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
    highest_price_meta = {}
    for symbol in current_symbols:
        meta = dict(state.highest_price_meta.get(symbol, {}))
        highest_price_meta[symbol] = {
            "updated_at": meta.get("updated_at") or normalized_date,
            "source": meta.get("source") or "paper_execution_log",
            "basis": meta.get("basis") or "trade_price",
            **meta,
        }

    hedge_tickers = {
        str(symbol).strip().upper()
        for symbol in getattr(config, "HEDGE_TICKERS", ())
        if str(symbol).strip()
    }
    hedge_symbols = [
        symbol for symbol in current_symbols if symbol.strip().upper() in hedge_tickers
    ]
    total_position_value = sum(
        position.shares * position.avg_price for position in state.positions.values()
    )
    hedge_position_value = sum(
        state.positions[symbol].shares * state.positions[symbol].avg_price
        for symbol in hedge_symbols
    )
    total_equity = float(state.cash) + float(total_position_value)
    current_cash_ratio = float(state.cash) / total_equity if total_equity > 0 else 0.0

    return {
        "current_symbols": current_symbols,
        "current_cash_ratio": current_cash_ratio,
        "current_hedge_ratio": float(hedge_position_value) / total_equity if total_equity > 0 else 0.0,
        "absolute_cash": float(state.cash),
        "shares": shares,
        "avg_price": avg_price,
        "highest_prices": highest_prices,
        "highest_price_meta": highest_price_meta,
        "hedge_symbols": hedge_symbols,
        "applied_trade_ids": sorted(state.applied_trade_ids),
    }
