# MFU-OPER9-6 Local Notion Reconciliation Matrix

## 1. Purpose

MFU-OPER9-6 standardizes how the Daily Ops Orchestrator combines local source-of-truth artifacts with optional read-only Notion live status.

Notion remains an input and review UI. Local CSV, JSON, Markdown, and SQLite artifacts remain the source-of-truth layer. This MFU does not add Notion writes, commits, appends, ledger changes, broker integration, or n8n workflows.

## 2. JSON Contract

When Notion read is skipped, local-only behavior remains compatible and reconciliation is marked unchecked.

Stage-level additions:

```json
{
  "local_stage_status": "DONE|READY|WARNING|BLOCKED|UNKNOWN|NOT_STARTED",
  "notion_stage_status": "PASS|WARNING|BLOCKED|UNKNOWN|SKIPPED|null",
  "reconciliation_checked": true,
  "reconciliation_status": "DONE|READY|WARNING|BLOCKED|UNKNOWN|null",
  "reconciliation_rule_id": "OPER9_6_...",
  "reconciliation_reason": "human readable reason"
}
```

Top-level addition:

```json
{
  "reconciliation_summary": {
    "checked": true,
    "has_conflicts": false,
    "conflict_count": 0,
    "blocking_conflict_count": 0,
    "warning_conflict_count": 0,
    "recommended_operator_action": "NONE|RUN_NEXT_COMMAND|CHECK_NOTION|RUN_PREVIEW|RUN_COMMIT|RUN_SYNC|RESOLVE_CONFLICT"
  }
}
```

## 3. Source-of-Truth Rule

The reconciler must not mark a source-of-truth stage complete from Notion alone.

- Notion Daily Plan rows without a local Daily Plan are a conflict.
- Notion COMMITTED/SYNCED rows without a local commit or append report are a conflict.
- Local ledger, snapshot, or review log evidence without the matching commit report suppresses repeated commit/append recommendations.
- BLOCKED reconciliation suppresses risky next commands.

## 4. Matrix

| Stage | Local state | Notion state | Reconciled status | Rule intent |
| --- | --- | --- | --- | --- |
| DAILY_PLAN_NOTION_EXPORT | Daily Plan missing | no Daily Plan row | BLOCKED | Generate local Daily Plan first. |
| DAILY_PLAN_NOTION_EXPORT | Daily Plan exists | no Daily Plan row | READY | Export local plan to Notion. |
| DAILY_PLAN_NOTION_EXPORT | Daily Plan exists | Daily Plan row exists | DONE | Local artifact and UI row agree. |
| DAILY_PLAN_NOTION_EXPORT | Daily Plan missing | Daily Plan row exists | WARNING | Notion row exists without local source artifact. |
| MANUAL_EXECUTION_TEMPLATE | Daily Plan exists | no execution row | READY | Export Manual Execution template. |
| MANUAL_EXECUTION_TEMPLATE | Daily Plan exists | DRAFT/READY row exists | DONE | Template rows are present in Notion. |
| MANUAL_EXECUTION_TEMPLATE | Daily Plan missing | execution row exists | WARNING | Notion rows exist without local Daily Plan. |
| MANUAL_EXECUTION_TEMPLATE | any | account/date mismatch | BLOCKED | Mismatched Notion rows are unsafe. |
| MANUAL_EXECUTION_PREVIEW | preview missing | READY rows exist | READY | Run read-only execution preview. |
| MANUAL_EXECUTION_PREVIEW | preview missing | READY rows with missing Actual Price | WARNING | Operator must fix Notion input before commit. |
| MANUAL_EXECUTION_PREVIEW | preview valid | READY rows exist | DONE or WARNING | Local preview remains authoritative. |
| MANUAL_EXECUTION_PREVIEW | preview missing | no READY rows | UNKNOWN | No actionable Notion input found. |
| MANUAL_EXECUTION_PREVIEW | preview exists | no READY rows | WARNING | Notion state may have changed after preview. |
| MANUAL_EXECUTION_COMMIT | preview valid, commit missing | not COMMITTED/SYNCED | READY | Commit may be recommended after operator review. |
| MANUAL_EXECUTION_COMMIT | commit report exists | any | DONE | Local commit report is source-of-truth. |
| MANUAL_EXECUTION_COMMIT | commit missing | COMMITTED/SYNCED | BLOCKED | Notion cannot prove local commit completion. |
| MANUAL_EXECUTION_COMMIT | ledger/snapshot exists, commit missing | any | WARNING | Suppress repeat commit recommendation. |
| MANUAL_EXECUTION_STATUS_SYNC | commit report exists | not COMMITTED/SYNCED | READY | Run status sync. |
| MANUAL_EXECUTION_STATUS_SYNC | commit report exists | COMMITTED/SYNCED | DONE | Local commit and Notion status agree. |
| MANUAL_EXECUTION_STATUS_SYNC | commit report missing | COMMITTED/SYNCED | BLOCKED | Notion status lacks local source evidence. |
| MANUAL_EXECUTION_STATUS_SYNC | commit report missing | any | BLOCKED | Commit report is required for sync. |
| MANUAL_REVIEW_TEMPLATE | review template missing | any | BLOCKED | Generate local review template first. |
| MANUAL_REVIEW_TEMPLATE | review template exists | no review rows | READY | Export Manual Review template. |
| MANUAL_REVIEW_TEMPLATE | review template exists | review rows exist | DONE | Local template and UI rows agree. |
| MANUAL_REVIEW_PREVIEW | preview missing | READY/reviewed rows exist | READY | Run read-only review preview. |
| MANUAL_REVIEW_PREVIEW | preview exists | READY/reviewed rows exist | DONE or WARNING | Local preview remains authoritative. |
| MANUAL_REVIEW_PREVIEW | preview missing | no READY/reviewed rows | UNKNOWN | No actionable review input found. |
| MANUAL_REVIEW_PREVIEW | preview exists | no READY/reviewed rows | WARNING | Notion state may have changed after preview. |
| MANUAL_REVIEW_APPEND | review preview valid, commit missing | not committed/synced | READY | Append may be recommended after operator review. |
| MANUAL_REVIEW_APPEND | review commit report exists | any | DONE | Local review commit report is source-of-truth. |
| MANUAL_REVIEW_APPEND | commit report missing | committed/synced | BLOCKED | Notion cannot prove local append completion. |
| MANUAL_REVIEW_STATUS_SYNC | review commit report exists | sync not reflected | READY | Run review status sync. |
| MANUAL_REVIEW_STATUS_SYNC | review commit report exists | committed/synced | DONE | Local append and Notion status agree. |
| MANUAL_REVIEW_STATUS_SYNC | review commit report missing | any | BLOCKED | Review commit report is required for sync. |
| FINAL_STATUS | workflow_status REVIEW_DONE | key sync reflected | DONE | Local workflow is complete. |
| FINAL_STATUS | workflow_status REVIEW_DONE | key sync not reflected | WARNING | Keep next commands null and report sync conflict. |
| FINAL_STATUS | workflow_status not REVIEW_DONE | any | existing flow | Preserve existing next stage recommendation. |

## 5. Next Action Policy

- READY preview stages recommend `RUN_PREVIEW`.
- READY commit or append stages recommend `RUN_COMMIT`.
- READY sync stages recommend `RUN_SYNC`.
- READY Notion export/template stages recommend `RUN_NEXT_COMMAND`.
- BLOCKED or conflict stages recommend `RESOLVE_CONFLICT` and suppress risky commands.
- `REVIEW_DONE` continues to suppress top-level and stage-level `next_command` and `next_action`; unsynced Notion state is reported through reconciliation warnings.

## 6. Exclusions

This MFU does not execute or add:

- Notion create/update/delete
- `export_paper_to_notion.py`
- `sync_notion_execution_status.py`
- `sync_notion_review_status.py`
- `import_notion_executions.py --commit`
- `import_notion_reviews.py --commit`
- broker/API/order integration
- ledger or DB mutation
- generated output commits
- n8n workflow implementation

## 7. OPER9-4A Check

The repository already contains `docs/TRD/mfu_oper9_4a_evidence_filename_date_format_alignment.md`, and orchestrator tests assert compact evidence filenames such as `daily_plan_notion_export_20260608.json`. MFU-OPER9-6 keeps that contract unchanged.
