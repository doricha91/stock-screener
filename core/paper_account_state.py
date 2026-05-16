from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PaperPosition:
    symbol: str
    shares: int
    avg_price: float
    highest_price: float


@dataclass(frozen=True)
class PaperAccountState:
    cash: float
    currency: str
    positions: dict[str, PaperPosition]
    applied_trade_ids: set[str]
    realized_pnl: float = 0.0
    realized_pnl_by_symbol: dict[str, float] = field(default_factory=dict)


def create_initial_paper_state(
    initial_cash: float = 100000.0,
    currency: str = "USD",
) -> PaperAccountState:
    return PaperAccountState(
        cash=float(initial_cash),
        currency=currency,
        positions={},
        applied_trade_ids=set(),
        realized_pnl=0.0,
        realized_pnl_by_symbol={},
    )


def apply_paper_trade(
    state: PaperAccountState,
    trade_row: dict,
) -> PaperAccountState:
    trade_id = str(trade_row.get("trade_id", "")).strip()
    symbol = str(trade_row.get("symbol", "")).strip()
    side = str(trade_row.get("side", "")).strip().upper()

    if not trade_id:
        raise ValueError("trade_id is required")
    if not symbol:
        raise ValueError("symbol is required")

    if trade_id in state.applied_trade_ids:
        return state

    if side not in {"BUY", "SELL"}:
        raise ValueError(f"unsupported side: {side}")

    try:
        shares = int(trade_row.get("shares"))
    except Exception as exc:
        raise ValueError("shares must be an integer") from exc

    try:
        price = float(trade_row.get("price"))
    except Exception as exc:
        raise ValueError("price must be numeric") from exc

    if price <= 0:
        raise ValueError("price must be > 0")
    if shares == 0:
        raise ValueError("shares must not be 0")
    if side == "BUY" and shares < 0:
        raise ValueError("BUY shares must be > 0")
    if side == "SELL" and shares > 0:
        raise ValueError("SELL shares must be < 0")

    new_cash = float(state.cash)
    new_positions = dict(state.positions)
    new_applied_trade_ids = set(state.applied_trade_ids)
    new_realized_pnl = float(state.realized_pnl)
    new_realized_pnl_by_symbol = dict(state.realized_pnl_by_symbol)

    if side == "BUY":
        cost = shares * price
        if new_cash < cost:
            raise ValueError("insufficient cash for BUY")

        existing = new_positions.get(symbol)
        if existing is None:
            new_positions[symbol] = PaperPosition(
                symbol=symbol,
                shares=shares,
                avg_price=price,
                highest_price=price,
            )
        else:
            new_total_shares = existing.shares + shares
            new_avg_price = ((existing.shares * existing.avg_price) + (shares * price)) / new_total_shares
            new_positions[symbol] = PaperPosition(
                symbol=symbol,
                shares=new_total_shares,
                avg_price=new_avg_price,
                highest_price=max(existing.highest_price, price),
            )
        new_cash -= cost
    else:
        sell_quantity = abs(shares)
        existing = new_positions.get(symbol)
        if existing is None or existing.shares < sell_quantity:
            raise ValueError("cannot SELL more shares than held")

        realized_pnl_delta = (price - existing.avg_price) * sell_quantity
        new_realized_pnl += realized_pnl_delta
        new_realized_pnl_by_symbol[symbol] = (
            new_realized_pnl_by_symbol.get(symbol, 0.0) + realized_pnl_delta
        )
        new_cash += sell_quantity * price
        remaining_shares = existing.shares - sell_quantity
        if remaining_shares == 0:
            new_positions.pop(symbol, None)
        else:
            new_positions[symbol] = PaperPosition(
                symbol=symbol,
                shares=remaining_shares,
                avg_price=existing.avg_price,
                highest_price=existing.highest_price,
            )

    new_applied_trade_ids.add(trade_id)
    return PaperAccountState(
        cash=new_cash,
        currency=state.currency,
        positions=new_positions,
        applied_trade_ids=new_applied_trade_ids,
        realized_pnl=new_realized_pnl,
        realized_pnl_by_symbol=new_realized_pnl_by_symbol,
    )


def build_paper_state_from_trades(
    trade_rows: list[dict],
    initial_cash: float = 100000.0,
    currency: str = "USD",
) -> PaperAccountState:
    state = create_initial_paper_state(initial_cash=initial_cash, currency=currency)
    for trade_row in trade_rows:
        state = apply_paper_trade(state, trade_row)
    return state
