# MFU-PAPER9-6 Symbol Side-by-Side Performance

## Scope

- Build a symbol-level side-by-side report from:
  - `outputs/paper_test/reports/paper_symbol_realized_performance.csv`
  - `outputs/paper_test/reports/paper_symbol_unrealized_performance.csv`
- Keep realized and unrealized interpretation separate
- Exclude replay, recalculation of source metrics, FIFO, lot ledger, `open_date`, `holding_days`, and commentary generation

## Added Components

- `core/paper_symbol_side_by_side_performance.py`
- `scripts/generate_paper_symbol_side_by_side_performance.py`
- `tests/test_paper_symbol_side_by_side_performance.py`

## Outputs

- `outputs/paper_test/reports/paper_symbol_side_by_side_performance.csv`
- `outputs/paper_test/reports/paper_symbol_side_by_side_performance_summary.md`

## Notes

- Join strategy is `outer join` on `symbol`
- `symbol_status` values:
  - `realized_only`
  - `unrealized_only`
  - `realized_and_unrealized`
- `total_pnl = realized_pnl + unrealized_pnl` is included only as a reference metric
- Missing-side defaults:
  - realized side missing -> realized fields default to `0`
  - unrealized side missing -> open-position fields default to `0`
- `risk_note` is used to flag `no_realized_history` or `no_open_position`
