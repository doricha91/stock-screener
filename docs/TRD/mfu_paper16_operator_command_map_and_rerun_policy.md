# PAPER16-2 Operator Command Map And Rerun Policy

## Purpose

Define the Daily Ops Status operator command map, actual export rerun policy, and manual Notion view cleanup procedure after the PAPER16-1 dashboard design.

This is a documentation-only MFU. It does not modify Python code, does not create or edit Notion views, does not run Notion actual write/export, and does not modify outputs/paper source-of-truth artifacts.

## Scope / Non-scope

Scope:

- operator actions for `workflow_status`, `review_progress_status`, and `sync_status`
- allowed and forbidden local commands by status
- actual export and status sync rerun policy
- source-of-truth rollback policy
- manual Notion view setup procedure
- PAPER16-3 readiness checklist

Non-scope:

- new status implementation
- new CLI or wrapper CLI implementation
- Notion actual write/export
- Notion DB or view create/update
- multi-account bulk export
- `paper_default` actual export
- broker/API, cloud runner, Alert, Replay, Schema Drift, Universe, or Strategy work

## Source-of-truth Rule

CSV, JSON, Markdown, and SQLite remain source-of-truth. Notion is an input, review, staging, and presentation layer.

If local commit/append succeeds and Notion sync/export fails, do not rollback local source-of-truth. Rerun the Notion sync/export path against the same source-of-truth report, `account_id`, `status_date`, and `External Key`.

## Current CLI Reference

Confirmed local commands:

- `python scripts\paper.py status --account-id <account_id> --json`
- `python scripts\paper.py plan --date <YYYYMMDD> --account-id <account_id>`
- `python scripts\paper.py eod --date <YYYYMMDD> --account-id <account_id> --dry-run`
- `python scripts\paper.py reports --account-id <account_id>`
- `python scripts\paper.py review-template --account-id <account_id>`
- `python scripts\paper.py review-validate --account-id <account_id>`
- `python scripts\paper.py review-append --account-id <account_id>`
- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json`
- `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json`

Current Daily Ops Status actual export guard:

- `--daily-ops-status` requires `--dry-run` or `--confirm-actual`
- `--daily-ops-status` cannot be combined with other export targets
- actual Daily Ops Status export is limited to `account_id=paper_sandbox`

## Operator Command Map

### Workflow Status

| Status Area | Status Value | Classification | Meaning | Allowed Action | Forbidden Action | Next Recommended Command | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| workflow_status | `NO_PLAN` | current | Daily plan is missing. | Generate plan for the account/date. | Commit, review append, actual export as done. | `python scripts\paper.py plan --date <YYYYMMDD> --account-id <account_id>` | For non-default accounts, confirm the account root is expected. |
| workflow_status | `PLAN_READY` | current | Plan exists, but same-date state/snapshot is missing. | Run EOD dry-run or complete execution flow. | Treat as committed or reviewed. | `python scripts\paper.py eod --date <YYYYMMDD> --account-id <account_id> --dry-run` | Actual execution commit is a separate guarded workflow. |
| workflow_status | `COMMITTED` | current | Source-of-truth was updated, but reports/review are not ready. | Generate reports and review template. | Mark review done. | `python scripts\paper.py reports --account-id <account_id>` then `python scripts\paper.py review-template --account-id <account_id>` | If reports fail, inspect missing snapshot/log artifacts. |
| workflow_status | `REVIEW_READY` | current | Reports and validation are ready; review append is pending. | Complete review input and run review append when ready. | Mark closeout complete before append. | `python scripts\paper.py review-append --account-id <account_id>` | If manual review fields are incomplete, update the review input first. |
| workflow_status | `REVIEW_PARTIAL` | current | Some review rows are appended but pending rows remain. | Complete pending review rows, validate, append remaining rows. | Treat day as fully closed. | `python scripts\paper.py review-validate --account-id <account_id>` then `python scripts\paper.py review-append --account-id <account_id>` | Closeout is not complete while pending rows remain. |
| workflow_status | `REVIEW_DONE` | current | Review rows are complete. | Confirm Daily Ops Status dry-run/actual export if allowed. | Re-run append without verifying idempotency. | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json` | Actual export remains guarded and paper_sandbox-only in current stage. |
| workflow_status | `UNKNOWN_OR_INCOMPLETE` | current | Status cannot be classified safely. | Inspect local artifacts and blocking reason. | Commit, append, or actual export as success. | `python scripts\paper.py status --account-id <account_id> --json` | Resolve missing artifacts before proceeding. |

### Review Progress Status

| Status Area | Status Value | Classification | Meaning | Allowed Action | Forbidden Action | Next Recommended Command | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| review_progress_status | `NOT_STARTED` | current | Review has not been answered/appended. | Fill review rows and validate. | Mark review complete. | `python scripts\paper.py review-validate --account-id <account_id>` | Append only after valid review input exists. |
| review_progress_status | `PARTIAL` | current | Some review rows are complete, pending rows remain. | Complete pending rows and append remaining valid rows. | Closeout as done. | `python scripts\paper.py review-validate --account-id <account_id>` | Matches `REVIEW_PARTIAL` operating state. |
| review_progress_status | `DONE` | current | Review progress is complete. | Confirm status/export presentation. | Re-append without checking duplicate risk. | `python scripts\paper.py status --account-id <account_id> --json` | Use Daily Ops Status export only if target/account is allowed. |
| review_progress_status | `NOT_APPLICABLE` | current | Review progress is not relevant yet. | Follow workflow status. | Force review append. | Use workflow-specific command. | Usually upstream plan/commit/report state is not ready. |
| review_progress_status | `UNKNOWN` | candidate/future | Progress cannot be determined. | Inspect template/log consistency. | Commit/append/export as success. | `python scripts\paper.py status --account-id <account_id> --json` | Treat as blocking until understood. |
| review_progress_status | `READY` | candidate/future | Potential future validated-ready state. | Follow future SOP once implemented. | Assume complete. | TBD | Not currently a stable local status semantic. |

### Sync Status

| Status Area | Status Value | Classification | Meaning | Allowed Action | Forbidden Action | Next Recommended Command | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| sync_status | `DRY_RUN` | current | Payload was generated without Notion write. | Inspect payload; run actual only if allowed. | Assume Notion row is updated. | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json` | Actual is guarded and paper_sandbox-only. |
| sync_status | `SYNCED` | current | Notion presentation row was created/updated. | Compare visible fields with local status if needed. | Treat Notion as source-of-truth. | `python scripts\paper.py status --account-id <account_id> --json` | Source-of-truth remains local. |
| sync_status | `FAILED` | current/operator concept | Export/sync failed or a failure summary was generated. | Fix schema/mapping/client issue and rerun same External Key. | Rollback local ledger/review state. | If a documented schema/mapping validator command exists, run it first; otherwise inspect schema/mapping manually, then rerun dry-run. | For Daily Ops Status, actual rerun must remain guarded. |
| sync_status | `SKIPPED` | candidate/future | Sync was intentionally skipped. | Confirm skip reason. | Bulk rerun blindly. | TBD | Keep until future exporter emits it consistently. |
| sync_status | `NOT_SYNCED` | candidate/future | Notion row has not been synced yet. | Dry-run first; actual only if allowed. | Bulk actual export. | `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json` | Not currently a mapped option in code; use as operator concept only. |
| sync_status | `SYNC_FAILED` | candidate/future | Alias-style operator label for sync failure. | Treat the same as `FAILED`. | Rollback source-of-truth. | Inspect schema/mapping first, then rerun dry-run before actual retry. | Prefer mapped value `FAILED` in Notion select options. |

## Blocking / Warning Policy

- `FAIL`, `FAILED`, or a concrete `Blocking Reason` blocks commit, append, and actual export until the cause is resolved.
- `WARNING` blocks commit/append/export by default unless the specific command has a documented explicit allow option.
- `REVIEW_PARTIAL` blocks full closeout because pending review rows remain.
- `REVIEW_DONE` allows review closeout interpretation, but does not by itself prove Notion presentation is synced.
- `SYNC_FAILED` / `FAILED` does not invalidate successful local commit/append.
- `External Key` must not be manually edited in Notion outside a future migration procedure.

## Actual Export / Sync Rerun Policy

General policy:

- Always run dry-run before actual export.
- Actual write/export requires an explicit confirm flag or a documented approved command.
- If schema/property mismatch is suspected, stop actual export. Run a documented schema/mapping validator command if one exists; otherwise inspect schema/mapping manually before rerunning dry-run.
- Prefer idempotent update by the same `External Key`.
- Do not run multi-account bulk export until duplicate row audit and bulk policy are complete.
- Do not run `paper_default` actual export for new multi-account Daily Ops Status flows.

Daily Ops Status current policy:

- validated actual target: `paper_sandbox`
- validated key example: `daily_ops_status:paper_sandbox:2026-05-20`
- dry-run command: `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --dry-run --json`
- guarded actual command: `python scripts\export_paper_to_notion.py --daily-ops-status --account-id paper_sandbox --confirm-actual --json`

Manual Execution / Manual Review status sync:

- If local commit/append report exists and source-of-truth update succeeded, Notion status sync failure is presentation-layer failure.
- Rerun status sync from the same commit/append report.
- Do not regenerate or rewrite the local ledger/review log just because Notion sync failed.
- Use `--dry-run` first where the sync script supports it.

Duplicate safety:

- If an actual export might have created a duplicate row, stop bulk reruns.
- Use `External Key`, `Account ID`, and `Status Date` to inspect the candidate duplicate manually.
- Defer duplicate row cleanup to a future duplicate row audit procedure.

## Manual Notion View Cleanup Procedure

This procedure is for the user after Codex completes this MFU. Codex does not perform these Notion UI operations.

1. Open the existing `Daily Ops Status` DB.
2. Do not create a new DB.
3. If using a linked database, confirm it points to the same `Daily Ops Status` DB.
4. Do not duplicate the database as a separate DB.
5. Create or rename views exactly:
   - `Today Ops`
   - `By Account`
   - `Needs Action`
   - `Recent Sync`
   - `Review Closeout`
6. Apply the filters, sorting, grouping, visible fields, and hidden fields from `mfu_paper16_daily_ops_status_dashboard_design.md`.
7. Keep `External Key`, `Account ID`, `Status Date`, `Workflow Status`, `Review Progress Status`, and `Sync Status` visible in at least one troubleshooting view.
8. Hide internal/debug fields only at the view layer; do not delete properties.
9. Do not manually edit `External Key`.
10. After cleanup, compare view names and visible fields against this SOP and the PAPER16-1 dashboard design.

## PAPER16-3 Readiness Checklist

PAPER16-3 can check manual Notion screen consistency after the user completes the view cleanup.

Checklist:

- `Today Ops` exists and shows selected-date account status.
- `By Account` groups or sorts rows by account history.
- `Needs Action` surfaces non-done workflow rows and failed sync rows.
- `Recent Sync` shows `External Key`, `Sync Status`, and `Synced At`.
- `Review Closeout` shows review progress and pending counts.
- No duplicate Daily Ops Status DB was created.
- `External Key` was not manually edited.
- `paper_default` actual export remains disabled.
- No multi-account bulk export was run.

## Risks / Open Questions

- `NOT_SYNCED`, `SYNC_FAILED`, and `READY` are operator concepts or future candidates, not fully stable emitted values in all current code paths.
- Status-specific commands should be refined once more than one non-default account is operating.
- Existing SOP files contain legacy encoding artifacts; this MFU adds only minimal addenda.
