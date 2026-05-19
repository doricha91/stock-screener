# MFU-PAPER9-3 Symbol-Level Realized Performance

## Scope

- Aggregate symbol-level realized performance from `outputs/paper_test/reports/paper_realized_trade_journal.csv`
- Keep PAPER9-2 journal as the source of truth
- Exclude unrealized PnL, open positions, FIFO, lot ledger, `open_date`, and `holding_days`

## Added Components

- `core/paper_symbol_realized_performance.py`
- `scripts/generate_paper_symbol_realized_performance.py`
- `tests/test_paper_symbol_realized_performance.py`

## Input and Outputs

Input:

- `outputs/paper_test/reports/paper_realized_trade_journal.csv`

Outputs:

- `outputs/paper_test/reports/paper_symbol_realized_performance.csv`
- `outputs/paper_test/reports/paper_symbol_realized_performance_summary.md`

## Policy Validation

All input rows must share:

- `cost_basis_method = average_cost`
- `entry_basis_type = position_avg_price_before_sell`
- `lot_linking_status = not_applicable`

Mixed policy rows are rejected.

## Metrics

Per symbol:

- realized trade count
- total realized PnL
- win/loss/flat counts and rates
- average realized PnL
- average realized return pct
- best/worst trade PnL and return pct
- total shares closed
- first/last close date
- gross profit / gross loss / profit factor

## Notes

- This report summarizes realized SELL-event performance only.
- Unrealized PnL and current open positions are intentionally excluded.
- Empty input produces an empty CSV plus warning summary instead of replaying upstream logic.
