# MFU-PAPER11-10 Paper Status Command

## Summary

- Added `paper.py status` as a read-only operator status summary.
- Supported forms:
  - `python scripts/paper.py status`
  - `python scripts/paper.py status --date YYYYMMDD`
  - `python scripts/paper.py status --json`
  - `python scripts/paper.py status --verbose`

## Inputs Read

- `outputs/paper_test/daily_action_plan_YYYYMMDD.md`
- `outputs/paper_test/paper_current_state_YYYYMMDD.json`
- `outputs/paper_test/paper_account_snapshot.csv`
- `outputs/paper_test/paper_position_snapshot.csv`
- `outputs/paper_test/paper_execution_log.csv`
- `outputs/paper_test/reports/paper_daily_review_summary.md`
- `outputs/paper_test/reports/paper_performance_summary.md`
- `outputs/paper_test/reviews/paper_manual_review_log_template.csv`
- `outputs/paper_test/reviews/paper_manual_review_log_validation_report.md`
- `outputs/paper_test/reviews/paper_manual_review_log.csv`

## Status Resolution

### Date omitted

- infer latest operational date from:
  - latest account snapshot date
  - latest position snapshot date
  - latest current-state filename
  - latest daily-action-plan filename

### Date provided

- evaluate that exact date for:
  - plan existence
  - same-date snapshots
  - reports presence
  - review template / validation state

## Workflow Status Rules

- `NO_PLAN`
  - daily action plan missing for the target date
- `PLAN_READY`
  - daily action plan exists
  - same-date commit snapshots do not exist
- `COMMITTED`
  - same-date current-state/account/position snapshot artifacts exist
  - but review artifacts are not yet fully ready
- `REVIEW_READY`
  - committed state exists
  - reports exist
  - review template exists
  - validation result is `PASS`
- `UNKNOWN_OR_INCOMPLETE`
  - fallback when files do not match a cleaner state

## Next Recommended Command

- `NO_PLAN` -> `paper.py preview --date YYYYMMDD`
- `PLAN_READY` -> `paper.py commit --date YYYYMMDD`
- `COMMITTED` -> `paper.py review`
- `REVIEW_READY` -> `no immediate action`
- `UNKNOWN_OR_INCOMPLETE` -> `inspect status details manually`

## JSON / Verbose

- `--json`
  - dumps the full status payload for automation
- `--verbose`
  - keeps human-readable output but includes additional fields such as latest dates and row counts

## Safety Notes

- `status` is strictly read-only.
- It does not run:
  - `prepare-data`
  - `data-freshness`
  - `plan`
  - `eod`
  - `reports`
  - `review-template`
  - `review-validate`
  - `review-append`
