from core.position_sizing import calculate_entry_shares


def test_calculate_entry_shares_normal_case():
    assert calculate_entry_shares(
        total_equity=100000,
        available_buying_power=30000,
        price=200,
        max_positions=10,
    ) == 50


def test_calculate_entry_shares_limited_by_buying_power():
    assert calculate_entry_shares(
        total_equity=100000,
        available_buying_power=5000,
        price=200,
        max_positions=10,
    ) == 25


def test_calculate_entry_shares_zero_buying_power():
    assert calculate_entry_shares(
        total_equity=100000,
        available_buying_power=0,
        price=200,
        max_positions=10,
    ) == 0


def test_calculate_entry_shares_zero_price():
    assert calculate_entry_shares(
        total_equity=100000,
        available_buying_power=30000,
        price=0,
        max_positions=10,
    ) == 0


def test_calculate_entry_shares_zero_max_positions():
    assert calculate_entry_shares(
        total_equity=100000,
        available_buying_power=30000,
        price=200,
        max_positions=0,
    ) == 0


def test_calculate_entry_shares_matches_existing_formula():
    total_equity = 100000
    available_buying_power = 30000
    price = 200
    max_positions = 10

    expected = int(min(total_equity / max_positions, available_buying_power) / price)

    assert calculate_entry_shares(
        total_equity=total_equity,
        available_buying_power=available_buying_power,
        price=price,
        max_positions=max_positions,
    ) == expected
