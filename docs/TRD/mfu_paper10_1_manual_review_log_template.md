# MFU-PAPER10-1 Manual Review Log Template

## Scope

- Create a manual review log template from existing paper review reports
- Preserve the non-actionable review boundary
- Write outputs under `outputs/paper_test/reviews/` instead of `reports/`

## Added Components

- `core/paper_manual_review_log_template.py`
- `scripts/generate_paper_manual_review_log_template.py`
- `tests/test_paper_manual_review_log_template.py`

## Outputs

- `outputs/paper_test/reviews/paper_manual_review_log_template.csv`
- `outputs/paper_test/reviews/paper_manual_review_log_template.md`

## Notes

- Input sources are `paper_symbol_review_worksheet.csv` and `paper_symbol_review_buckets.csv`
- Worksheet question rows are converted directly into manual log rows
- Manual fields default to blank or pending values for operator input
- No PnL recomputation, bucket reclassification, or worksheet regeneration occurs in this MFU
- The template remains non-actionable and does not recommend buy, sell, or hold actions
