# MFU-PAPER10-2 Manual Review Log Validator

## Scope

- Validate manual review log CSV structure and row-level policy
- Report issues without modifying the source CSV
- Preserve the non-actionable review boundary

## Added Components

- `core/paper_manual_review_log_validator.py`
- `scripts/validate_paper_manual_review_log.py`
- `tests/test_paper_manual_review_log_validator.py`

## Outputs

- `outputs/paper_test/reviews/paper_manual_review_log_validation_report.md`
- `outputs/paper_test/reviews/paper_manual_review_log_validation_issues.csv`

## Notes

- Default input is `outputs/paper_test/reviews/paper_manual_review_log_template.csv`
- Validation covers required columns, allowed values, duplicate keys, and blank-field policy
- Errors and warnings are written to issues CSV and summarized in markdown
- This MFU does not append rows, generate cumulative logs, or update existing review entries
