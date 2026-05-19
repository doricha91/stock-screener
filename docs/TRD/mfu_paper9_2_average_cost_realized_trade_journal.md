# MFU-PAPER9-2 Average-Cost Realized Trade Journal

## Scope

- Generate a SELL-event-based realized trade journal from `outputs/paper_test/paper_execution_log.csv`
- Preserve existing paper EOD writer and reducer behavior
- Exclude FIFO, LIFO, lot ledger, `open_date`, and `holding_days`

## Added Components

- `core/paper_realized_trade_journal.py`
- `scripts/generate_paper_realized_trade_journal.py`
- `tests/test_paper_realized_trade_journal.py`

## Accounting Policy

- `cost_basis_method = average_cost`
- `entry_basis_type = position_avg_price_before_sell`
- `lot_linking_status = not_applicable`

SELL rows emit realized journal rows using:

- `shares_closed = abs(sell_shares)`
- `entry_price_basis = avg_price immediately before SELL`
- `realized_pnl = (exit_price - entry_price_basis) * shares_closed`
- `realized_return_pct = (exit_price / entry_price_basis - 1) * 100`

## Outputs

- `outputs/paper_test/reports/paper_realized_trade_journal.csv`
- `outputs/paper_test/reports/paper_realized_trade_journal_summary.md`

## Notes

- BUY rows update average cost and cash only.
- SELL rows generate realized journal entries.
- Duplicate `trade_id` rows are skipped, counted, and reported in summary warnings.
- This output is a realized trade journal, not a lot-matched closed trade ledger.
