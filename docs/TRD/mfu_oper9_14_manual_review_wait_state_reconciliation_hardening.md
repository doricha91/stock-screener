# MFU-OPER9-14 Manual Review Wait State Reconciliation Hardening

## 1. Summary

OPER9-14 hardens the Manual Review section of the Daily Ops Orchestrator.

After Manual Review template export, Notion can contain review rows that are still `PENDING` / `DRAFT`. In that state the next operator action is not a Python command. The operator must enter Manual Answer and update Review Status in Notion before running the review preview import.

## 2. Baseline

- Baseline commit: `79530dbf8c79bb6187c936c5bd3be185a8558746`
- Smoke account: `paper_orch_smoke_202606`
- Dates:
  - data_date: `2026-06-05`
  - trade_date: `2026-06-08`

## 3. Problem Analysis

The smoke account reached a valid Manual Review template-export state:

- Manual Review rows exist in Notion.
- The rows are `PENDING` / `DRAFT`.
- No READY / REVIEWED rows exist yet.
- No local review preview artifact exists yet.

The Orchestrator previously allowed the diagnostic `FINAL_STATUS` command to become operator-facing `next_command`, which made n8n render a Python status command instead of a human input wait state.

## 4. Policy Changes

### Manual Review Input Wait

Manual Review rows are treated as input wait when:

- Manual Review template stage is complete.
- Notion Manual Review rows exist.
- status counts include `PENDING` or `DRAFT`.
- status counts do not include `READY`, `REVIEWED`, or `ANSWERED`.
- local review preview artifact does not exist.

Expected operator summary:

- `current_step=MANUAL_REVIEW_TEMPLATE` or `MANUAL_REVIEW_PREVIEW`
- `recommended_operator_action=WAIT_FOR_INPUT`
- `next_command=null`
- operator message instructs the operator to enter Manual Answer and set Review Status to READY/REVIEWED in Notion.

### Manual Review Preview Ready

When Manual Review rows contain `READY` or `REVIEWED` and no local review preview exists, the operator-facing next step remains:

```cmd
python scripts\import_notion_reviews.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --preview --json
```

`FINAL_STATUS` must not become current step in that state.

### Manual Review Append Ready

When local review preview exists and review commit report is missing, the operator-facing next step remains the append/commit command:

```cmd
python scripts\import_notion_reviews.py --date <TRADE_DATE> --account-id <ACCOUNT_ID> --commit --preview-json "<PATH>" --json
```

This remains manual-approval gated because it mutates local source-of-truth review artifacts.

## 5. Notion Details Additions

Manual Review live-read details are additive and include:

- `pending_review_count`
- `draft_import_status_count`
- `ready_review_count`
- `reviewed_count`
- `missing_manual_answer_count`

The existing `missing_actual_price_count` field remains for backward compatibility.

## 6. Safety Boundaries

OPER9-14 does not execute writes.

Still forbidden:

- Notion create/update/delete from Orchestrator status
- automatic `export_paper_to_notion.py`
- automatic `sync_notion_*`
- automatic `import_notion_reviews.py --commit`
- broker/API/order execution
- ledger/DB mutation
- committing `.env`, secrets, generated output, or smoke artifacts

Local CSV/JSON/Markdown/SQLite artifacts remain the source of truth. Notion remains an input/review/status UI.

## 7. Test Coverage

Added regression coverage for:

- Manual Review PENDING/DRAFT rows waiting for Notion input
- Manual Review READY rows recommending review preview
- local review preview recommending review append with manual approval
- REVIEW_DONE terminal policy remaining unchanged
- OPER9-13 Manual Execution wait/post-sync tests remaining intact

## 8. Remaining Limits

- The Orchestrator still does not validate individual review answer quality.
- The Orchestrator does not write Review Status changes back to Notion.
- n8n rendering and approval flow remain OPER10/AUTO scope.
