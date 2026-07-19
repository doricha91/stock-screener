"""Manual Execution adapters for the shared Paper long-position policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

import config

from core.long_position_policy import (
    BUY,
    DEFAULT_MAX_LONG_POSITIONS,
    LongPositionAction,
    LongPositionPolicyResult,
    normalize_symbol,
    validate_long_position_limits,
)


NORMAL = "NORMAL"
OVER_CAP_RECOVERY = "OVER_CAP_RECOVERY"


def get_configured_manual_execution_hedge_symbols() -> frozenset[str]:
    """Return normalized hedge symbols from config.HEDGE_TICKERS."""

    return frozenset(
        normalize_symbol(symbol)
        for symbol in getattr(config, "HEDGE_TICKERS", ())
    )


@dataclass(frozen=True)
class ManualExecutionLongPositionValidation:
    """Immutable validation result; this adapter never edits the action batch."""

    allowed: bool
    mode: str
    max_long_positions: int
    policy: LongPositionPolicyResult
    error_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "mode": self.mode,
            "current_count": self.policy.current_count,
            "projected_count": self.policy.projected_count,
            "maximum_projected_count": self.policy.maximum_projected_count,
            "max_long_positions": self.max_long_positions,
            "is_within_cap": self.policy.is_within_cap,
            "policy_allowed": self.policy.allowed,
            "error_codes": list(self.error_codes),
            "projected_positions": [list(item) for item in self.policy.projected_positions],
        }


def validate_manual_execution_long_position_actions(
    positions: Mapping[str, Any] | Iterable[Any],
    actions: Iterable[LongPositionAction | Mapping[str, Any]],
    *,
    max_long_positions: int = DEFAULT_MAX_LONG_POSITIONS,
    hedge_symbols: Iterable[str] = (),
) -> ManualExecutionLongPositionValidation:
    """Validate an ordered Preview/Commit batch with the shared hard-cap policy."""

    ordered_actions = tuple(actions)
    try:
        materialized_hedge_symbols = tuple(hedge_symbols)
    except TypeError:
        materialized_hedge_symbols = (None,)
    policy = validate_long_position_limits(
        positions,
        ordered_actions,
        max_long_positions=max_long_positions,
        excluded_symbols=materialized_hedge_symbols,
    )
    mode = OVER_CAP_RECOVERY if policy.current_count > max_long_positions else NORMAL
    error_codes = list(policy.error_codes)

    if mode == NORMAL:
        allowed = (
            policy.allowed
            and policy.projected_count <= max_long_positions
            and policy.is_within_cap
        )
        if not allowed and not error_codes:
            error_codes.append("normal_long_position_cap_validation_failed")
    else:
        try:
            normalized_hedge_symbols = {
                normalize_symbol(symbol) for symbol in materialized_hedge_symbols
            }
        except (TypeError, ValueError):
            normalized_hedge_symbols = set()
        has_non_hedge_buy = any(
            _is_non_hedge_buy(action, normalized_hedge_symbols)
            for action in ordered_actions
        )
        allowed = (
            not has_non_hedge_buy
            and policy.allowed
            and policy.projected_count <= policy.current_count
        )
        if has_non_hedge_buy and "buy_blocked_while_over_cap" not in error_codes:
            error_codes.append("buy_blocked_while_over_cap")
        if not allowed and not error_codes:
            error_codes.append("over_cap_recovery_validation_failed")

    return ManualExecutionLongPositionValidation(
        allowed=allowed,
        mode=mode,
        max_long_positions=max_long_positions,
        policy=policy,
        error_codes=tuple(error_codes),
    )


def _is_non_hedge_buy(
    action: LongPositionAction | Mapping[str, Any],
    normalized_hedge_symbols: set[str],
) -> bool:
    try:
        if isinstance(action, Mapping):
            action_type = action["action_type"]
            symbol = action["symbol"]
        else:
            action_type = action.action_type
            symbol = action.symbol
        return (
            str(action_type).strip().upper() == BUY
            and normalize_symbol(symbol) not in normalized_hedge_symbols
        )
    except (AttributeError, KeyError, TypeError, ValueError):
        return False
