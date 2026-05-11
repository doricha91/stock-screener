from core.paper_trade_preview import PaperTradePreview, build_paper_trade_previews


def test_ready_buy_row_converts_to_preview():
    previews, warnings = build_paper_trade_previews(
        [
            {
                "date": "2026-05-07",
                "regime": "BULL",
                "symbol": "AAPL",
                "type": "BUY",
                "rec_shares": "10",
                "rec_price": "185.20",
                "act_shares": "10",
                "act_price": "185.30",
                "reason": "PAPER_FILLED",
                "notes": "",
                "status": "READY_FOR_PAPER_TRADE",
            }
        ]
    )

    assert warnings == []
    assert len(previews) == 1
    preview = previews[0]
    assert isinstance(preview, PaperTradePreview)
    assert preview.side == "BUY"
    assert preview.shares == 10
    assert preview.price == 185.30
    assert preview.gross_amount == 1853.0


def test_ready_sell_row_converts_to_negative_shares():
    previews, warnings = build_paper_trade_previews(
        [
            {
                "date": "2026-05-07",
                "regime": "BULL",
                "symbol": "TSLA",
                "type": "SELL",
                "rec_shares": "3",
                "rec_price": "240.00",
                "act_shares": "3",
                "act_price": "240.10",
                "reason": "PAPER_FILLED",
                "notes": "",
                "status": "READY_FOR_PAPER_TRADE",
            }
        ]
    )

    assert warnings == []
    assert len(previews) == 1
    preview = previews[0]
    assert preview.side == "SELL"
    assert preview.shares == -3
    assert round(preview.gross_amount, 2) == -720.30


def test_pending_row_is_excluded_with_warning():
    previews, warnings = build_paper_trade_previews(
        [
            {
                "date": "2026-05-07",
                "regime": "BULL",
                "symbol": "AAPL",
                "type": "BUY",
                "rec_shares": "10",
                "rec_price": "185.20",
                "act_shares": "",
                "act_price": "",
                "reason": "",
                "notes": "",
                "status": "PENDING_ACTUAL_FILL",
            }
        ]
    )

    assert previews == []
    assert len(warnings) == 1
    assert "PENDING_ACTUAL_FILL" in warnings[0]


def test_review_and_warning_rows_are_excluded():
    previews, warnings = build_paper_trade_previews(
        [
            {
                "date": "2026-05-07",
                "regime": "BULL",
                "symbol": "AAPL",
                "type": "SELL",
                "rec_shares": "10",
                "rec_price": "185.20",
                "act_shares": "10",
                "act_price": "185.30",
                "reason": "REVIEW_EXIT",
                "notes": "",
                "status": "READY_FOR_PAPER_TRADE",
            },
            {
                "date": "2026-05-07",
                "regime": "BULL",
                "symbol": "TSLA",
                "type": "SELL",
                "rec_shares": "10",
                "rec_price": "185.20",
                "act_shares": "10",
                "act_price": "185.30",
                "reason": "WARNING_HIGHEST_PRICE_STALE",
                "notes": "",
                "status": "READY_FOR_PAPER_TRADE",
            },
        ]
    )

    assert previews == []
    assert len(warnings) == 2


def test_invalid_numeric_fields_are_warning_only():
    previews, warnings = build_paper_trade_previews(
        [
            {
                "date": "2026-05-07",
                "regime": "BULL",
                "symbol": "AAPL",
                "type": "BUY",
                "rec_shares": "10",
                "rec_price": "185.20",
                "act_shares": "abc",
                "act_price": "185.30",
                "reason": "PAPER_FILLED",
                "notes": "",
                "status": "READY_FOR_PAPER_TRADE",
            }
        ]
    )

    assert previews == []
    assert len(warnings) == 1
    assert "invalid numeric fields" in warnings[0]
