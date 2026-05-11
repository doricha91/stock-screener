from __future__ import annotations


def calculate_entry_shares(
    total_equity: float,
    available_buying_power: float,
    price: float,
    max_positions: int,
) -> int:
    """
    Calculate shares for a normal new BUY entry.

    This intentionally mirrors the existing backtest logic:

        target_position_value = total_equity / max_positions
        allocation = min(target_position_value, available_buying_power)
        shares = int(allocation / price)

    Non-goals:
    - no ATR risk sizing
    - no target_long_slots sizing
    - no commission/slippage
    - no switching-specific logic
    """
    if total_equity <= 0:
        return 0
    if available_buying_power <= 0:
        return 0
    if price <= 0:
        return 0
    if max_positions <= 0:
        return 0

    target_position_value = total_equity / max_positions
    allocation = min(target_position_value, available_buying_power)
    shares = int(allocation / price)

    return max(0, shares)
