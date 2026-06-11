# MFU-OPER9-18 No-Action Day Daily Review Completion Guard

## Summary

OPER9-18 fixes a Daily Ops Orchestrator loop on no-action days. When the Daily Plan has zero execution candidates, Manual Execution is intentionally skipped and `paper.py review` can complete without creating a same-day execution commit or same-day account snapshot.

## Problem

OPER9-16 added a stale artifact guard for fixed-name review files. It required `paper_daily_review_summary.md` `Latest snapshot date` to match `trade_date` before marking `DAILY_REVIEW` as `DONE`.

That rule is correct for normal execution days, but too strict for no-action days:

- no execution candidates means no manual execution commit is expected;
- account and position snapshots can legitimately remain on the previous data date;
- the current review completion evidence is the review template `review_date=trade_date` plus validation `PASS`.

## Completion Policy

When `MANUAL_EXECUTION_TEMPLATE` reports `no_execution_candidates=true`, `DAILY_REVIEW` is `DONE` if all of the following are true:

- `paper_manual_review_log_template.csv` exists;
- every `review_date` in the review template equals `trade_date`;
- `paper_manual_review_log_validation_report.md` reports `Validation result: PASS`;
- `paper_daily_review_summary.md` exists;
- `paper_performance_summary.md` exists.

In this no-action day path, `paper_daily_review_summary.md` `Latest snapshot date != trade_date` is downgraded from blocker to warning. `paper_performance_summary.md` snapshot date mismatch remains a warning.

The review template date guard is not relaxed. A stale template date still blocks `DAILY_REVIEW` and `MANUAL_REVIEW_TEMPLATE`.

## JSON Contract

`DAILY_REVIEW` may include these additive fields:

- `no_action_day_review_guard`
- `review_template_date_current`
- `snapshot_date_mismatch_allowed`
- `daily_review_snapshot_date`
- `performance_snapshot_date`

No existing fields are removed.

## CSV Handling

Review template CSV parsing uses `utf-8-sig` through the shared CSV reader, so a UTF-8 BOM on `paper_manual_review_log_template.csv` does not hide the `review_date` header.

## Validation

Guard tests cover:

- no-action day review completion with previous-day snapshot dates;
- UTF-8 BOM review template headers;
- stale review template dates remaining blocked even on no-action days;
- normal execution day summary snapshot mismatch remaining blocked;
- existing OPER9-16 and OPER9-17 guard behavior.
