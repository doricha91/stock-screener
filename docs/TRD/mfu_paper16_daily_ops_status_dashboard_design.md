# PAPER16-1 Daily Ops Status Dashboard Design

## Purpose

Design the operator-facing Notion dashboard for the `Daily Ops Status` DB. This document defines the manual Notion view layout, field priority, status interpretation, and setup checklist before Alert/Monitoring, Replay, Schema Drift, Universe, or Strategy expansion work.

This is a design-only MFU. It does not create or modify Notion views, does not run Notion actual write/export, does not change Python code, and does not modify paper source-of-truth artifacts.

## Scope / Non-scope

Scope:

- Daily Ops Status dashboard purpose
- recommended Notion views
- display field priorities
- status interpretation table
- manual Notion view setup checklist
- minimal SOP addendum

Non-scope:

- Notion actual DB/view create/update
- Notion actual write/export
- exporter or schema code changes
- wrapper CLI / GUI / GitHub Actions / Notion button implementation
- Alert / Replay / Schema Drift / Universe / Strategy implementation
- `paper_default` migration
- outputs/paper ledger changes

## Source-of-truth Principle

CSV, JSON, Markdown, and SQLite remain the source-of-truth. Local `paper.py status` and generated artifacts define the real operating state.

Notion `Daily Ops Status` is a presentation layer. It summarizes local status rows for operator visibility, but it is not authoritative for ledger, review, execution, or account state.

PAPER15 validated limited Daily Ops Status actual create/update for `paper_sandbox`. PAPER16-1 does not run additional Notion actual write/export and does not manually change Notion from Codex.

## Dashboard Goals

The dashboard should answer these operator questions:

- Which account and date is being inspected?
- Is the daily plan ready?
- Has execution/current state/snapshot work completed?
- Are reports and review template ready?
- Is review pending, partially appended, or done?
- Was the Daily Ops Status row synced to Notion?
- What local command or manual check should be done next?
- Is a row blocked because of missing files, validation failure, or sync failure?

Initial use should focus on `paper_sandbox`. `paper_default` actual export, multi-account bulk export, and automation-triggered export remain forbidden until a later safety review.

## Current Mapping Reference

Mapping section:

- `daily_ops_status`

External Key:

- `daily_ops_status:{account_id}:{status_date}`

Core properties currently mapped:

| Mapping key | Notion property | Type |
| --- | --- | --- |
| `name` | `Name` | title |
| `external_key` | `External Key` | rich_text |
| `account_id` | `Account ID` | select |
| `status_date` | `Status Date` | date |
| `workflow_status` | `Workflow Status` | select |
| `review_progress_status` | `Review Progress Status` | select |
| `review_completion_ratio` | `Review Completion Ratio` | number |
| `next_recommended_command` | `Next Recommended Command` | rich_text |
| `blocking_reason` | `Blocking Reason` | rich_text |
| `plan_exists` | `Plan Exists` | checkbox |
| `current_state_exists` | `Current State Exists` | checkbox |
| `account_snapshot_exists` | `Account Snapshot Exists` | checkbox |
| `position_snapshot_exists` | `Position Snapshot Exists` | checkbox |
| `execution_log_rows_for_date` | `Execution Log Rows For Date` | number |
| `reports_ready` | `Reports Ready` | checkbox |
| `daily_review_summary_exists` | `Daily Review Summary Exists` | checkbox |
| `performance_summary_exists` | `Performance Summary Exists` | checkbox |
| `review_template_exists` | `Review Template Exists` | checkbox |
| `review_template_row_count` | `Review Template Row Count` | number |
| `review_validation_result` | `Review Validation Result` | select |
| `manual_review_log_exists` | `Manual Review Log Exists` | checkbox |
| `manual_review_log_row_count` | `Manual Review Log Row Count` | number |
| `review_answered_row_count` | `Review Answered Row Count` | number |
| `review_pending_row_count` | `Review Pending Row Count` | number |
| `last_status_checked_at` | `Last Status Checked At` | date |
| `sync_status` | `Sync Status` | select |
| `synced_at` | `Synced At` | date |
| `schema_version` | `Schema Version` | rich_text |
| `source_root` | `Source Root` | rich_text |

## Field Priority

Primary fields:

- `Status Date`
- `Account ID`
- `Workflow Status`
- `Review Progress Status`
- `Review Completion Ratio`
- `Sync Status`
- `Next Recommended Command`
- `Blocking Reason`
- `Synced At`
- `External Key`

Secondary fields:

- `Plan Exists`
- `Current State Exists`
- `Account Snapshot Exists`
- `Position Snapshot Exists`
- `Execution Log Rows For Date`
- `Reports Ready`
- `Review Template Exists`
- `Review Validation Result`
- `Manual Review Log Exists`
- `Manual Review Log Row Count`
- `Review Answered Row Count`
- `Review Pending Row Count`

Usually hidden fields:

- `Schema Version`
- `Source Root`
- `Last Status Checked At`
- `Daily Review Summary Exists`
- `Performance Summary Exists`
- `Review Template Row Count`

Keep `External Key` visible in troubleshooting views. It may be hidden in high-level daily views after operators are comfortable with the dashboard.

## Recommended Views

### Today Ops

Purpose:

- Show today's or selected-date operating state by account.

Recommended filter:

- `Status Date` is today, or manually selected operation date.

Recommended sort:

- `Account ID` ascending
- `Workflow Status` ascending

Recommended group:

- `Account ID`

Display fields:

- `Name`
- `Account ID`
- `Status Date`
- `Workflow Status`
- `Review Progress Status`
- `Review Completion Ratio`
- `Sync Status`
- `Next Recommended Command`
- `Blocking Reason`
- `Synced At`

Hide:

- `Source Root`
- `Schema Version`
- low-level artifact checkboxes unless troubleshooting.

Operator decision:

- Identify the next local command or manual check for each account.

### By Account

Purpose:

- Review recent operating history per account.

Recommended filter:

- none by default, or `Status Date` within the last 30 days.

Recommended sort:

- `Status Date` descending

Recommended group:

- `Account ID`

Display fields:

- `Status Date`
- `Workflow Status`
- `Review Progress Status`
- `Sync Status`
- `Review Pending Row Count`
- `Next Recommended Command`
- `External Key`

Hide:

- detailed artifact flags unless investigating a specific account/date.

Operator decision:

- Confirm whether one account repeatedly stalls at the same workflow step.

### Needs Action

Purpose:

- Surface rows that require local operator action.

Recommended filter:

- `Workflow Status` is one of `NO_PLAN`, `PLAN_READY`, `COMMITTED`, `REVIEW_READY`, `REVIEW_PARTIAL`, `UNKNOWN_OR_INCOMPLETE`
- or `Sync Status` is `FAILED`
- or `Review Validation Result` is `FAIL`

Recommended sort:

- `Status Date` descending
- `Workflow Status` ascending

Recommended group:

- `Workflow Status`

Display fields:

- `Account ID`
- `Status Date`
- `Workflow Status`
- `Review Progress Status`
- `Review Pending Row Count`
- `Review Validation Result`
- `Sync Status`
- `Blocking Reason`
- `Next Recommended Command`

Hide:

- `Schema Version`
- `Source Root`
- non-actionable artifact flags unless needed.

Operator decision:

- Decide the next local command, manual review completion, or schema/sync troubleshooting step.

### Recent Sync

Purpose:

- Inspect recent Daily Ops Status Notion sync outcomes.

Recommended filter:

- `Synced At` is within the last 7 days, or no filter during early rollout.

Recommended sort:

- `Synced At` descending

Recommended group:

- `Sync Status`

Display fields:

- `Account ID`
- `Status Date`
- `External Key`
- `Sync Status`
- `Synced At`
- `Last Status Checked At`
- `Workflow Status`
- `Review Progress Status`

Hide:

- most artifact existence flags.

Operator decision:

- Confirm whether a dry-run, actual sync, or failed sync is the latest known Notion presentation state.

### Review Closeout

Purpose:

- Focus on review completion across accounts/dates.

Recommended filter:

- `Workflow Status` is one of `REVIEW_READY`, `REVIEW_PARTIAL`, `REVIEW_DONE`

Recommended sort:

- `Review Pending Row Count` descending
- `Status Date` descending

Recommended group:

- `Review Progress Status`

Display fields:

- `Account ID`
- `Status Date`
- `Workflow Status`
- `Review Progress Status`
- `Review Completion Ratio`
- `Review Template Exists`
- `Review Validation Result`
- `Manual Review Log Exists`
- `Review Answered Row Count`
- `Review Pending Row Count`
- `Next Recommended Command`

Hide:

- execution/snapshot fields unless investigating upstream issues.

Operator decision:

- Determine whether to complete pending review rows, run `review-append`, or mark the day done locally.

## Status Interpretation

### Workflow Status

| Value | Meaning | Operator action |
| --- | --- | --- |
| `NO_PLAN` | Daily plan artifact is missing. | Run local plan generation for the account/date. |
| `PLAN_READY` | Plan exists but same-date state/snapshot is missing. | Run dry-run EOD or complete execution/current-state step as appropriate. |
| `COMMITTED` | Local source-of-truth was updated but reports/review are not ready. | Run reports and prepare review template. |
| `REVIEW_READY` | Reports/template/validation are ready; review append is pending. | Complete review input and run local review append when ready. |
| `REVIEW_PARTIAL` | At least one review row was appended, but pending review rows remain. | Complete pending review rows, then rerun review validation/append. |
| `REVIEW_DONE` | Review rows are complete for the template and log. | No immediate local review action. Confirm sync/presentation if needed. |
| `UNKNOWN_OR_INCOMPLETE` | Status cannot be classified safely. | Inspect local artifacts and `Blocking Reason`. |

### Review Progress Status

| Value | Meaning | Operator action |
| --- | --- | --- |
| `NOT_STARTED` | Review template exists but no review answers/log rows are complete. | Fill review rows before append. |
| `READY` | Candidate/future option for ready-to-append review state. | Treat as review action needed until code/SOP defines exact use. |
| `PARTIAL` | Some review rows are complete/appended, but pending rows remain. | Finish pending rows. |
| `DONE` | Review completion is full. | No review action unless validation/sync failed. |
| `UNKNOWN` | Progress could not be determined. | Inspect local template/log consistency. |
| `NOT_APPLICABLE` | No review template/progress context applies. | Use workflow status to determine upstream action. |

### Sync Status

| Value | Meaning | Operator action |
| --- | --- | --- |
| `DRY_RUN` | Payload was generated without Notion write. | Safe for inspection; no Notion row update expected. |
| `SYNCED` | Daily Ops Status row was actually created/updated. | Confirm displayed fields match local status if needed. |
| `FAILED` | Candidate/future or failure status for actual sync failure. | Do not rollback local source-of-truth; inspect Notion/schema/export error. |
| `SKIPPED` | Candidate/future status for intentionally skipped sync. | Confirm skip reason before rerun. |

## Manual Notion View Setup Checklist

General setup:

- Confirm DB name is `Daily Ops Status`.
- Confirm property names match `config/notion_property_mapping.example.json`.
- Confirm `Account ID`, `Workflow Status`, `Review Progress Status`, and `Sync Status` are select properties.
- Confirm `External Key` remains visible in at least one troubleshooting view.
- Do not create relation/rollup dependencies in the first dashboard pass.

Create views:

- Create `Today Ops`.
- Create `By Account`.
- Create `Needs Action`.
- Create `Recent Sync`.
- Create `Review Closeout`.

For each view:

- Apply the filters described above.
- Apply the sort order described above.
- Apply grouping only where it improves operator scanning.
- Show primary fields first.
- Hide debug/internal fields unless the view is for troubleshooting.
- Verify the displayed property names match this document and the mapping file.

Safety checklist:

- Do not use Notion as source-of-truth.
- Do not manually edit `External Key` unless explicitly performing a future migration procedure.
- Do not infer local ledger success from Notion sync success alone.
- Do not enable bulk export or paper_default actual export from this dashboard design.
- Treat `paper_sandbox` as the first manual dashboard cleanup target.

## Relationship To Existing Notion DBs

`Daily Ops Status` is the operating dashboard. Existing Notion DBs remain detail/staging DBs:

- `Daily Plans`: plan presentation
- `Manual Executions`: execution input/staging
- `Manual Reviews`: review input/staging
- `Account Snapshots`: account state presentation
- `Weekly Reports`: weekly summary presentation
- `Benchmark Reports`: benchmark comparison presentation
- `Daily Review Summaries`: daily outcome presentation

The initial dashboard should connect these concepts through `Account ID`, `Status Date`, and `External Key` conventions only. Relation/rollup design should wait until the dashboard proves stable.

## Risks / Open Questions

- `FAILED`, `SKIPPED`, and `READY` are valid design options but may not yet be emitted in all code paths.
- `Review Progress Status = READY` needs a future explicit semantics decision if operators want to distinguish validated-ready from not-started.
- View filters using "today" must match the intended operation date, not necessarily the calendar date in every workflow.
- Existing SOP files contain legacy text and encoding artifacts; this MFU only adds minimal addenda instead of rewriting the SOP.

## Recommended Next MFU

PAPER16-2 should refine the operating SOP around the dashboard:

- exact command map for each `Workflow Status`
- actual export rerun policy
- schema validation response policy
- operator checklist for `paper_sandbox` and later approved non-default accounts
