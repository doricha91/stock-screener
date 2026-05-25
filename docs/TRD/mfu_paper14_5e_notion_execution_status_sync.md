# MFU-PAPER14-5E: Manual Execution Status Sync

## Purpose

Sync PAPER14-5D Manual Execution commit results back to the Notion `Manual Executions` rows.

이번 PAPER14-5E는 Manual Execution commit 결과를 Notion Manual Executions row에 상태값으로 back-write하는 작업이며, paper ledger commit, Daily Review Summary export, broker/API 연동은 수행하지 않는다.

## Sync source

- Source artifact: `outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.json`
- Sync decision is based only on the commit report.
- The sync flow does not re-query Notion to decide whether a row was committed.

## Back-write fields

Only the following properties are updated:

- `External Key`
- `Validation Status`
- `Validation Message`
- `Import Status`
- `Imported At`
- `Synced At`
- `Status`

Recommended values:

- `External Key` = `candidate.canonical_key`
- `Validation Status` = `PASS` or `WARNING`
- `Validation Message` = summarized warning list, or `OK`
- `Import Status` = `COMMITTED`
- `Imported At` = sync timestamp
- `Synced At` = sync timestamp
- `Status` = `IMPORTED`

## Fields not updated

The sync step must not modify the source input fields:

- `Execution Date`
- `Symbol`
- `Side`
- `Quantity`
- `Actual Price`
- `Commission`
- `Currency`
- `Broker`
- `Note`
- `Plan Date`
- `Linked Daily Plan Key`

## Dry-run policy

- `--dry-run` builds the payload and result summary without updating any Notion page.
- Non-dry-run updates pages by `page_id`.
- `page_id`, `canonical_key`, and `committed_trade_id` must all be present in the commit report row.
- Missing required fields produce a `SKIPPED` row result rather than a write attempt.

## Failure handling

- Notion update failure is reported per row.
- `overall_status` becomes `PARTIAL_SUCCESS` when some rows succeed and some fail or skip.
- Notion sync failure does not roll back paper ledger files.

Reason:

- 5E is a post-commit presentation sync step.
- The paper ledger is already the source of truth by the time status sync runs.

## Operational response

- If dry-run succeeds, operators can run the non-dry-run command for the same commit report.
- If some rows fail to sync, keep the ledger as-is and rerun the status sync after fixing Notion access or page issues.
- Re-running the same commit report is idempotent because the sync writes the same status values again.
