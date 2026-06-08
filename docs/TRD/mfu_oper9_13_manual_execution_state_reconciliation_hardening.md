# MFU-OPER9-13 Manual Execution State Reconciliation Hardening

## 1. Summary

OPER9-13 hardens the Manual Execution section of the Daily Ops Orchestrator after the smoke account reached post-sync execution state.

The goal is to keep `operator_summary`, `next_command`, and reconciliation aligned with the real operational state:

- DRAFT Manual Execution rows mean the operator must enter Actual Price and set Status to READY in Notion.
- Post-commit/post-sync Manual Execution rows are not expected to remain READY.
- Missing Notion `Account ID` select options should surface as a structured operator warning instead of an opaque HTTP 400 warning.

## 2. Baseline

- Baseline commit: `772226e8d5938d71ade290460270e92e3313d680`
- Smoke account: `paper_orch_smoke_202606`
- Dates:
  - data_date: `2026-06-05`
  - trade_date: `2026-06-08`

## 3. Problem Analysis

Three state handling gaps were found:

1. Manual Execution DRAFT rows were not represented as a manual input wait state.
   - Template export creates DRAFT / NOT_IMPORTED rows with blank Actual Price.
   - The correct next action is Notion input, not a Python command.

2. Post-sync Manual Execution rows were falsely treated as a preview conflict.
   - After preview, commit, and status sync, Notion rows can be COMMITTED / IMPORTED / SYNCED.
   - READY rows disappearing after commit/sync is expected.

3. A missing `Account ID` select option produced raw Notion HTTP 400 warnings.
   - OPER9-12 showed the data source ids, endpoints, date filters, and core mapping were valid.
   - The minimum failing condition was an account_id select filter for an account value not present as a Notion select option.

## 4. Policy Changes

### DRAFT Wait State

When Manual Execution rows exist with DRAFT status, no READY rows, missing Actual Price, and no local preview, the Orchestrator now treats the state as manual input wait:

- `operator_summary.current_step=MANUAL_EXECUTION_TEMPLATE`
- `operator_summary.recommended_operator_action=WAIT_FOR_INPUT`
- `operator_summary.next_command=null`
- message: enter Actual Price and set Status to READY in Notion

### Post-Sync Preview Reconciliation

When local execution preview exists and either a local commit report, execution status sync evidence, or Notion post-sync statuses exist, absence of READY rows is no longer a conflict.

Accepted post-sync statuses include:

- `COMMITTED`
- `IMPORTED`
- `SYNCED`
- `STATUS_SYNCED`
- `IMPORT_SYNCED`

The preview stage remains DONE or WARNING according to local preview validity, but `_reconciliation_conflict=false` for normal post-sync state.

### Account ID Select Warning

Notion live-read HTTP 400 errors matching the missing `Account ID` select option pattern are converted into a structured warning:

- `warning_code=NOTION_ACCOUNT_ID_SELECT_OPTION_MISSING`
- redacted operator warning text
- no token, data source id, page id, or private row content

This warning is visible in `operator_summary.warnings`, but it does not block the current actionable upstream stage when that stage can still proceed safely.

## 5. Safety Boundaries

OPER9-13 does not add automatic writes.

Still forbidden:

- Notion create/update/delete from Orchestrator status
- automatic `export_paper_to_notion.py`
- automatic `sync_notion_*`
- automatic `import_notion_* --commit`
- broker/API/order execution
- ledger/DB mutation
- committing `.env`, secrets, generated output, or smoke artifacts

Local CSV/JSON/Markdown/SQLite artifacts remain the source of truth. Notion remains an input/review/status UI.

## 6. Test Coverage

Added regression coverage for:

- Manual Execution DRAFT rows waiting for Notion input
- Manual Execution READY rows still recommending preview
- local preview leading to commit recommendation
- post-sync rows not creating a false reconciliation conflict
- missing Account ID select option warning being structured and redacted
- structured Account ID warning not blocking a valid upstream next command

## 7. Remaining Limits

- The Orchestrator still does not create missing Notion select options.
- A Notion schema preseed or approved template export may still be needed for new account ids.
- `WAIT_FOR_INPUT` is an operator action enum addition intended for n8n rendering; n8n workflow implementation remains OPER10/AUTO scope.
