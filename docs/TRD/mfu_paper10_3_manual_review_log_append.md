# MFU-PAPER10-3 Manual Review Log Append

## Scope

- Append processed manual review rows into a cumulative review log
- Reuse PAPER10-2 validator before append
- Preserve append-only behavior without updating existing rows

## Added Components

- `core/paper_manual_review_log_append.py`
- `scripts/append_paper_manual_review_log.py`
- `tests/test_paper_manual_review_log_append.py`

## Outputs

- `outputs/paper_test/reviews/paper_manual_review_log.csv`
- `outputs/paper_test/reviews/paper_manual_review_log_append_report.md`
- `outputs/paper_test/reviews/paper_manual_review_log_append_issues.csv`

## Notes

- Pending rows are intentionally excluded from append
- Appendable statuses are `reviewed`, `deferred`, and `not_applicable`
- Duplicate key is `review_date + symbol + question_id`
- Existing rows are never updated or overwritten in this MFU
