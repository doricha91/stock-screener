# MFU-PAPER9-5 Symbol-Level Unrealized Performance

## Scope

- Generate current open-position unrealized performance from the latest rows in `outputs/paper_test/paper_position_snapshot.csv`
- Keep realized reports separate
- Exclude realized PnL integration, total PnL integration, FIFO, lot ledger, `open_date`, and `holding_days`

## Added Components

- `core/paper_symbol_unrealized_performance.py`
- `scripts/generate_paper_symbol_unrealized_performance.py`
- `tests/test_paper_symbol_unrealized_performance.py`

## Input and Outputs

Input:

- `outputs/paper_test/paper_position_snapshot.csv`
- `outputs/paper_test/paper_account_snapshot.csv` for cross-check

Outputs:

- `outputs/paper_test/reports/paper_symbol_unrealized_performance.csv`
- `outputs/paper_test/reports/paper_symbol_unrealized_performance_summary.md`

## Notes

- Only the latest `snapshot_date` rows with `position_status = OPEN` are included.
- Input unrealized values are preserved by default; recalculated values are used only for validation warnings.
- Account snapshot totals are checked against:
  - summed `market_value`
  - summed `cost_basis`
  - summed `unrealized_pnl`
- Tolerance for cross-check and input-vs-recalc warnings is `0.05`.
