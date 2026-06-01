## Purpose

Enable a narrowly scoped actual export for `Daily Ops Status` so one `paper_sandbox` status row can be created or updated in Notion.

## Scope / Non-scope

In scope:
- `--daily-ops-status` actual export for `account_id=paper_sandbox`
- External Key based single-row upsert
- schema-pass guard before write

Out of scope:
- bulk export
- other Notion data sources
- Notion migration
- paper ledger changes
- broker/API and cloud runner work

## Actual Export Guard

- `--daily-ops-status` actual export requires `--confirm-actual`
- `--daily-ops-status` actual export rejects any account except `paper_sandbox`
- dry-run and actual flags cannot be combined
- data source id must be configured
- schema validation must return `PASS`

## Upsert Policy

- External Key: `daily_ops_status:{account_id}:{status_date}`
- query existing row by `External Key`
- existing row -> `update`
- missing row -> `create`
- `Sync Status = SYNCED`
- `Synced At = actual export timestamp`
- `Schema Version = daily_ops_status.v1`

## Failure Handling

For actual export failures, CLI returns a JSON-friendly failure summary with:
- `action=failed`
- `sync_status=FAILED`
- `error`

## Verification

- schema validation
- dry-run payload generation
- guarded actual export for `paper_sandbox`

## Next MFU

- broaden Daily Ops Status actual export from `paper_sandbox` to explicitly approved non-default accounts
- add duplicate-row audit and operator runbook for Daily Ops Status closeout
