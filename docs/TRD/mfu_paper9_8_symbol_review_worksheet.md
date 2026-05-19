# MFU-PAPER9-8 Symbol Review Worksheet

## Scope

- Generate a non-actionable review worksheet from `outputs/paper_test/reports/paper_symbol_review_buckets.csv`
- Reuse bucket assignments and performance fields without recalculating PnL
- Exclude action recommendations, replay, FIFO, lot ledger, `open_date`, and `holding_days`

## Added Components

- `core/paper_symbol_review_worksheet.py`
- `scripts/generate_paper_symbol_review_worksheet.py`
- `tests/test_paper_symbol_review_worksheet.py`

## Outputs

- `outputs/paper_test/reports/paper_symbol_review_worksheet.md`
- `outputs/paper_test/reports/paper_symbol_review_worksheet.csv`

## Notes

- `is_actionable` is always `false`
- Markdown contains:
  - header
  - summary
  - review queue
  - per-symbol worksheet sections
- CSV contains one row per review question
- Review queue ordering uses:
  - `review_priority`
  - bucket order
  - `total_pnl` ascending
- Question templates are fixed by `review_bucket`
