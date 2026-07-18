from core.long_position_policy import LongPositionAction, validate_long_position_limits
from core.param_grid import params_grid
from core.portfolio_config import PORTFOLIO_CONFIG


def positions(count: int, shares: int = 10) -> dict[str, int]:
    return {f"L{index:02d}": shares for index in range(count)}


def action(symbol: str, action_type: str, quantity: int) -> LongPositionAction:
    return LongPositionAction(symbol=symbol, action_type=action_type, quantity=quantity)


def test_hard_cap_configuration_is_fixed_and_not_in_optimizer_grid():
    assert PORTFOLIO_CONFIG["max_long_positions"] == 10
    assert "max_long_positions" not in params_grid


def test_new_buy_fills_ninth_position_to_hard_cap():
    result = validate_long_position_limits(positions(9), [action("NEW", "BUY", 1)])
    assert result.allowed is True
    assert result.projected_count == 10
    assert result.maximum_projected_count == 10
    assert result.available_slots == 0


def test_new_buy_at_hard_cap_is_blocked():
    result = validate_long_position_limits(positions(10), [action("NEW", "BUY", 1)])
    assert result.allowed is False
    assert result.error_codes == ("max_long_positions_exceeded",)
    assert result.projected_count == 11


def test_additional_buy_of_existing_position_does_not_change_distinct_count():
    result = validate_long_position_limits(positions(10), [action("L00", "BUY", 2)])
    assert result.allowed is True
    assert result.projected_count == 10
    assert dict(result.projected_positions)["L00"] == 12


def test_full_sell_then_new_buy_is_allowed_at_hard_cap():
    result = validate_long_position_limits(
        positions(10),
        [action("L00", "SELL", 10), action("NEW", "BUY", 1)],
    )
    assert result.allowed is True
    assert result.projected_count == 10
    assert result.maximum_projected_count == 10
    assert result.available_slots == 0


def test_partial_sell_does_not_free_a_position_slot():
    result = validate_long_position_limits(
        positions(10),
        [action("L00", "SELL", 1), action("NEW", "BUY", 1)],
    )
    assert result.allowed is False
    assert result.error_codes == ("max_long_positions_exceeded",)
    assert result.maximum_projected_count == 11


def test_review_exit_does_not_free_a_position_slot():
    result = validate_long_position_limits(
        positions(10),
        [action("L00", "REVIEW_EXIT", 10), action("NEW", "BUY", 1)],
    )
    assert result.allowed is False
    assert result.error_codes == ("max_long_positions_exceeded",)


def test_buy_before_full_sell_is_blocked_for_intermediate_hard_cap_breach():
    result = validate_long_position_limits(
        positions(10),
        [action("NEW", "BUY", 1), action("L00", "SELL", 10)],
    )
    assert result.allowed is False
    assert result.projected_count == 10
    assert result.maximum_projected_count == 11


def test_buy_is_blocked_while_starting_over_cap_including_existing_position_buy():
    new_buy = validate_long_position_limits(positions(11), [action("NEW", "BUY", 1)])
    existing_buy = validate_long_position_limits(positions(11), [action("L00", "BUY", 1)])
    assert new_buy.error_codes == ("buy_blocked_while_over_cap",)
    assert existing_buy.error_codes == ("buy_blocked_while_over_cap",)
    assert new_buy.projected_count == existing_buy.projected_count == 11


def test_full_sell_recovery_is_allowed_even_if_final_count_remains_over_cap():
    recovered = validate_long_position_limits(positions(11), [action("L00", "SELL", 10)])
    partial_recovery = validate_long_position_limits(positions(12), [action("L00", "SELL", 10)])
    assert recovered.allowed is True
    assert recovered.is_within_cap is True
    assert recovered.projected_count == 10
    assert partial_recovery.allowed is True
    assert partial_recovery.is_within_cap is False
    assert partial_recovery.projected_count == 11


def test_zero_shares_and_excluded_hedge_symbols_are_not_long_positions():
    holdings = {" zero ": 0, " hedge ": 10, "long": 10}
    result = validate_long_position_limits(
        holdings,
        [action(" LONG ", "BUY", 2), action("hedge", "BUY", 1)],
        excluded_symbols=[" HEDGE "],
    )
    assert result.allowed is True
    assert result.current_count == 1
    assert result.projected_count == 1
    assert result.available_slots == 9
    assert result.projected_positions == (("LONG", 12),)


def test_symbols_are_normalized_before_position_and_action_processing():
    result = validate_long_position_limits(
        {" aapl ": 5},
        [action("AAPL", "buy", 2)],
    )
    assert result.projected_positions == (("AAPL", 7),)


def test_sell_above_held_is_fail_closed():
    result = validate_long_position_limits({"AAPL": 5}, [action("AAPL", "SELL", 6)])
    assert result.allowed is False
    assert result.error_codes == ("sell_quantity_exceeds_held",)
    assert result.projected_positions == (("AAPL", 5),)


def test_invalid_action_quantity_type_and_limit_are_fail_closed():
    invalid_type = validate_long_position_limits({"AAPL": 1}, [action("AAPL", "HOLD", 1)])
    invalid_quantity = validate_long_position_limits({"AAPL": 1}, [action("AAPL", "BUY", 0)])
    invalid_actions = validate_long_position_limits({"AAPL": 1}, None)  # type: ignore[arg-type]
    invalid_limit = validate_long_position_limits({"AAPL": 1}, [], max_long_positions=0)
    assert invalid_type.error_codes == ("invalid_action_input",)
    assert invalid_quantity.error_codes == ("invalid_action_input",)
    assert invalid_actions.error_codes == ("invalid_action_input",)
    assert invalid_limit.error_codes == ("invalid_position_input",)
    assert not invalid_type.allowed and not invalid_quantity.allowed
    assert not invalid_actions.allowed and not invalid_limit.allowed


def test_invalid_position_quantity_is_fail_closed():
    result = validate_long_position_limits({"AAPL": -1}, [])
    assert result.allowed is False
    assert result.error_codes == ("invalid_position_input",)
    assert result.available_slots == 0


def test_missing_position_fields_fail_closed_without_raising():
    cases = [
        {"AAPL": {}},
        [{"shares": 1}],
    ]
    for invalid_positions in cases:
        result = validate_long_position_limits(invalid_positions, [])
        assert result.allowed is False
        assert result.error_codes == ("invalid_position_input",)
        assert result.available_slots == 0


def test_missing_action_fields_fail_closed_without_raising():
    cases = [
        [{"symbol": "AAPL"}],
        [{"symbol": "AAPL", "action_type": "BUY"}],
        [{"action_type": "BUY", "quantity": 1}],
    ]
    for invalid_actions in cases:
        result = validate_long_position_limits({"AAPL": 1}, invalid_actions)
        assert result.allowed is False
        assert result.error_codes == ("invalid_action_input",)


def test_none_symbols_fail_closed_without_creating_none_position():
    invalid_position = validate_long_position_limits({None: 1}, [])
    invalid_action = validate_long_position_limits({"AAPL": 1}, [action(None, "BUY", 1)])
    invalid_excluded = validate_long_position_limits({"AAPL": 1}, [], excluded_symbols=[None])
    assert invalid_position.error_codes == ("invalid_position_input",)
    assert invalid_action.error_codes == ("invalid_action_input",)
    assert invalid_excluded.error_codes == ("invalid_position_input",)
    assert all(symbol != "NONE" for symbol, _ in invalid_position.projected_positions)


def test_available_slots_obey_cap_and_full_sell_boundaries():
    nine_positions = validate_long_position_limits(positions(9), [])
    ten_positions = validate_long_position_limits(positions(10), [])
    eleven_positions = validate_long_position_limits(positions(11), [])
    full_sell = validate_long_position_limits(positions(10), [action("L00", "SELL", 10)])
    assert nine_positions.available_slots == 1
    assert ten_positions.available_slots == 0
    assert eleven_positions.available_slots == 0
    assert full_sell.projected_count == 9
    assert full_sell.available_slots == 1


def test_excluded_symbol_does_not_consume_available_slot():
    result = validate_long_position_limits(
        {**positions(9), "HEDGE": 10},
        [],
        excluded_symbols=["hedge"],
    )
    assert result.current_count == 9
    assert result.available_slots == 1


def test_result_order_is_deterministic():
    actions = [action("z", "BUY", 1), action("a", "BUY", 1)]
    first = validate_long_position_limits({" B ": 1}, actions)
    second = validate_long_position_limits({"B": 1}, actions)
    assert first == second
    assert first.projected_positions == (("A", 1), ("B", 1), ("Z", 1))
