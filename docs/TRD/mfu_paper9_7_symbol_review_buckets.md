# MFU-PAPER9-7 Symbol Review Buckets

## Scope

- Build non-actionable review buckets from `outputs/paper_test/reports/paper_symbol_side_by_side_performance.csv`
- Classify symbols for review only
- Exclude replay, PnL recalculation, action suggestions, FIFO, lot ledger, `open_date`, and `holding_days`

## Added Components

- `core/paper_symbol_review_buckets.py`
- `scripts/generate_paper_symbol_review_buckets.py`
- `tests/test_paper_symbol_review_buckets.py`

## Outputs

- `outputs/paper_test/reports/paper_symbol_review_buckets.csv`
- `outputs/paper_test/reports/paper_symbol_review_buckets_summary.md`

## Classification Rules

- Buckets:
  - `review_loss`
  - `track_realized_gain`
  - `monitor_open_gain`
  - `monitor_open_loss`
  - `neutral`
- `neutral_threshold_pct = 0.5`
- Open-position criteria are evaluated before realized-history criteria.

## Notes

- `is_actionable` is always `false`
- `sample_size_flag` is separate from `review_bucket`
- `review_priority` maps to:
  - `high`: `review_loss`, `monitor_open_loss`
  - `medium`: `monitor_open_gain`, `track_realized_gain`
  - `low`: `neutral`
- `low_sample` warnings are surfaced in the summary rather than creating a separate bucket
