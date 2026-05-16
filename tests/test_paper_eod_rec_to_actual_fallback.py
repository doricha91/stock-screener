from core.paper_trade_preview import (
    build_paper_trade_previews,
    is_blank_actual_value,
    resolve_paper_actual_fill,
)


def test_blank_actual_values_fall_back_to_rec_values():
    row = {
        "symbol": "AAPL",
        "type": "BUY",
        "rec_shares": "10",
        "rec_price": "100.5",
        "act_shares": "[ ]",
        "act_price": "[ ]",
    }

    resolved = resolve_paper_actual_fill(row)

    assert resolved.shares == 10
    assert resolved.price == 100.5


def test_numeric_actual_values_take_priority_over_rec_values():
    row = {
        "symbol": "AAPL",
        "type": "BUY",
        "rec_shares": "10",
        "rec_price": "100",
        "act_shares": "8",
        "act_price": "101",
    }

    resolved = resolve_paper_actual_fill(row)

    assert resolved.shares == 8
    assert resolved.price == 101.0


def test_invalid_rec_and_actual_values_are_skipped():
    previews, warnings = build_paper_trade_previews(
        [
            {
                "date": "2026-05-12",
                "regime": "BULL",
                "symbol": "AAPL",
                "type": "BUY",
                "rec_shares": "[ ]",
                "rec_price": "[ ]",
                "act_shares": "[ ]",
                "act_price": "[ ]",
                "reason": "MATCH",
                "notes": "",
                "status": "READY_FOR_PAPER_TRADE",
            }
        ]
    )

    assert previews == []
    assert len(warnings) == 1
    assert "invalid numeric fields" in warnings[0]


def test_switch_rows_generate_previews_with_real_tickers():
    previews, warnings = build_paper_trade_previews(
        [
            {
                "date": "2026-05-12",
                "regime": "BULL",
                "symbol": "CPAY",
                "type": "SELL",
                "rec_shares": "29",
                "rec_price": "338.34",
                "act_shares": "[ ]",
                "act_price": "[ ]",
                "reason": "[ ]",
                "notes": "",
                "status": "READY_FOR_PAPER_TRADE",
            },
            {
                "date": "2026-05-12",
                "regime": "BULL",
                "symbol": "CF",
                "type": "BUY",
                "rec_shares": "75",
                "rec_price": "130.39",
                "act_shares": "[ ]",
                "act_price": "[ ]",
                "reason": "[ ]",
                "notes": "",
                "status": "READY_FOR_PAPER_TRADE",
            },
            {
                "date": "2026-05-12",
                "regime": "BULL",
                "symbol": "VRSN",
                "type": "SELL",
                "rec_shares": "34",
                "rec_price": "285.80",
                "act_shares": "[ ]",
                "act_price": "[ ]",
                "reason": "[ ]",
                "notes": "",
                "status": "READY_FOR_PAPER_TRADE",
            },
            {
                "date": "2026-05-12",
                "regime": "BULL",
                "symbol": "BRK-B",
                "type": "BUY",
                "rec_shares": "20",
                "rec_price": "484.96",
                "act_shares": "[ ]",
                "act_price": "[ ]",
                "reason": "[ ]",
                "notes": "",
                "status": "READY_FOR_PAPER_TRADE",
            },
        ]
    )

    assert warnings == []
    assert [preview.symbol for preview in previews] == ["CPAY", "CF", "VRSN", "BRK-B"]
    assert [preview.shares for preview in previews] == [-29, 75, -34, 20]


def test_blank_placeholder_detection_covers_expected_values():
    for value in [None, "", " ", "[ ]", "[]", "[  ]", "N/A", "nan"]:
        assert is_blank_actual_value(value) is True
