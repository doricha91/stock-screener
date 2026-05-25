# MFU-PAPER14-6: Daily Review Summary Notion Export

## Purpose

Add a read-only Notion export for the end-of-day manual execution review summary.

이번 PAPER14-6은 Daily Review Summary Notion read-only export 작업이며, Manual Execution import/commit, Notion status back-write, broker/API 연동은 수행하지 않는다.

## Source artifact

Priority order:

1. `outputs/paper_test/reports/manual_execution_import_commit_YYYYMMDD.json`
2. `outputs/paper_test/paper_execution_log.csv`
   - filtered by `date = review_date`
   - filtered by `source = notion_manual_execution`
3. `paper_account_snapshot.csv`
4. `paper_position_snapshot.csv`
5. `paper_current_state_YYYYMMDD.json` when available

Policy:

- The exporter does not re-read Notion Manual Executions rows.
- Missing commit report does not fail the export by itself.
- If the commit report is missing but ledger rows exist, the export falls back to ledger-derived activity with `availability_status = NO_COMMIT_REPORT`.

## Notion property mapping

Data source key:

- `daily_review_summaries`

Property contract:

- `Name`
- `External Key`
- `Review Date`
- `Review Status`
- `Availability Status`
- `Committed Trade Count`
- `Warning Count`
- `Fail Count`
- `Cash Start`
- `Cash End`
- `Cash Impact`
- `Position Impact Summary`
- `Commit Report Path`
- `Preview Report Path`
- `Latest Snapshot Date`
- `Schema Version`
- `Synced At`
- `Sync Status`

## External Key

- `daily_review_summary:{review_date}`
- Example: `daily_review_summary:2026-05-25`

The export uses External Key upsert semantics, so re-running the same date updates the same row.

## Page body

The page body remains intentionally simple and stable:

- `오늘의 리뷰 요약`
- `체결 요약`
- `포지션 변화`
- `경고 / 특이사항`
- `원천 파일`

The body uses headings, bullets, and plain text blocks instead of Notion table blocks.

## Dry-run / actual export policy

- `--dry-run` builds the payload without Notion writes.
- Non-dry-run requires explicit user permission.
- `--all` does not automatically include `daily_review_summaries` in this MFU.

## Manual Executions relationship

- `Manual Executions` is the input/staging layer for actual fills.
- `Daily Review Summary` is a read-only result summary layer.
- The export does not change Manual Executions rows, paper ledgers, or broker state.

## Excluded scope

- Manual Execution import
- Manual Execution commit
- Notion Manual Executions status back-write
- Daily Plan source mutation
- broker/API integration

## Test result summary

- Daily review summary computation tests cover commit-report primary path, no-commit-report fallback, and no-activity behavior.
- Notion exporter tests cover payload types, External Key, and dry-run path.
- Schema validator tests cover the `daily_review_summaries` contract.

## Remaining risks

- If the commit report is missing, warning detail is limited compared with the primary path.
- `paper_current_state_YYYYMMDD.json` may be absent for legacy/manual-commit dates; the exporter tolerates this and keeps the path blank.
- The body is intentionally compact; richer trade diagnostics can be added in a later MFU if needed.
