from core.paper_trade_preview import (
    PAPER_VIRTUAL_FILL_REASON,
    build_paper_trade_previews,
    resolve_paper_actual_fill,
)


def test_virtual_fill_source_is_used_when_actual_fields_are_blank():
    row = {
        "symbol": "AAPL",
        "type": "BUY",
        "rec_shares": "10",
        "rec_price": "100",
        "act_shares": "[ ]",
        "act_price": "[ ]",
        "reason": "[ ]",
    }

    resolved = resolve_paper_actual_fill(row)

    assert resolved.shares == 10
    assert resolved.price == 100.0
    assert resolved.source == "paper_virtual_fill"
    assert "Rec_Shares" in resolved.reason


def test_actual_fill_source_is_preserved_when_actual_fields_are_numeric():
    row = {
        "symbol": "AAPL",
        "type": "BUY",
        "rec_shares": "10",
        "rec_price": "100",
        "act_shares": "8",
        "act_price": "101",
        "reason": "Manual broker fill",
    }

    resolved = resolve_paper_actual_fill(row)

    assert resolved.shares == 8
    assert resolved.price == 101.0
    assert resolved.source == "journal_actual_fill"
    assert resolved.reason == "Manual broker fill"


def test_preview_rows_show_virtual_fill_source_and_reason_for_switch_rows():
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
        ]
    )

    assert warnings == []
    assert [preview.symbol for preview in previews] == ["CPAY", "CF"]
    assert all(preview.source == "paper_virtual_fill" for preview in previews)
    assert all(preview.reason == PAPER_VIRTUAL_FILL_REASON for preview in previews)
