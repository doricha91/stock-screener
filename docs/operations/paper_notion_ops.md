# Paper Notion Operations Guide

## 1. Purpose

This document explains the detailed PAPER14 Notion operating procedure.

이번 PAPER14 Notion 운영 절차는 Notion을 source of truth로 두지 않는다.

- Notion = 입력 UI / 검토 UI / staging layer
- CSV / JSON / Markdown / SQLite = source of truth
- Python = validation / preview / commit / append 주체

## 2. Notion DB roles

### `Daily Plans`

- System-generated daily plan
- Review and presentation layer only
- Operators use it to confirm today's intended action

### `Manual Executions`

- Input UI for actual fills
- Staging layer before execution preview and commit

### `Daily Review Summaries`

- System-generated day-end result summary
- Review layer only

### `Manual Reviews`

- Input UI for retrospective answers at question level
- Staging layer before review append

### `Account Snapshots`

- Read-only account status export

### `Weekly Reports`

- Read-only weekly rollup export

### `Benchmark Reports`

- Read-only benchmark comparison export

## 3. Daily operating sequence

### 3.1 Daily Plan

Generate the plan locally first, then export it to Notion.

### 3.2 Manual Executions

Use Notion only for input, then validate and commit locally.

```cmd
python scripts\import_notion_executions.py --date 2026-05-25 --preview --json
python scripts\import_notion_executions.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_execution_import_preview_20260525.json --allow-warnings
python scripts\sync_notion_execution_status.py --date 2026-05-25 --commit-report outputs\paper_test\reports\manual_execution_import_commit_20260525.json --json
```

### 3.3 Daily Review Summary

Generate the review summary from local source artifacts and export it to Notion.

```cmd
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --dry-run --json
python scripts\export_paper_to_notion.py --daily-review-summary --date 2026-05-25 --json
```

### 3.4 Manual Reviews

Use Notion only for answer entry, then validate and append locally.

```cmd
python scripts\import_notion_reviews.py --date 2026-05-25 --preview --json
python scripts\import_notion_reviews.py --date 2026-05-25 --commit --preview-json outputs\paper_test\reports\manual_review_import_preview_20260525.json --allow-warnings
python scripts\sync_notion_review_status.py --date 2026-05-25 --commit-report outputs\paper_test\reports\manual_review_import_commit_20260525.json --json
```

## 4. Import Status and Validation Status

### `READY`

- Input has been entered in Notion
- Candidate is waiting for Python preview

### `COMMITTED`

- The local source-of-truth artifact was successfully committed or appended
- Status sync may write this back to Notion afterward

### `PASS`

- Validation produced no blocking issue

### `WARNING`

- Validation found non-fatal issues
- Commit or append is blocked by default
- The operator must explicitly use `--allow-warnings` to continue

### `FAIL`

- Validation found blocking issues
- Commit or append must not run

## 5. Dry-run, created, updated

### `dry-run`

- Payload and decision path are built
- Notion write does not happen
- CSV / ledger / review log write does not happen

### `created`

- No existing Notion row was found for the External Key
- A new Notion row is created

### `updated`

- One existing Notion row was found for the External Key
- The existing row is updated instead of duplicated

## 6. WARNING and FAIL handling

- `FAIL` means stop and fix the issue first.
- `WARNING` means stop by default.
- Use `--allow-warnings` only when the operator explicitly accepts the risk.
- When `--allow-warnings` is used, record the reason in the review note or operation note.

## 7. Smartphone vs PC

### Smartphone-friendly

- Confirm `Daily Plan`
- Enter `Manual Executions`
- Confirm `Daily Review Summary`
- Enter `Manual Reviews`
- Check `READY` / `COMMITTED` status in Notion

### Local PC required

- Run preview commands
- Run commit / append commands
- Refresh local source-of-truth artifacts
- Run status back-write
- Run Notion export and sync commands

## 8. Notion sync failure response

If local source-of-truth commit succeeds but Notion sync fails:

- do not roll back the local source artifacts
- keep the ledger / review log as-is
- re-run only the matching status sync command with the same commit report

This applies because Notion sync is a presentation / status layer, not the source of truth.

## 9. Out of scope

This SOP does not cover:

- Notion DB auto-creation
- Notion schema migration
- mobile remote execution
- GitHub Actions automation
- broker/API integration
