# MFU-PAPER15-4B paper_sandbox Manual Execution Commit Rehearsal

## Purpose

Run a single safety-bounded manual execution commit rehearsal for `paper_sandbox` in the real workspace so that snapshot/report/review artifacts can be exercised without touching legacy `paper_default` roots or external systems.

## Scope / Non-scope

In scope:
- `paper_sandbox` pre-check
- one local manual execution preview fixture
- one local manual execution commit
- reports
- review-template
- review-validate
- final status check
- contamination checks for `outputs/paper_test` and `outputs/paper_accounts/paper_default`

Out of scope:
- Notion actual export/sync/write
- review-append
- broker/API
- cloud runner
- `paper_default` migration
- real investment orders

## Rehearsal account_id

- `account_id = paper_sandbox`
- allowed root: `outputs/paper_accounts/paper_sandbox`

## Pre-check result

Before commit:
- `paper.py status --account-id paper_sandbox --json`
  - workflow: `PLAN_READY`
  - plan existed
  - snapshots/current state/execution log were absent
- existing sandbox files:
  - `daily_action_plan_20260520.md`
  - `config_snapshots/paper_config_snapshot_20260520.json`

## Manual Execution fixture summary

Fixture file:
- `outputs/paper_accounts/paper_sandbox/manual_execution_preview_20260520_sandbox.json`

Fixture values:
- `account_id = paper_sandbox`
- `execution_date = 2026-05-20`
- `symbol = AMT`
- `side = BUY`
- `quantity = 1`
- `actual_price = 184.02`
- `canonical_key = manual_execution:paper_sandbox:2026-05-20:AMT:BUY:01`
- `legacy_canonical_key = null`
- `legacy_key_compatible = false`

Bootstrap support file:
- `paper_account_snapshot.csv`
  - single baseline row for `2026-05-19`
  - purpose: provide `initial_cash` / `currency` seed for commit helper

## Commit command or core path used

CLI path used:

`python scripts\import_notion_executions.py --date 2026-05-20 --account-id paper_sandbox --commit --preview-json outputs\paper_accounts\paper_sandbox\manual_execution_preview_20260520_sandbox.json --json`

Result:
- commit succeeded
- committed rows: `1`

## Generated sandbox artifacts

Commit/update outputs under sandbox root:
- `paper_execution_log.csv`
- `paper_account_snapshot.csv`
- `paper_position_snapshot.csv`
- `paper_current_state_20260520.json`
- `reports/manual_execution_import_commit_20260520.json`
- `reports/manual_execution_import_commit_20260520.md`
- `archive/dev_backups/paper_account_snapshot_before_manual_execution_commit_...csv`

Reports after commit:
- equity curve
- drawdown
- performance summary
- realized trade journal
- realized ranking
- symbol realized/unrealized/side-by-side summaries
- symbol review buckets
- symbol review worksheet
- daily review summary
- report index

Review outputs after retry:
- `reviews/paper_manual_review_log_template.csv`
- `reviews/paper_manual_review_log_template.md`
- `reviews/paper_manual_review_log_validation_report.md`
- `reviews/paper_manual_review_log_validation_issues.csv`

## Reports result

`python scripts\paper.py reports --account-id paper_sandbox`

Result:
- succeeded
- no longer blocked by missing `paper_account_snapshot.csv`

## Review-template result

First run:
- failed with `paper_symbol_review_worksheet.csv not found`

Follow-up check:
- reports directory did contain `paper_symbol_review_worksheet.csv`

Retry:
- succeeded
- `review_template_row_count = 4`

## Review-validate result

First run:
- failed because `paper_manual_review_log_template.csv` did not exist yet

Retry after successful review-template:
- succeeded
- `validation_result = PASS`

## Final status result

Final `paper.py status --account-id paper_sandbox --json`:
- `workflow_status = REVIEW_READY`
- `execution_log_row_count = 1`
- `account_snapshot_exists = true`
- `position_snapshot_exists = true`
- `current_state_exists = true`
- `reports_exists = true`
- `review_template_exists = true`
- `review_validation_result = PASS`
- `manual_review_log_exists = false`

## outputs/paper_test contamination check

Before/after file-list comparison showed no differences for `outputs/paper_test`.

Result:
- no contamination detected

## outputs/paper_accounts/paper_default contamination check

Before/after file-list comparison showed no differences for `outputs/paper_accounts/paper_default`.

Result:
- no contamination detected

## Failures / blockers

Observed but resolved during rehearsal:
- initial `review-template` call failed even though `reports` had completed
- initial `review-validate` failed because template had not yet been created

Current remaining blocker:
- `review-append` was intentionally not executed in this MFU

## Readiness decision

`paper_sandbox` is ready for:
- non-default manual execution commit rehearsal
- snapshot/current-state/execution-log generation
- reports
- review-template
- review-validate
- final status re-check

This is sufficient for a constrained local non-default daily ops rehearsal without external integrations.

## Next MFU recommendation

Next MFU should validate `review-append` for `paper_sandbox` and then rehearse the full local operator chain:

`status -> plan -> manual execution commit -> reports -> review-template -> review-validate -> review-append -> status`

while keeping Notion actual sync/write disabled.
