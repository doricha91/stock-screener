"""Pure policy helpers for the Paper long-position hard cap."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from core.portfolio_config import PORTFOLIO_CONFIG


DEFAULT_MAX_LONG_POSITIONS = PORTFOLIO_CONFIG["max_long_positions"]

BUY = "BUY"
SELL = "SELL"
REVIEW_EXIT = "REVIEW_EXIT"
_SUPPORTED_ACTION_TYPES = {BUY, SELL, REVIEW_EXIT}


@dataclass(frozen=True)
class LongPositionAction:
    """A normalized, generic action. BUY and SELL quantities are positive."""

    symbol: str
    action_type: str
    quantity: int


@dataclass(frozen=True)
class LongPositionPolicyResult:
    """Result of projecting ordered actions against the long-position cap."""

    allowed: bool
    is_within_cap: bool
    current_count: int
    projected_count: int
    maximum_projected_count: int
    available_slots: int
    projected_positions: tuple[tuple[str, int], ...]
    error_codes: tuple[str, ...]


def normalize_symbol(symbol: Any) -> str:
    """Return the canonical symbol form used by the policy."""

    if symbol is None:
        raise ValueError("symbol must not be None")
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol must not be empty")
    return normalized


def validate_long_position_limits(
    positions: Mapping[str, Any] | Iterable[Any],
    actions: Iterable[LongPositionAction | Mapping[str, Any]],
    *,
    max_long_positions: int = DEFAULT_MAX_LONG_POSITIONS,
    excluded_symbols: Iterable[str] = (),
) -> LongPositionPolicyResult:
    """Project ordered actions and validate the distinct-long hard cap.

    Positions may be a symbol-to-shares mapping, a symbol-to-object mapping with
    a ``shares`` attribute, or iterable rows containing ``symbol`` and ``shares``.
    Excluded symbols are intentionally outside this policy (for example, hedges).
    Invalid input returns a fail-closed result rather than changing any state.
    """

    try:
        if not _is_positive_int(max_long_positions):
            raise ValueError("max_long_positions must be a positive integer")
        excluded = {normalize_symbol(symbol) for symbol in excluded_symbols}
        long_positions = _normalize_open_positions(positions, excluded)
    except (KeyError, TypeError, ValueError, AttributeError):
        return _invalid_result("invalid_position_input")

    current_count = len(long_positions)
    projected = dict(long_positions)
    maximum_projected_count = current_count
    errors: list[str] = []

    try:
        action_rows = iter(actions)
    except TypeError:
        return LongPositionPolicyResult(
            allowed=False,
            is_within_cap=current_count <= max_long_positions,
            current_count=current_count,
            projected_count=current_count,
            maximum_projected_count=current_count,
            available_slots=max(0, max_long_positions - current_count),
            projected_positions=tuple(sorted(projected.items())),
            error_codes=("invalid_action_input",),
        )

    for raw_action in action_rows:
        try:
            action = _normalize_action(raw_action)
        except (KeyError, TypeError, ValueError, AttributeError):
            _add_error(errors, "invalid_action_input")
            continue

        if action.symbol in excluded:
            continue

        if action.action_type == REVIEW_EXIT:
            continue

        held_shares = projected.get(action.symbol, 0)
        if action.action_type == BUY:
            if current_count > max_long_positions:
                _add_error(errors, "buy_blocked_while_over_cap")
                continue
            projected[action.symbol] = held_shares + action.quantity
            maximum_projected_count = max(maximum_projected_count, len(projected))
            if len(projected) > max_long_positions:
                _add_error(errors, "max_long_positions_exceeded")
            continue

        if held_shares < action.quantity:
            _add_error(errors, "sell_quantity_exceeds_held")
            continue
        if held_shares == action.quantity:
            projected.pop(action.symbol)
        else:
            projected[action.symbol] = held_shares - action.quantity
        maximum_projected_count = max(maximum_projected_count, len(projected))

    projected_count = len(projected)
    return LongPositionPolicyResult(
        allowed=not errors,
        is_within_cap=projected_count <= max_long_positions,
        current_count=current_count,
        projected_count=projected_count,
        maximum_projected_count=maximum_projected_count,
        available_slots=max(0, max_long_positions - projected_count),
        projected_positions=tuple(sorted(projected.items())),
        error_codes=tuple(errors),
    )


def _normalize_open_positions(
    positions: Mapping[str, Any] | Iterable[Any],
    excluded_symbols: set[str],
) -> dict[str, int]:
    if isinstance(positions, Mapping):
        rows = ((symbol, value) for symbol, value in positions.items())
    else:
        rows = (_position_row_to_pair(row) for row in positions)

    normalized: dict[str, int] = {}
    for symbol, value in rows:
        normalized_symbol = normalize_symbol(symbol)
        shares = _extract_shares(value)
        if shares < 0:
            raise ValueError("position shares must not be negative")
        if shares == 0 or normalized_symbol in excluded_symbols:
            continue
        normalized[normalized_symbol] = normalized.get(normalized_symbol, 0) + shares
    return normalized


def _position_row_to_pair(row: Any) -> tuple[Any, Any]:
    if isinstance(row, Mapping):
        return row["symbol"], row["shares"]
    return row.symbol, row.shares


def _extract_shares(value: Any) -> int:
    if isinstance(value, Mapping):
        value = value["shares"]
    elif hasattr(value, "shares"):
        value = value.shares
    if not _is_nonnegative_int(value):
        raise ValueError("position shares must be a non-negative integer")
    return value


def _normalize_action(raw_action: LongPositionAction | Mapping[str, Any]) -> LongPositionAction:
    if isinstance(raw_action, LongPositionAction):
        symbol = raw_action.symbol
        action_type = raw_action.action_type
        quantity = raw_action.quantity
    elif isinstance(raw_action, Mapping):
        symbol = raw_action["symbol"]
        action_type = raw_action["action_type"]
        quantity = raw_action["quantity"]
    else:
        raise ValueError("action must be a LongPositionAction or mapping")

    normalized_type = str(action_type).strip().upper()
    if normalized_type not in _SUPPORTED_ACTION_TYPES:
        raise ValueError("unsupported action type")
    if not _is_positive_int(quantity):
        raise ValueError("action quantity must be a positive integer")
    return LongPositionAction(
        symbol=normalize_symbol(symbol),
        action_type=normalized_type,
        quantity=quantity,
    )


def _is_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _add_error(errors: list[str], error_code: str) -> None:
    if error_code not in errors:
        errors.append(error_code)


def _invalid_result(error_code: str) -> LongPositionPolicyResult:
    return LongPositionPolicyResult(
        allowed=False,
        is_within_cap=False,
        current_count=0,
        projected_count=0,
        maximum_projected_count=0,
        available_slots=0,
        projected_positions=(),
        error_codes=(error_code,),
    )
